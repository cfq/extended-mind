# 0017 - Screenshots and PDFs

## Asked
- Screenshots look blurry, like JPEGs, on cfq's screens.
- Capture at 2×: head and full-page screenshots both PNG.
- Also save the page as a PDF through its print stylesheet. Print styles drop overlays (Wikipedia's donation banner) and well-made sites print beautifully (Asterisk).

## Extrapolated
- Existing screenshots stay at 1×; only new fetches get 2× and a PDF.
- A PDF link in the reading view, next to the screenshot links.

## Changes
### Browser
- Context with `device_scale_factor=2`. Viewport stays 1280×1280 CSS pixels, so pages lay out as before.
- Head screenshot: PNG, 2560×2560.
- Full-page screenshot: PNG, 2560 wide, up to 40,000 tall (the 20,000 CSS pixel cap, doubled).
- PDF: `page.pdf()`, A4, backgrounds on, print media (Playwright's default for PDFs). After the screenshots.
- PDF is best effort: if printing fails, the visit still returns its HTML and screenshots.

### Data
- `ItemSource.Kind.PDF` (`pdf`), saved as `<name>.pdf`, `application/pdf`. Migration `0007` (choices only).

### API
- Item detail gets `pdf`: the source URL, or `null`.
- `GET /items/{id}/sources/{filename}` serves PDFs too.

### Frontend
- Reading view header: "PDF" link after the screenshot links.

### Tests
- Fetch saves the PDF; no PDF source when printing failed, item still done.
- API links and serves the PDF.
- Live browser: head 2560×2560, full 2560×40,000, PDF bytes.

---

## Claude Notes
- Cause of the blur: Playwright's default `device_scale_factor` is 1, so a 1280 CSS pixel page made a 1280 pixel image. High-density screens stretch it 2–3×.
- Started as option B (full page as JPEG q90). Measured full-page captures:

  | Page | 1× PNG | 2× PNG | 2× JPEG q90 | 2× JPEG q80 |
  |---|---|---|---|---|
  | Asterisk (images, 16k px) | 4.4 MB | 12.4 MB | 12.6 MB | 9.3 MB |
  | Wikipedia (text, capped) | 3.3 MB | 7.3 MB | 10.4 MB | 7.7 MB |

  - PNG grows 2–3×, not 4×, at 2×. JPEG q90 is no smaller; on text it's larger. Switched to PNG.
- Rejected: capture at 2× and downscale to 1× (same pixel count, still stretched; needs Pillow). WebP: 16,383 px limit per side, full page would need strips. AVIF: slow on 100 MP images, decoder limits. Both need Pillow.
- Karakeep for reference: 1440×900 viewport, 1×, JPEG q80, viewport-only by default.
- PDF at A4: print stylesheets assume a paper size. A 1280 px "screen" PDF kept the screen layout but repeated fixed overlays on every page.
- PDF sizes depend on embedded images. The Asterisk essay: 4.4 MB at 1×, 12.8 MB in the real fetch at 2×: the page picks larger `srcset` images for the higher density.
- A retry whose PDF fails keeps the previous PDF, like screenshots when a browser visit fails.
- PDFs are served from the app origin like screenshots. Browser PDF viewers run in their own sandbox; a CSP `sandbox` header would stop Chrome rendering them, so none is set.
- Lint: `ruff` fails on `main` with 38 errors in older migrations and two tests; this branch's files are clean. Left for a separate change.
- Real fetch through the dev worker (Asterisk essay): HTML 69 KB, rendered 70 KB, full PNG 12.4 MB, head PNG 1.4 MB (2560×2560), PDF 12.8 MB.
