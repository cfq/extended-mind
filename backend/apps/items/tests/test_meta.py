from apps.items import fetch, meta

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

    assert meta.parse(html) == {
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

    assert meta.parse(html) == {
        "article:tag": ["design", "cities", "cities", "history"],
        "og:image": "/a.png",
    }


def test_parse_bytes_detects_encoding():
    html = b'<html><head><meta property="og:title" content="Caf\xc3\xa9"></head></html>'

    assert meta.parse(html) == {"og:title": "Caf\u00e9"}


def test_parse_not_a_document():
    assert meta.parse("") == {}
    # Extraction needs a whole document too.
    assert meta.parse('<meta property="og:title" content="x">') == {}


def test_image_url_preference_and_relative():
    assert meta.image_url({"og:image": "/a.png"}, PAGE) == "https://x.test/a.png"
    assert (
        meta.image_url(
            {"og:image": "http://x.test/a.png", "og:image:secure_url": "/s.png"}, PAGE
        )
        == "https://x.test/s.png"
    )
    assert (
        meta.image_url({"twitter:image": "https://cdn.test/t.jpg"}, PAGE)
        == "https://cdn.test/t.jpg"
    )
    assert (
        meta.image_url({"og:image": ["/first.png", "/second.png"]}, PAGE)
        == "https://x.test/first.png"
    )


def test_image_url_none():
    assert meta.image_url({}, PAGE) is None
    assert meta.image_url({"og:image": "data:image/png;base64,xx"}, PAGE) is None


def test_extract_fills_meta(item):
    body = "<p>Some article text about rivers and cities. " * 40
    html = (
        '<html><head><title>T</title><meta property="og:image" content="/i.png">'
        f"</head><body><article>{body}</article></body></html>"
    )

    fetch.extract(item, html)

    assert item.page.meta == {"og:image": "/i.png"}
