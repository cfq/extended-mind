"""Article extraction: trafilatura, with fixes around it. Before:
image markup tidied and in-page link targets marked. After: markdown and
text cleaned. Also the page's Open Graph, Twitter and article meta tags."""

import re
from datetime import date
from urllib.parse import urldefrag, urljoin

import trafilatura
from lxml import html as lxml_html
from trafilatura.utils import load_html

from apps.items.models import Item
from apps.items.pipeline.download import FetchError
from apps.items.tagging import rules as tagging

# srcset: the candidate closest to this width, preferring wider.
TARGET_WIDTH = 1600
# A 1x candidate with no width, roughly.
X_WIDTH = 800
LAZY_SRC = ("data-src", "data-lazy-src", "data-original")
LAZY_SRCSET = ("data-srcset", "data-lazy-srcset")

# Shorter blocks (separators, headings, "Image credit") can repeat for real.
MIN_REPEAT = 80
# A block is a repeat when this share of its 8-word runs came earlier.
# Catches a second copy split into paragraphs differently.
REPEAT_SHARE = 0.8
SHINGLE = 8
WORD = re.compile(r"\w+")

SCRIPT_TAG = re.compile(r"<(sup|sub)>(.*?)</\1>", re.DOTALL)
LINK = re.compile(r"\[([^\]]*)\]\(([^)]*)\)")
SCRIPTABLE = re.compile(r"[0-9+\-=()]+")
SUPERSCRIPT = str.maketrans("0123456789+-=()", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾")
SUBSCRIPT = str.maketrans("0123456789+-=()", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎")


# In-page links (footnotes and their back-links). trafilatura drops
# element ids, so targets are marked in the text before extraction and
# turned into anchors after: [](#anchor:id), rendered by the reading view.
MARK_OPEN, MARK_CLOSE = "\u2045anchor:", "\u2046"
MARK = re.compile(re.escape(MARK_OPEN) + r"([\w\-:.\\]+?)" + re.escape(MARK_CLOSE))
ANCHOR_ID = re.compile(r"[\w\-:.]+")
# Marked just before the element; blocks are marked at their start.
INLINE = {"a", "sup", "sub", "span", "em", "strong", "b", "i", "small", "cite"}


def mark_anchors(tree) -> None:
    """Puts a text marker at each element an in-page link points to."""
    targets = {
        href[1:]
        for a in tree.iter("a")
        if (href := a.get("href") or "").startswith("#") and len(href) > 1
    }
    for element in tree.xpath("//*[@id]"):
        anchor = element.get("id")
        if anchor not in targets or not ANCHOR_ID.fullmatch(anchor):
            continue
        mark = f"{MARK_OPEN}{anchor}{MARK_CLOSE}"
        # <sup><a id=…>1</a></sup>: mark before the <sup>, so its content
        # stays a bare link and becomes a superscript.
        while (
            element.tag in INLINE
            and (parent := element.getparent()) is not None
            and parent.tag in INLINE
            and element.getprevious() is None
            and not (parent.text or "").strip()
        ):
            element = parent
        if element.tag not in INLINE:
            element.text = mark + (element.text or "")
        elif (previous := element.getprevious()) is not None:
            previous.tail = (previous.tail or "") + mark
        elif (parent := element.getparent()) is not None:
            parent.text = (parent.text or "") + mark


def local_links(markdown: str, url: str) -> str:
    """Links to this page plus a #fragment become just the #fragment."""
    page = urldefrag(url).url

    def replace(match: re.Match) -> str:
        base, fragment = urldefrag(match.group(1))
        if fragment and base.rstrip("/") == page.rstrip("/"):
            return f"](#{fragment})"
        return match.group(0)

    return re.sub(r"\]\(([^)\s]+)\)", replace, markdown)


def anchors(markdown: str) -> str:
    # trafilatura escapes markdown characters in text (fn\_1).
    return MARK.sub(
        lambda m: f"[](#anchor:{m.group(1).replace(chr(92), '')})", markdown
    )


def shingles(block: str) -> set[str]:
    words = WORD.findall(block.lower())
    if len(words) < SHINGLE:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i : i + SHINGLE]) for i in range(len(words) - SHINGLE + 1)}


def drop_repeats(text: str, separator: str) -> str:
    """Drops long blocks that mostly repeat earlier text. Some pages carry
    the article twice and trafilatura keeps both."""
    seen: set[str] = set()
    kept = []
    for block in text.split(separator):
        runs = shingles(block)
        if len(block.strip()) >= MIN_REPEAT and runs:
            if len(runs & seen) / len(runs) >= REPEAT_SHARE:
                continue
        seen |= runs
        kept.append(block)
    return separator.join(kept)


def replace_script(match: re.Match) -> str:
    tag, inner = match.group(1), match.group(2).strip()
    link = LINK.fullmatch(inner)
    text = link.group(1).strip() if link else inner
    if SCRIPTABLE.fullmatch(text):
        text = text.translate(SUPERSCRIPT if tag == "sup" else SUBSCRIPT)
    return f"[{text}]({link.group(2)})" if link else text


def scripts_to_text(markdown: str) -> str:
    """trafilatura writes <sup>/<sub> as raw HTML, which the reading view
    shows as text. Footnote numbers become superscript digits (still
    links); anything else becomes plain text."""
    return SCRIPT_TAG.sub(replace_script, markdown)


