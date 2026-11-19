"""Fixes around trafilatura: marks in-page link targets before
extraction, and cleans its markdown and text after."""

import re
from urllib.parse import urldefrag

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
