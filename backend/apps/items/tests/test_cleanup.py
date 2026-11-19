from apps.items import cleanup

LONG = "A paragraph long enough to count as article text, not a separator. " * 2


def test_drops_long_repeats_keeps_short_ones():
    markdown = "\n\n".join(
        ["# Title", LONG, "●", "Other text " * 10, "●", LONG, "# Title"]
    )

    assert cleanup.clean_markdown(markdown) == "\n\n".join(
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

    assert cleanup.clean_markdown(markdown) == first + second


def test_keeps_paragraph_quoting_a_line():
    quoted = "As I said, one two three four five six seven eight nine ten. " + (
        "Then something entirely new happens in this paragraph with fresh words. " * 3
    )
    earlier = LONG + " One two three four five six seven eight nine ten."
    markdown = "\n\n".join([earlier, quoted])

    assert cleanup.clean_markdown(markdown) == markdown


def test_text_repeats_by_line():
    assert (
        cleanup.clean_text(f"{LONG}\nshort\n{LONG}\nshort") == f"{LONG}\nshort\nshort"
    )


def test_footnote_links_become_superscript_links():
    markdown = "felt<sup>[12](https://x.test#fn-1)</sup>. Then<sup> 3 </sup>"

    assert cleanup.clean_markdown(markdown) == "felt[¹²](https://x.test#fn-1). Then³"


def test_other_scripts_become_text():
    assert cleanup.clean_markdown("19<sup>th</sup> century, H<sub>2</sub>O") == (
        "19th century, H₂O"
    )
