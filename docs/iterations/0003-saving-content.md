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
    - `user`, `url`, 
    - `status` (`pending` | `fetching` | `done` | `failed`), 
    - `error`, 
    - `title`, `description`, 
    - `text` for extracted text, `markdown` for md
    - `created_at`, `fetched_at`.
  - API: `POST /api/v1/items`, `GET /api/v1/items`, `GET /api/v1/items/{id}`. 
    - Own items only.
    - Others' items return 404
- Task `fetch_item(item_id)`: fetch, extract, save, update status. Deferred on create.


## Extractor
  - trafilatura 
    - extract(html, url=input_url, output_format="markdown", include_links=True, include_formatting=True, include_images=True)
    - we'll deal with downloading images and replacing those links later
    - extract text as well, and store both under `markdown` and `text` columns. Text for search.
    - save original HTML too under `body`
  - react-markdown renders on front-end.
  - description, metadata, etc handled by trafilatura
  - httpx2 
    

## Out of Scope
  - Inbox
  - Streaming of changes in status to the front-end
    - No polling, events or streaming yet. Changes visible on update
  - Article images
    - We'll do it together with image item saves
  - JS-only pages (no body via plain HTTP): fail for now, Playwright later

---

## Claude Notes

Proposed:
- `ItemSource` model, one row per file on disk:
  - `item` (FK), `kind` (`html`, `image`, …), `filename`, `mime`, `size`, `sha256`, `created_at`.
- Files in `${DATA_DIR}/item_sources/{item_uuid}/`, e.g. `raw.html`. Images, snapshots later.
  - Deleting an item deletes its folder.
  - No dedup across items.
  - New bind mount for app + worker.
- Raw HTML on disk only, not in the DB.
  - Conflicts with "save original HTML too under `body`" in Extractor. Drop that line?
- URLs: UUID base62-encoded (22 chars), e.g. `/item/1BvXqz8Rk2mN4pLwT6yHcE`. Or the plain UUID?
- No nh3: react-markdown doesn't render raw HTML. Never add `rehype-raw`.
- URL cleanup: strip `utm_*`, `fbclid`, `gclid` and similar before saving. Keep the original as submitted?
