from apps.items import cleanup

URL = "https://site.test/post/"
LONG = "A paragraph long enough to count as article text, not a separator. " * 2


def test_drops_long_repeats_keeps_short_ones():
    markdown = "\n\n".join(
        ["# Title", LONG, "●", "Other text " * 10, "●", LONG, "# Title"]
    )

    assert cleanup.clean_markdown(markdown, URL) == "\n\n".join(
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

    assert cleanup.clean_markdown(markdown, URL) == first + second


def test_keeps_paragraph_quoting_a_line():
    quoted = "As I said, one two three four five six seven eight nine ten. " + (
        "Then something entirely new happens in this paragraph with fresh words. " * 3
    )
    earlier = LONG + " One two three four five six seven eight nine ten."
    markdown = "\n\n".join([earlier, quoted])

    assert cleanup.clean_markdown(markdown, URL) == markdown


def test_text_repeats_by_line():
    assert (
        cleanup.clean_text(f"{LONG}\nshort\n{LONG}\nshort") == f"{LONG}\nshort\nshort"
    )


def test_footnote_links_become_superscript_links():
    markdown = "felt<sup>[12](https://x.test#fn-1)</sup>. Then<sup> 3 </sup>"

    assert (
        cleanup.clean_markdown(markdown, URL) == "felt[¹²](https://x.test#fn-1). Then³"
    )


def test_other_scripts_become_text():
    assert cleanup.clean_markdown("19<sup>th</sup> century, H<sub>2</sub>O", URL) == (
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
    from apps.items import fetch
    from apps.items.models import Item, PageItem

    item = Item(url=URL)
    page = PageItem(item=item)
    fetch.extract(item, FOOTNOTED)

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

    assert cleanup.local_links(markdown, URL) == (
        "[a](#x) [b](https://site.test/post/) [c](https://x.test/post/#x)"
    )


def test_anchor_marks_with_escaped_ids():
    assert cleanup.anchors("⁅anchor:fn\\_1⁆Note") == "[](#anchor:fn_1)Note"
