# 0020 - Item types and uploads

## Asked
- Items get types: a common `Item`, with `PageItem` and `ImageItem` one-to-one.
- The pipeline records what it does per item: `Item` → `ItemStep` → `ItemStepRun`, so it's clear where and which bits fail.
- Image uploads, and image URLs saved as image items.
- Images in the item list: image items and articles. Aspect ratio kept, max width 150px. A card redesign comes later.
- One iteration.

## Extrapolated
- Article list image: the sharing image (`og_image`), else the head screenshot, else none.
- Steps and runs are backend only; the UI comes next iteration.

## Plan
### Item
- Common: `id`, `user`, `type`, `url`, `url_submitted`, `found_on`, `site_name`, `title`, `description`, `published_at`, `created_at`, `fetched_at`.
- `type`: `page` / `image`; blank until the fetch decides. No typed section in the API until then.
- `url`: the item's own address (page, or image file), what gets fetched. Blank for uploads.
- `found_on`: nullable URL. Where it was seen when that isn't `url`: an upload's page. Set from the upload form/API.
- Dropped: `status`, `error` columns.
- Default manager joins `page` and `image`; `item.detail` returns the typed row.

### PageItem
- `item` (one-to-one, primary key, `related_name="page"`), `author`, `meta`, `text`, `markdown`.

### ImageItem
- `item` (one-to-one, primary key, `related_name="image"`), `width`, `height`, `text` (OCR later; empty now).
- The file: `ItemSource` kind `original`.

### Text
- Each type keeps its own text. Tagger and search read through the type: `item.detail.search_text()`.
- Tagger: pages only, as now (images have no text yet).

### Steps and runs
- `ItemStep`: `item`, `name`, `position`, `created_at`. Unique `(item, name)`. Created `pending` the moment the pipeline knows it's needed.
- `ItemStepRun`: `step`, `run_id` (one UUID per pass), `outcome` (`ok`, `failed`, `skipped`, `blocked`, `no_content`), `started_at`, `finished_at`, `message`, `meta` (jsonb).
- Step state: no runs → `pending`; otherwise the latest run's outcome.
- One helper runs a step: creates/gets the step, writes the run with timings, outcome and message, catches the exception.
- `ItemSource.run`: nullable FK to the step run that produced the file.
- Steps, in code:
  - Every saved URL: `fetch_http` (incl. redirects), then by content type:
    - Image → `ImageItem`, `save_original`, `dimensions`.
    - HTML → `PageItem`, `fetch_browser` (screenshots, PDF inside it as today), `extract`, `images`, `og_image`, `tag`.
  - Upload: `save_original`, `dimensions`.
- `FetchAttempt` dropped. Its HTTP status and method go to the run's `meta`.

### Item status
- Derived by a helper, not stored: same values as now (`pending`, `fetching`, `done`, `failed`).
  - Any step pending or running → `fetching` (`pending` if no step has run).
  - A required step failed → `failed`, with its latest run's message as the error.
  - Otherwise `done`.
- Required: `fetch_http`/`fetch_browser` (one must succeed) and `extract` for pages; `save_original` for images.
- API keeps `status` and `error` fields, filled by the helper. Lists annotate it in the query.

### Uploads
- `POST /api/v1/items/images`, multipart: one or more `file`, optional `found_on`. One item per file; returns them. Token and session auth.
- JPEG, PNG, GIF, WebP, checked by content. 50 MB per file. No HEIC.
- No dedupe: every upload is a new item.
- Title: the file name without extension.
- Steps run in the background job, like a URL save.

### Image URLs
- A saved URL whose content type is an image becomes an image item: the downloaded file is its `original`.

### Retry
- `POST /items/{id}/retry` stays: runs the whole pipeline again as a new pass.
- The retry button leaves the item page for now.

### Frontend
- Add page: file picker (multiple) and drag and drop, optional "found on" URL.
- Item page for images: the image, dimensions, size, type, found on.
- List: an image per item, aspect ratio kept, max width 150px. Image items: the original. Pages: sharing image, else head screenshot.
- API types: `type`, `found_on`, `page`/`image` sections.

