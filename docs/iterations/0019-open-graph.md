# 0019 - Open Graph

## Asked
- Save `og:image` and related tags with the item.

## Extrapolated
- "Related tags": the page's `og:*`, `twitter:*` and `article:*` meta tags.
- The image is downloaded and kept, like article images: the remote one rots.

## Plan
### Meta tags
- During extraction, read every `<meta property|name>` starting `og:`, `twitter:` or `article:` from the same HTML the article comes from (plain first, then rendered).
- Store them raw on the item: `Item.meta`, a JSON object, key → value; repeated keys (`article:tag`, several `og:image`) → list.
- Existing fields (title, description, author, site name, date) stay as they are: trafilatura already falls back to OG for those.

### Image
- Image URL: `og:image` (or `og:image:secure_url`), else `twitter:image`. Resolved against the page URL.
- Downloaded in the existing `save_images` job, after the article images; same download code, limits and referer.
- New `ItemSource.Kind.OG_IMAGE`; `url` is the remote image URL. A retry or reextract with the same URL doesn't download again.
- Download failure: logged, item unaffected.

### API
- Item detail: `meta` (the raw object) and `og_image` (local URL or `null`).
- Sources endpoint serves `og_image` like other images.

### Not in this iteration
- UI: no thumbnails, nothing in the reading view. New design later.
- Duplicate check against article images: wait and see.
- Running `reextract` for existing items.
- Deploying to prod after merge.

### Tests
- Meta parsing: property and name attributes, repeated keys, relative image URLs, missing tags.
- Image saved as `og_image`; not downloaded twice; failure leaves the item done.
- API fields.

---

## Claude Notes
- trafilatura's metadata has `image` (from `og:image`/`twitter:image`) and `pagetype` (`og:type`) but drops the rest; parsing the meta tags directly keeps everything.
- Raw JSON over columns: the set of useful tags varies by site, and nothing queries them yet. Columns can come later for what gets used.
- Agreed with cfq: raw JSON field (searchable with Postgres JSON lookups and `jsonb_to_tsvector` later); download the image, no duplicate check; no UI; no reextract; prod stays as is after merge.
- `reextract` would backfill existing items when wanted: it re-extracts from saved HTML and queues `save_images`.
- Meta tags parsed with trafilatura's `load_html`: it detects the encoding of saved bytes the way extraction does (lxml alone read UTF-8 bytes without a charset as Latin-1). It only accepts whole documents, like extraction.
- Lowercased keys; empty `content` skipped; a repeated key with the same value stays a string.
- Image filenames are content-hashed, so a sharing image identical to an article image gets the same file. Two sources then share it:
  - The sources endpoint takes the first match instead of `get_object_or_404`, which would 500 on two rows.
  - Replacing an old sharing image keeps the file if another source uses it.
- `save_images` returns the sharing image in its (saved, failed) counts.
- Real fetches on dev:
  - Asterisk essay: 8 meta tags, `og:image` 1600×900 PNG, 1.2 MB.
  - github.com/microsoft/playwright: 12 meta tags incl. `og:image:alt`, repo card JPEG, 76 KB.