def clean_markdown(markdown: str, url: str) -> str:
    markdown = anchors(local_links(scripts_to_text(markdown), url))
    return drop_repeats(markdown, "\n\n")


def clean_text(text: str) -> str:
    return drop_repeats(MARK.sub("", text), "\n")


# HTML tidying, before extraction.


def parse_srcset(srcset: str) -> list[tuple[str, float]]:
    """[(url, width)]. URLs can contain commas (Substack's do), so
    candidates are split on a comma followed by whitespace."""
    candidates = []
    for part in re.split(r",\s+", srcset.strip()):
        bits = part.strip().rstrip(",").split()
        if not bits:
            continue
        width = float(X_WIDTH)
        if len(bits) > 1:
            descriptor = bits[-1]
            try:
                if descriptor.endswith("w"):
                    width = float(descriptor[:-1])
                elif descriptor.endswith("x"):
                    width = float(descriptor[:-1]) * X_WIDTH
            except ValueError:
                pass
        candidates.append((bits[0], width))
    return candidates


def best_source(candidates: list[tuple[str, float]]) -> str | None:
    if not candidates:
        return None
    wide = [c for c in candidates if c[1] >= TARGET_WIDTH]
    if wide:
        return min(wide, key=lambda c: c[1])[0]
    return max(candidates, key=lambda c: c[1])[0]


def is_placeholder(src: str | None) -> bool:
    return not src or src.startswith("data:")


def tidy_html(html: str | bytes, url: str) -> str | bytes:
    """Rewrites image markup trafilatura would drop or misread:
    <picture> to one <img>, srcset to the best src, lazy-load attributes
    to src, relative URLs to absolute."""
    tree = trafilatura.load_html(html)
    if tree is None:
        return html

    for img in tree.iter("img"):
        for attr in LAZY_SRCSET:
            if img.get(attr):
                img.set("srcset", img.get(attr))
        for attr in LAZY_SRC:
            if img.get(attr) and is_placeholder(img.get("src")):
                img.set("src", img.get(attr))

    for picture in list(tree.iter("picture")):
        img = next(picture.iter("img"), None)
        if img is None:
            continue
        candidates = []
        for source in picture.iter("source"):
            candidates += parse_srcset(source.get("srcset") or "")
        candidates += parse_srcset(img.get("srcset") or "")
        best = best_source(candidates)
        if best:
            img.set("src", best)
        img.attrib.pop("srcset", None)
        img.tail = picture.tail
        picture.getparent().replace(picture, img)

    for img in tree.iter("img"):
        best = best_source(parse_srcset(img.get("srcset") or ""))
        if best:
            img.set("src", best)
        img.attrib.pop("srcset", None)
        img.attrib.pop("sizes", None)

    mark_anchors(tree)
    tree.make_links_absolute(url, resolve_base_href=True, handle_failures="ignore")
    return lxml_html.tostring(tree, encoding="unicode")


# Extraction.


def parse_date(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def extract(item: Item, html: str | bytes) -> list[str]:
    """Fills the item's content and metadata from a page's HTML, on the
    item and its page (unsaved). Returns the tags the page declares."""
    page = item.page
    page.meta = parse_meta(html)
    html = tidy_html(html, item.url)
    markdown = trafilatura.extract(
        html,
        url=item.url,
        output_format="markdown",
        include_links=True,
        include_formatting=True,
        include_images=True,
    )
    if not markdown:
        raise FetchError("No article content found.")
    metadata = trafilatura.extract_metadata(html, default_url=item.url)
    item.title = (metadata and metadata.title) or ""
    item.description = (metadata and metadata.description) or ""
    item.site_name = (metadata and metadata.sitename) or ""
    item.published_at = parse_date(metadata and metadata.date)
    page.author = (metadata and metadata.author) or ""
    page.markdown = clean_markdown(markdown, item.url)
    text = trafilatura.extract(html, url=item.url, output_format="txt") or ""
    page.text = clean_text(text)
    if not metadata:
        return []
    return tagging.page_tags(metadata.categories, metadata.tags)


# Meta tags: kept as the page declares them.

PREFIXES = ("og:", "twitter:", "article:")
# The sharing image, in order of preference.
IMAGE_KEYS = (
    "og:image:secure_url",
    "og:image",
    "og:image:url",
    "twitter:image",
    "twitter:image:src",
)


def parse_meta(html: str | bytes) -> dict[str, str | list[str]]:
    """Meta tags whose property or name starts with og:, twitter: or
    article:. Keys lowercased; a key that repeats maps to a list."""
    # trafilatura's loader: detects the encoding of bytes, as extraction does.
    tree = load_html(html)
    if tree is None:
        return {}
    meta: dict[str, str | list[str]] = {}
    for tag in tree.iter("meta"):
        key = (tag.get("property") or tag.get("name") or "").strip().lower()
        content = (tag.get("content") or "").strip()
        if not key.startswith(PREFIXES) or not content:
            continue
        if key not in meta:
            meta[key] = content
        elif isinstance(meta[key], list):
            meta[key].append(content)
        elif meta[key] != content:
            meta[key] = [meta[key], content]
    return meta


def sharing_image_url(meta: dict, page_url: str) -> str | None:
    """The sharing image's absolute URL, or None."""
    for key in IMAGE_KEYS:
        value = meta.get(key)
        if isinstance(value, list):
            value = value[0]
        if not value:
            continue
        url = urljoin(page_url, value)
        if url.startswith(("http://", "https://")):
            return url
    return None
