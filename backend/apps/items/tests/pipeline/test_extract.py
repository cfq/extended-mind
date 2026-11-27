from datetime import date

import pytest
from lxml import html as lxml_html

from apps.items.pipeline import extract

URL = "https://site.test/post/"
LONG = "A paragraph long enough to count as article text, not a separator. " * 2


def test_drops_long_repeats_keeps_short_ones():
    markdown = "\n\n".join(
        ["# Title", LONG, "●", "Other text " * 10, "●", LONG, "# Title"]
    )

    assert extract.clean_markdown(markdown, URL) == "\n\n".join(
        ["# Title", LONG, "●", "Other text " * 10, "●", "# Title"]
    )


def test_drops_copy_split_differently():
    first = "One two three four five six seven eight nine ten. " * 3
    second = "Eleven twelve thirteen fourteen fifteen sixteen seventeen. " * 3
    copy_part = (
        "seven eight nine ten. "
        + "One two three four five six seven eight nine ten. " * 2
    )
    markdown = "\n\n".join([first + second, copy_part, second])

    assert extract.clean_markdown(markdown, URL) == first + second


def test_keeps_paragraph_quoting_a_line():
    quoted = "As I said, one two three four five six seven eight nine ten. " + (
        "Then something entirely new happens in this paragraph with fresh words. " * 3
    )
    earlier = LONG + " One two three four five six seven eight nine ten."
    markdown = "\n\n".join([earlier, quoted])

    assert extract.clean_markdown(markdown, URL) == markdown


def test_text_repeats_by_line():
    assert (
        extract.clean_text(f"{LONG}\nshort\n{LONG}\nshort") == f"{LONG}\nshort\nshort"
    )


def test_footnote_links_become_superscript_links():
    markdown = "felt<sup>[12](https://x.test#fn-1)</sup>. Then<sup> 3 </sup>"

    assert (
        extract.clean_markdown(markdown, URL) == "felt[¹²](https://x.test#fn-1). Then³"
    )


def test_other_scripts_become_text():
    assert extract.clean_markdown("19<sup>th</sup> century, H<sub>2</sub>O", URL) == (
        "19th century, H₂O"
    )


FOOTNOTED = (
    "<html><body><article><h1>Essay</h1>"
    + "<p>Some long text about revolutions and everyday life in the city. " * 6
    + 'and felt<sup class="fn"><a href="#fn-1" id="fn-1-link">1</a></sup>.</p>'
    + "<p>More text that carries on the argument for quite a while longer. " * 6
    + '</p><ol class="footnotes"><li id="fn-1">Guattari and Rolnik, '
    '<em>Molecular Revolution</em>. <a href="#fn-1-link">↩︎</a></li></ol>'
    + '<p>See <a href="https://site.test/other/#top">elsewhere</a> and '
    + '<a href="#missing">a dead link</a>.</p>'
    + "</article></body></html>"
)


def test_footnotes_link_within_the_article():
    from apps.items.models import Item, PageItem

    item = Item(url=URL)
    page = PageItem(item=item)
    extract.extract(item, FOOTNOTED)

    markdown = page.markdown
    # Reference → note, and the note's back-link → reference.
    assert "felt[](#anchor:fn-1-link)[¹](#fn-1)" in markdown
    assert "[](#anchor:fn-1)Guattari and Rolnik" in markdown
    assert "[↩︎](#fn-1-link)" in markdown
    # Other pages keep their URL; a link to a missing id is still local.
    assert "](https://site.test/other/#top)" in markdown
    assert "](#missing)" in markdown
    assert "anchor" not in page.text
    assert "⁅" not in page.text


def test_local_links_only_for_this_page():
    markdown = "[a](https://site.test/post#x) [b](https://site.test/post/) [c](https://x.test/post/#x)"

    assert extract.local_links(markdown, URL) == (
        "[a](#x) [b](https://site.test/post/) [c](https://x.test/post/#x)"
    )


def test_anchor_marks_with_escaped_ids():
    assert extract.anchors("⁅anchor:fn\\_1⁆Note") == "[](#anchor:fn_1)Note"


def imgs(html):
    tree = lxml_html.fromstring(html)
    return [dict(img.attrib) for img in tree.iter("img")]


# HTML tidying


def test_parse_srcset_with_commas_in_urls():
    srcset = (
        "https://cdn.test/fetch/w_424,c_limit/a.png 424w, "
        "https://cdn.test/fetch/w_1456,c_limit/a.png 1456w"
    )
    assert extract.parse_srcset(srcset) == [
        ("https://cdn.test/fetch/w_424,c_limit/a.png", 424),
        ("https://cdn.test/fetch/w_1456,c_limit/a.png", 1456),
    ]
    assert extract.parse_srcset("a.jpg 1x, b.jpg 2x") == [
        ("a.jpg", 800),
        ("b.jpg", 1600),
    ]


