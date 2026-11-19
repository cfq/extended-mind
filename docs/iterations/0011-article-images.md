# 0011 - Article images

## Asked
- Save the images in articles, so they survive the original going away.
- Article images only. Uploads and image items come later.

## Extrapolated
- Images that are part of the article: the ones extraction keeps, not logos, avatars or icons.
- Shown from your copy, served by the app behind your login.
- The article's markdown points at your copies; the saved HTML keeps the originals for reference.
- Existing articles get their images too, from the saved HTML. No refetch of pages.
- Downloading images never holds up or fails the save.

## Plan
### Keeping more images through extraction
- trafilatura drops some article images. Of the 9 saved articles, Art Nouveau has 26 `<img>` in its HTML and 0 in the article, because they're inside `<figure><picture>`.
- Before extraction, tidy the HTML:
  - `<picture>`: keep one `<img>` with the best source
  - `srcset`: pick the candidate closest to 1600 px wide
  - lazy-load attributes (`data-src`, `data-lazy-src`, `data-original`) become `src`
  - relative URLs made absolute
- Tested against the saved articles; how many images survive is in the notes.

### Download
- New job `save_images`, queued after a successful fetch (default queue).
- For each image in the article's markdown: GET with the article as `Referer`. Max 20 MB each, 100 per article, 30 s timeout, `image/*` only.
- Saved as `ItemSource` kind `image` in the item's folder, as the HTML is now. Original URL, mime, size and sha256 recorded. Same image twice in an article: saved once.
- Each saved image's link in the markdown is replaced with the local URL. A failed image keeps its original URL.
- Already saved for this item (same original URL): no new download, just the link swap. So `reextract`, which rebuilds the markdown from the HTML, followed by `save_images` restores the local links without downloading again.

### Serving
- `GET /api/v1/items/{id}/sources/{filename}`: session or token, your items only. Long private cache.
- SVGs served with a sandbox Content-Security-Policy, so a script inside one can't run.
- Local links are stored in the markdown as `/api/v1/items/{id}/sources/{filename}`, so that path has to stay stable.

### Backfill
- `reextract` uses the tidied HTML, then queues `save_images`. Run once over existing items.

### Frontend
- Images `loading="lazy"`. Otherwise the reading view's existing image styles.

### Tests
- HTML tidying: picture, srcset, lazy attributes, relative URLs.
- Download: limits, non-image, duplicates, Referer, failure keeps the original URL. HTTP faked.
- Serving: auth, other user's item, SVG header.
- Markdown rewriting: saved images swapped, failed ones left, re-run after `reextract` doesn't download again.

## Agreed
- Markdown links rewritten to local copies when saved; failed images keep the original; HTML untouched.

- Stored in the item's folder, next to its HTML.
- No resizing or converting; images stored as served.

## Out of scope
- Image uploads, image items (iteration after next).
- Playwright and screenshots (next).
- Resizing, thumbnails, format conversion.
- The fetch log.

## Review round 1
- Compared trafilatura with Crawl4AI and Readability on the saved articles; trafilatura stays (results in Claude Notes).
- Fix two trafilatura defects in the saved markdown: an article saved twice (The Machines), and `<sup>`/`<sub>` left as raw HTML tags.
- Art Nouveau's missing images stay a known gap for now.

---

## Claude Notes
- Code: `apps/items/images.py` (tidying, download, swap). `fetch.extract` tidies before extraction; `tasks.save_images` runs after a fetch, on the default queue.
- Tidying uses trafilatura's own HTML loader (same encoding detection as extraction), then lxml. srcset split on a comma followed by whitespace, because Substack URLs contain commas. An `x` descriptor counts as 800 px per x.
- trafilatura drops images when its fallback extractor wins. It compares its own result with a readability-style fallback and keeps the better text; the fallback has no images. Art Nouveau: 34,000 characters with the fallback, 1,100 without (with `fast=True`, images survive but most of the text is lost). So the fallback stays on, and that article has no images. Its 26 `<img>` include 13 figures in the article.
- Tidying changed no image counts on the 10 saved articles. What it changes is which file is saved: the srcset candidate near 1600 px instead of the small default `src`.
- `ItemSource.url` for images is the URL as written in the markdown, the key for the swap. The HTML source's `url` is still the final URL after redirects.
- Filenames: the URL's last path segment (decoded) slugified, plus the first 8 characters of the sha256 and an extension from the mime type. Content in the name, so responses are cached as immutable.
- An image source whose file is missing is downloaded again.
- The same URL used twice in an article (including as a link around the image) is swapped everywhere.
- Images that drop out of a re-extracted article stay on disk until the item is deleted.
- The sources endpoint serves `image` sources only; the saved HTML isn't served, as it would run scripts on our origin.
- Formatting `apps/items` with ruff also rewrites the old migrations 0001 and 0003; those were restored, and only changed files are formatted.
- Dev data: `reextract` over 10 items with saved HTML (1 without), then `save_images` for each. 13 images saved across 4 articles, 0 failed. Unauthenticated request to an image: 401.
- Round 1, extractor comparison (throwaway container, no network, saved HTML; outputs kept locally in `tmp/bakeoff`, not committed):
  - Crawl4AI fit markdown: no images in any article. Raw markdown: the whole page, menus, ads and icons (47 images on Terence Eden's post).
  - Readability (readability-lxml + markdownify): cleanest Art Nouveau with 6 figures, but lost over half of Terence Eden's post and parts of two others. Drops Substack's section headings: its "unlikely candidates" rule removes elements whose class contains `header` (`header-anchor-post`). Hard-coded, no parameter; removing heading classes first brings them back (0 → 5).
  - trafilatura: best text on 9 of 10.
- Round 1, cleanup (`apps/items/cleanup.py`, run in `extract`):
  - Repeats: a block of 80+ characters is dropped when 80% of its 8-word runs appeared earlier. The Machines' second copy is split into paragraphs differently, so exact matching missed most of it. The Machines: 7,211 → 4,392 words. Applied to the plain text too (by line), which the tagger reads.
  - Also dropped: a pull-quote on Terence Eden's post that repeats a sentence of the reply above it word for word.
  - `<sup>`/`<sub>`: digits and `+-=()` become Unicode superscript/subscript; a footnote link keeps its link (`[¹](…)`); anything else becomes plain text (`19<sup>th</sup>` → `19th`). Raw HTML stays unrendered in the reading view.
  - Dev data re-extracted; the image jobs swapped links again without downloading.
