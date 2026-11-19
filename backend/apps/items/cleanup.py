"""Fixes for trafilatura's output, after extraction."""

import re

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


def clean_markdown(markdown: str) -> str:
    return drop_repeats(scripts_to_text(markdown), "\n\n")


def clean_text(text: str) -> str:
    return drop_repeats(text, "\n")