### Migration
- Add `type`, `found_on`; create `PageItem`, `ImageItem`, `ItemStep`, `ItemStepRun`.
- Every existing item → `PageItem` with `author`, `meta`, `text`, `markdown`; `type="page"`.
- Drop `status`, `error`, and those page columns from `Item`; drop `FetchAttempt`.
- After merge, on dev: retry all URL items so they get steps and runs. Prod: cfq decides.

### Dependencies (ask)
- Pillow: image dimensions, and content checks on upload. Also needed later for EXIF, OCR prep, HEIC.

### Deployment
- nginx `client_max_body_size 50m` on both sites (cfq).

### Tests
- Models and migration: existing items become pages with their fields.
- Pipeline: steps and runs per path (page, blocked page, image URL, upload); failure in an optional step leaves the item `done`; failure in a required one makes it `failed` with the message.
- Status helper on single items and lists.
- Uploads: types, size limit, multiple files, `found_on`, auth.
- API: typed sections, list images.
- Retry: new pass, new `run_id`, same steps.

---

## Claude Notes
- Explored: abstract base (no shared table: unions, generic FKs), multi-table inheritance (awkward to add the child after the fetch decides the type), `django-polymorphic`. One-to-one picked: shared table for lists, tags, projects; the typed row added once the type is known.
- `error` as a pointer to the last failed attempt dropped: set/unset bookkeeping, one failure only. Failures come from the latest run of each step.
- Step state from runs, not stored. `DISTINCT ON (step)` for one item, `Exists` + subquery for lists. A stored latest outcome on the step can come later if needed.
- Debug files for intermediate steps: later.
- Text stays per type: search may become per-type (multimodal, object detection), so no shared `Item.text`.
- Built as planned, with these decisions:
  - Status: computed in Python from prefetched steps and runs (`steps.status`), not a SQL annotation. Lists prefetch `steps__runs`: a fixed number of queries per list.
  - Runs are written as they start (`running`) and updated when they finish, so a pass in progress shows as `fetching`. A worker killed mid-step leaves a `running` run: the item stays `fetching` until a retry.
  - Core steps (decide `fetching`): `fetch_http`, `fetch_browser`, `extract`, `save_original`. Required for `done`: `extract` (page), `save_original` (image). Everything else is optional.
  - Error: the latest problem run's message (`failed`, `blocked`, `no_content`).
  - `extract` gets a run per candidate tried: plain HTML, then rendered.
  - A URL that's neither HTML nor a supported image (e.g. a PDF) now fails: "Not a page or an image: application/pdf." Before, it was `done` with nothing saved.
  - Image URLs: title from the file name in the URL; `save_original` checks the content with Pillow, so a mislabelled response fails there.
  - Steps added when known: `images`, `og_image`, `tag` only after extraction succeeds, so a failed page doesn't keep pending extras.
  - `images` ends ok with "N failed." and the failed URLs in `meta`. `og_image` is `skipped` when the page has none. `tag` is `skipped` with no model configured.
  - Uploads: every file is checked before any is saved; one bad file rejects the request. `save_original` runs in the request (the file is there); `dimensions` in a `process_upload` job. Retry on an upload re-reads dimensions.
  - Migration: existing items become pages; their old status becomes an `extract` step with one run (`done` → ok, `failed` → failed with the old error), so statuses survive. Old pending items stay pending.
  - Test fixtures carry the same `extract` step and run.
  - `ItemSource.run` set for HTML (fetch_http), rendered, screenshots, PDF (fetch_browser), article and sharing images, originals.
  - `make lock` added Pillow 13.0.0.
- Checked on dev: upload (640×480 PNG, found on), image URL (Wikimedia PNG, 800×600), page (Asterisk: browser, extract, tag, images, og_image; thumbnail is the sharing image). The Asterisk article has no images in its markdown: trafilatura drops its figures, as before this change.
