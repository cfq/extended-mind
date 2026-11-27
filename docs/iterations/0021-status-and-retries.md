# 0021 - Status and retries

## Asked
- Settings, under Log out: a new section with a table of the last 20 items. Moves to its own place later.
- Columns: title | very small image if there is one, else the URL | badges.
- A badge per step, with its state, in the style of GitHub build badges (badgen.net).
- Any item can be retried by clicking, even a successful one: clicking a badge retries that step.
- Retry uses the step logic in `steps.py`: a step and what depends on it.

## Extrapolated
- Badges drawn in CSS, no requests to badgen.net.
- The table refreshes while any step is pending or running.

## Plan
### API
- `GET /api/v1/items/activity?limit=20`: newest items with their steps, each step `{name, state, message, finished_at}`.
- `POST /api/v1/items/{id}/steps/{name}/retry`: queues the retry, returns the item's steps. Refused (409) while the step or one that depends on it is queued or running.

### Step definition
- `steps.STEPS`: a dict of `Step(depends_on, core, required_for, queue)`, in pipeline order.
- Read by: status (`CORE`, `REQUIRED`), retry (`dependents()`), display order (`ordered()`).
- The normal pipeline keeps its flow; a graph-driven runner can come later.

### Retry logic
- From `steps.STEPS`: each step's downstream steps. Retrying a step runs it and everything after it, in order, as one new pass (`run_id`).
  - `fetch_http` → everything (the existing item retry).
  - `fetch_browser` → new visit (rendered, screenshots, PDF), then `extract` → `images`, `og_image`, `tag`.
  - `extract` → from saved HTML (plain, then rendered), then `images`, `og_image`, `tag`.
  - `images`, `og_image`, `tag`, `dimensions` → just that step.
  - `save_original`: image URL → the whole item retry; upload → re-check the stored file, then `dimensions`.
- A `retry_step` job runs them. Each step callable on its own; `extract` from saved HTML shares code with `reextract`.
- The normal pipeline is unchanged; the map drives retries only.

### Badges
- Two parts: step name | state. Colours by state:
  - `ok` green, `failed` red, `blocked` / `no_content` orange, `running` blue, `pending` / `skipped` grey.
- Hover: the latest run's message and time.

### Table
- Title links to the item.
- Image: the list thumbnail, small (e.g. 32px high). No thumbnail: the URL, shortened.
- Badges in step order.

### Tests
- Activity endpoint: own items only, newest first, limit, steps and states.
- Retry: each step's set and order; runs share a new run_id; busy steps refused; other users' items 404.

---

## Claude Notes
- Asked mid-plan for a dict expressing the step relations, reusable elsewhere: `steps.STEPS`, Python rather than YAML so it sits next to the functions. `depends_on` (cfq) rather than `after`.
- `CORE` and `REQUIRED` are now derived from the flags. `ORDER` fixes display for migrated items, whose `extract` step was created first.
- New outcome `queued`: the retry endpoint marks the clicked step queued for the new pass; the step's run takes that row over when it starts. Only the clicked step is queued: it always runs, so nothing is left queued. Dependents keep their old badge until they run.
- Refused while the step or a dependent is queued or running. Pending steps can be retried, so one whose job was lost isn't stuck.
- Retry handlers in `tasks.RETRY`, one per step except `fetch_http` (the whole pass). `tag` is deferred to its own queue; `images` and `og_image` run only once the page is usable. The chain stops at the first step that raises (e.g. extract finding nothing); the job is recorded failed.
- `fetch.browse`, `fetch.extract_saved` and `image_items.recheck` are the steps on their own. `reextract` now uses `extract_saved` too, and adds the page extras' steps like a fetch does.
- Activity: `GET /items/activity?limit=` (max 100), the user's newest items with steps in pipeline order, each with its latest run's message and time.
- Table polls every 3s while any step is pending, queued or running.
- Badges: `<button>`s styled in CSS, badgen colours (label #555; ok #3c1, failed #e43, blocked/no content #f73, queued/running #08c, pending/skipped #9f9f9f). Hover title: message, time, "Retry …". No confirm on click.
- Checked on dev: activity lists the user's items with badges; retry `extract` on a page and `save_original` on an upload → 202 and queued, a second click 409, both finish ok.

