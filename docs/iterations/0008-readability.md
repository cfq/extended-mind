# 0008 - Readability

## Asked
- Another round on the article page, using readability research.
- Build it so cfq can see it and decide.

## Plan
- Article page only, CSS plus a reading-time line. No backend change.
- Measure: column capped at 65ch, within the 45–75 characters-per-line range.
- Leading: body line height 1.3 → 1.5; headings stay tight.
- Paragraph spacing: one line of space between paragraphs, so text sits on a regular vertical rhythm.
- Headings: a small size scale (h2 > h3 > body), more space above than below so each heading sits with its section.
- Wrapping: balanced lines for headings, no single-word last lines in the title or paragraphs, hyphenation on narrow screens only.
- Links: a visible underline, offset from the text; the current hairline nearly disappears.
- Dark mode: off-white text on a darker grey instead of pure white, which glares.
- Standfirst: larger and upright instead of italic.
- Reading time in the meta line, e.g. "8 min read".

## Out of scope
- Font change, reader settings (size, theme toggle), progress bar, the rest of the app.

---

## Claude Notes
- Measure: 45–75 characters per line is the long-standing range, about 66 the usual target (Bringhurst; Baymard). Built as `31em` (about 66 characters); cfq changed it to `65ch` in review (about 75, still in range). The old 36em was around 78.
- Leading: WCAG 1.4.12 uses 1.5 as its line-height baseline; screen studies favour about 1.4–1.6 for body text at these line lengths. Headings 1.15–1.2.
- Paragraph gap 1.5em, matching the line height, so paragraphs land on the same grid as lines.
- Heading scale about 1.25: h2 1.25em, h3 1.1em, h4 body size; margin about 2em above, 0.5em below (proximity).
- `text-wrap: balance` on the author and headings, `text-wrap: pretty` on paragraphs. Title changed to `pretty` by cfq in review. Browsers that don't support these ignore them.
- `hyphens: auto` at ≤600px only, where the narrow column makes ragged edges worst. Uses `lang="en"`, already set in `index.html`.
- Text stays left-aligned and ragged: justified text without good hyphenation leaves rivers and uneven word spacing.
- Links: `text-decoration` 1px, `text-underline-offset: 0.2em`, colour `--r-meta`; hover darkens to the text colour. The `#e6e6e6` hairline on white is about 1.2:1, so links are hard to find.
- Dark mode: text `#e8e8e8` on `#1f1f1f` (about 15:1). Pure white on dark grey causes halation, especially for people with astigmatism. Meta `#9a9a9a`, rules `#3a3a3a`.
- Blockquote: 10.4% indent each side → a left rule and 1.25em indent, so a quote reads as a quote at the narrower column.
- List items 0.5em apart, paragraphs 1.5em.
- Mobile line height no longer drops to 1.334; 1.5 everywhere.
- Light mode stays `#101010` on `#fff`.
- Kerning and ligatures on (`font-kerning: normal`, `text-rendering: optimizeLegibility`).
- Standfirst: 1.2em, upright, meta colour not used (it must stay readable). Long italic runs read slower.
- Reading time: words in the markdown ÷ 238 wpm (Brysbaert 2019, silent reading of non-fiction), rounded up, min 1. Pure function in `lib/meta.ts` with tests.
- To compare: `localhost:5173` will show the new page; `em.cfqs.com:8000` keeps the old one until the image is rebuilt.