def test_best_source_closest_to_1600_preferring_wider():
    assert (
        extract.best_source([("s", 600), ("m", 1200), ("l", 1920), ("xl", 3000)]) == "l"
    )
    assert extract.best_source([("s", 600), ("m", 1200)]) == "m"
    assert extract.best_source([]) is None


def test_tidy_picture_becomes_one_img():
    html = (
        "<html><body><p>Before</p><figure><picture>"
        '<source srcset="/a-600.avif 600w, /a-1920.avif 1920w" type="image/avif">'
        '<img src="/a-300.jpg" alt="A">'
        "</picture><figcaption>Cap</figcaption></figure></body></html>"
    )

    tidied = extract.tidy_html(html, "https://site.test/post")

    assert "<picture" not in tidied
    assert imgs(tidied) == [{"src": "https://site.test/a-1920.avif", "alt": "A"}]
    assert "Cap" in tidied


def test_tidy_lazy_srcset_and_relative():
    html = (
        "<html><body>"
        '<img src="data:image/gif;base64,R0l" data-src="lazy.jpg">'
        '<img src="small.jpg" srcset="small.jpg 400w, big.jpg 1600w" sizes="50vw">'
        '<img data-lazy-srcset="x1.jpg 1x, x2.jpg 2x">'
        "</body></html>"
    )

    tidied = extract.tidy_html(html, "https://site.test/blog/post")

    assert [img.get("src") for img in imgs(tidied)] == [
        "https://site.test/blog/lazy.jpg",
        "https://site.test/blog/big.jpg",
        "https://site.test/blog/x2.jpg",
    ]
    assert not any("srcset" in img or "sizes" in img for img in imgs(tidied))


def test_tidy_respects_base_href():
    html = (
        '<html><head><base href="https://cdn.test/"></head>'
        '<body><img src="a.png"></body></html>'
    )

    assert (
        imgs(extract.tidy_html(html, "https://site.test/"))[0]["src"]
        == "https://cdn.test/a.png"
    )


# Meta tags

PAGE = "https://x.test/posts/one"


def test_parse_keeps_og_twitter_article_tags():
    html = """<html><head>
    <meta property="og:title" content="A title">
    <meta property="OG:Type" content="article">
    <meta name="twitter:card" content="summary_large_image">
    <meta property="article:published_time" content="2026-11-01T10:00:00Z">
    <meta name="description" content="Not kept">
    <meta property="fb:app_id" content="Not kept">
    <meta property="og:empty" content="  ">
    </head><body></body></html>"""

    assert extract.parse_meta(html) == {
        "og:title": "A title",
        "og:type": "article",
        "twitter:card": "summary_large_image",
        "article:published_time": "2026-11-01T10:00:00Z",
    }


def test_parse_repeated_keys_become_lists():
    html = """<html><head>
    <meta property="article:tag" content="design">
    <meta property="article:tag" content="cities">
    <meta property="article:tag" content="cities">
    <meta property="article:tag" content="history">
    <meta property="og:image" content="/a.png">
    <meta property="og:image" content="/a.png">
    </head></html>"""

    assert extract.parse_meta(html) == {
        "article:tag": ["design", "cities", "cities", "history"],
        "og:image": "/a.png",
    }


def test_parse_bytes_detects_encoding():
    html = b'<html><head><meta property="og:title" content="Caf\xc3\xa9"></head></html>'

    assert extract.parse_meta(html) == {"og:title": "Caf\u00e9"}


def test_parse_not_a_document():
    assert extract.parse_meta("") == {}
    # Extraction needs a whole document too.
    assert extract.parse_meta('<meta property="og:title" content="x">') == {}


def test_image_url_preference_and_relative():
    assert (
        extract.sharing_image_url({"og:image": "/a.png"}, PAGE)
        == "https://x.test/a.png"
    )
    assert (
        extract.sharing_image_url(
            {"og:image": "http://x.test/a.png", "og:image:secure_url": "/s.png"}, PAGE
        )
        == "https://x.test/s.png"
    )
    assert (
        extract.sharing_image_url({"twitter:image": "https://cdn.test/t.jpg"}, PAGE)
        == "https://cdn.test/t.jpg"
    )
    assert (
        extract.sharing_image_url({"og:image": ["/first.png", "/second.png"]}, PAGE)
        == "https://x.test/first.png"
    )


def test_image_url_none():
    assert extract.sharing_image_url({}, PAGE) is None
    data_url = {"og:image": "data:image/png;base64,xx"}
    assert extract.sharing_image_url(data_url, PAGE) is None


def test_extract_fills_meta(item):
    body = "<p>Some article text about rivers and cities. " * 40
    html = (
        '<html><head><title>T</title><meta property="og:image" content="/i.png">'
        f"</head><body><article>{body}</article></body></html>"
    )

    extract.extract(item, html)

    assert item.page.meta == {"og:image": "/i.png"}


# Dates


@pytest.mark.parametrize(
    "value, expected",
    [("2026-11-03", date(2026, 11, 3)), ("", None), (None, None), ("not a date", None)],
)
def test_parse_date(value, expected):
    assert extract.parse_date(value) == expected
