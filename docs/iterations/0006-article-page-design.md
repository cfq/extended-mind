# 0006 - Article page design

A proper reading view for saved articles. Calm, editorial, near-monochrome.

## Decisions
  - Article page only (`/item/{id}`); header, dashboard, forms untouched
  - Typography
    - `system-ui`, one family for everything; no web font yet
    - base 20px on the article page, 18px under 960px wide, 25px over 1600px
    - line height 1.3, 1.334 on mobile
    - proportional figures, antialiased, left-aligned, no hyphenation
  - Colours
    - white background, near-black text, grey meta, hairline rules
    - no accent colour
    - dark mode kept: dark grey background, white text
  - Layout
    - single centred column, about 70 characters a line
    - page gutters 1.5rem, 15px on mobile; column full width on mobile
  - Header
    - large centred title, normal weight
    - author under it
    - meta line: site, published date, saved date, link to the source
  - Body
    - paragraphs spaced, not indented
    - headings body size, bold
    - blockquotes indented both sides, no rule
    - lists with en-dash markers
    - links in text colour with a hairline underline, grey on hover
    - description shown italic above the article as a standfirst
  - Status, retry, delete: small grey text buttons, out of the way

## Backend
  - `Item`: `author`, `site_name`, `published_at` (date)
  - Filled from trafilatura metadata on fetch
  - Returned by the items API
  - `manage.py reextract`: fills them for existing items from the saved HTML, no refetch

## Frontend
  - `ItemPage` restructured: header, standfirst, body, footer
  - Reading styles scoped to the article page

## Tests
  - fetch stores author, site name, published date; bad or missing date → empty
  - API returns the new fields
  - `reextract` fills existing items; items without saved HTML skipped
  - meta line: site name falls back to domain, dates formatted, missing parts left out

## Out of scope
  - Article images (still remote)
  - Web font
  - Rest of the app
  - Lead image, footnotes

---

## Claude Notes

Iteration doc written by Claude at cfq's request.

Small decisions:
- Meta grey `#767676` on white (4.5:1, WCAG AA); `#999` kept for captions and hover. Dark: `#999` meta, `#4d4d4d` hairlines.
- Column capped at 36em (~70 characters); header block 44em.
- No step above 25px: stops at ≥1600px.
- Title 3em/1, normal weight; author 1.5em; meta 0.75em. Mobile: title 2em/1.111.
- Paragraph spacing 1em, 1.33em on mobile. Headings body size, bold, 2em above.
- Links: hairline underline drawn with a gradient, grey on hover.
- Page background goes white (or dark) on the article page only, via `body:has(.reading)`; `.main:has(.reading)` drops the 48rem cap.
- Meta line: site name (falls back to domain) · published date · saved date · Original link. Dates in UTC, `3 November 2026`.
- `published_at` is a date; trafilatura gives `YYYY-MM-DD`, anything unparseable → empty.
- `reextract` passes the saved HTML as bytes: trafilatura detects the encoding.
- Fixtures not regenerated: the new fields default to empty, and `reextract` tests fill them.

Checked:
- `reextract` on the dev database: 6 re-extracted, 1 skipped (no saved HTML), 0 failed.
- Page not looked at in a browser: no login available to Claude.

Found on the way:
- Unitless `letter-spacing`/`word-spacing` values in the reference are invalid CSS and do nothing; not copied.
