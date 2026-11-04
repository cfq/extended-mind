# 0003 - Saving Content

Saving content, starting with articles, and displaying them. 

## Decisions
  - / is a dashboard
    - shows a list of items
    - on click opens a page for the item
    - before fetch complete, just metadata
    - after fetch complete, displays the article
    - order by date DESC
      - no need for pagination yet
  - /add new page for adding content
    - Link for Add in header
    - Takes in a URL
      - Would be cool to cleanup URL before fetching like tracking codes
    - Adds immediately, there's a status, unfetched yet
    - Worker kicks off, fetches, saves
    - Article body saved to database
    - Raw document fetched can be saved to filesystem
    - Updates status
    - Before completely fetched
      - item description, or preview empty
      - just URL as title
    - After fetched
      - item description show son dashboard
    - Fetch failed, status failed, shows error, can retry
    - Button to delete
  - /item/{id}
    - UUID - uuid.uuid7()
    - Same URL can be saved multiple times, a new fetch each time 


## Backend
  - App `apps/items/`.
  - Model `Item`: 
    - `user`, `url`, `url_submitted` 
    - `status` (`pending` | `fetching` | `done` | `failed`), 
    - `error`, 
    - `title`, `description`, 
    - `text` for extracted text, `markdown` for md
    - `created_at`, `fetched_at`.
  - API: `POST /api/v1/items`, `GET /api/v1/items`, `GET /api/v1/items/{id}`. 
    - Own items only.
    - Others' items return 404
- Task `fetch_item(item_id)`: fetch, extract, save, update status. Deferred on create.
- Retry item download `POST /api/v1/items/{id}/retry`
  - Retry deletes old download, just the file being retried. 
- Delete item `DELETE /api/v1/items/{id}`
- `url` cleaned, final URL after redirects
- `url_submitted` as it was submitted
- Non-HTML URLs (a PDF or image link): just keep the URL, don't download
  - after worker determines, set status to `done`


## Extractor
  - trafilatura 
    - extract(html, url=input_url, output_format="markdown", include_links=True, include_formatting=True, include_images=True)
    - we'll deal with downloading images and replacing those links later
    - extract text as well, and store both under `markdown` and `text` columns. Text for search.
    - raw html on disk
  - react-markdown renders on front-end.
  - description, metadata, etc handled by trafilatura
  - httpx2 
  - URL cleanup: strip `utm_*`, `fbclid`, `gclid` and similar before saving. 
    - use lib `courlan`
    - Keep the original as `url_submitted`.


## Downloads
  - `ItemSource` model, one row per file on disk:
    - `item` (FK), `kind` (`html`, `image`, …), `filename`, `url`, `mime`, `size`, `sha256`, `created_at`.
    - `url`: final URL after redirects
  - Files in `${DATA_DIR}/item_sources/{item_uuid}/`.
    - Deleting an item deletes its folder.
    - No dedup across items.
    - New bind mount for app + worker.
  - Raw HTML on disk only, not in the DB.
    - filename format: slugify(title or desc or url), max 60 chars + last 8-chars of ID
  - URLs: UUID base62-encoded (22 chars), e.g. `/item/1BvXqz8Rk2mN4pLwT6yHcE`
    - hand-write the base62 encode/decode
  - Fetch limits,
    - 60-second timeout, 50 MB maximum, a browser-like user agent.


## Out of Scope
  - Inbox
  - Streaming of changes in status to the front-end
    - No polling, events or streaming yet. Changes visible on update
  - Article images
    - We'll do it together with image item saves
  - JS-only pages (no body via plain HTTP): fail for now, Playwright later

---

## Claude Notes

Small decisions:
- `courlan` added as a direct dependency (already pulled in by trafilatura).
- URL cleanup: courlan `normalize_url(strict=True)` (drops `utm_*`, fragments), plus our own list: `fbclid`, `gclid`, `dclid`, `msclkid`, `igsh`, `si`, `mc_cid`, `mc_eid`.
- Only `http`/`https` URLs accepted on add.
- No article content found → `failed` ("No article content found.").
- Failed jobs re-raise, so Procrastinate records them as failed too.
- Item folder removed via a `post_delete` signal, so admin deletes clean up too.
- `ITEM_SOURCES_DIR` setting, default `/data/item_sources`; bind-mounted from `${DATA_DIR}/item_sources`.
- `make nuke-data` also deletes `item_sources`, since files without DB rows are orphans.
- After add, back to `/`. Delete asks for confirmation.
- `/` no longer says "Welcome {username}"; it's the item list.
