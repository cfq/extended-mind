0004 - Testing 

Initialisig some testing. It's unit testing for now and will cover the current scope of iterations 0001-0003. 

## Scope

### 0001 Setup
- `GET /api/v1/health` returns ok (exists).
- `ping` task runs.

### 0002 User signup
- User model
  - Email lowercased on save.
  - Email and username unique.
  - Email is the login field.
- `POST /auth/signup`
  - Creates user, 201.
  - `SIGNUP_ENABLED=false` → 403.
  - Duplicate email / username → 400.
  - Invalid email, weak password (Django defaults) → 400.
- `POST /auth/login`
  - Correct credentials → 200, session set.
  - Email case-insensitive.
  - Wrong password / unknown email → 401.
- `POST /auth/logout` → 204, session cleared.
- `GET /auth/session` → user when logged in, 401 when not.
- `GET /auth/csrf` sets the `csrftoken` cookie.
- `GET /users/{username}`
  - Login required.
  - Unknown → 404.
- CSRF enforced on authenticated POSTs (one test with CSRF checks on).
- SPA catch-all
  - Serves `index.html` for app routes.
  - 404 when no build present.
  - Doesn't swallow `/api`, `/admin`, `/static`.

### 0003 Saving content
- `ids`: base62 round-trip, fixed 22-char length, invalid input → `None`.
- `clean_url`: strips `utm_*`, `fbclid` etc., keeps other params.
- `source_filename`: title → description → URL fallback, 60-char cap, short ID suffix.
- Items API
  - Create: valid URL → 201, `pending`, task deferred; invalid / non-http → 400.
  - `url_submitted` kept as entered, `url` cleaned.
  - List: own items only, newest first.
  - Detail: own → 200; other user's, unknown, malformed ID → 404.
  - Retry: resets to `pending`, clears error, task deferred.
  - Delete: 204, row and folder gone.
  - All endpoints require login.
- `download`
  - Follows redirects, returns final URL.
  - Non-HTML → no body.
  - Over 50 MB → error.
  - HTTP errors raise.
- `fetch`
  - HTML → `done`, markdown, text, title, description, `ItemSource` row + file (size, sha256).
  - Non-HTML → `done`, no file.
  - No article content → error.
  - Retry replaces the old HTML file and row.
- `fetch_item` task
  - `pending` → `fetching` → `done`.
  - Failure → `failed` with error message, job re-raises.

## Strategy
- pytest + pytest-django; tests in each app's `tests/` folder, shared fixtures in `backend/conftest.py`.
- Real Postgres test database (the Compose `db`); Django creates and drops it.
- API tests through Django's test client, `force_login` for auth.
- Mocks
  - No real network, ever.
  - `download` tested against httpx2's mock transport.
  - `fetch` tested with `download` patched to return fixture HTML.
  - Procrastinate's in-memory connector: assert jobs deferred, no worker process.
  - Task functions called directly.
- Files: `ITEM_SOURCES_DIR` pointed at pytest's `tmp_path`.
- Trafilatura not mocked: runs for real on small fixture HTML files, offline and deterministic.
- Test data: plain fixtures/helpers, no factory library.

## Boundaries
- In: our code's behaviour, at function and API level.
- Out
  - Frontend tests.
  - End-to-end / browser tests.
  - Library internals: Django auth, trafilatura extraction quality, courlan beyond our param list.
  - Admin.
  - Docker, Compose, Makefile.
  - CI (still later).
  - Performance.

## Open questions
- Coverage report (`pytest-cov`, new dev dependency) or not?
- Fixture HTML: small hand-written pages, or trimmed real pages saved from the web?
- `factory_boy` instead of plain helpers? Only worth it once models grow.
- Frontend tests (Vitest) out for now: agree?

---

## Claude Notes

Built with defaults for the open questions: no coverage, real pages as fixtures, plain helpers, no frontend tests.

Fixtures:
- `apps/users/fixtures/test_users.json`: `test` (pk 2, owns the items) and `other` (pk 3). Password `testpass123`.
- `apps/items/fixtures/test_items.json`: dump of the 5 saved articles + their sources.
- `apps/items/fixtures/item_sources/`: their raw HTML, copied into `tmp_path` per test.

Small decisions:
- Shared fixtures in `backend/conftest.py`: `data`, `user`, `other_user`, `user_client`, `item`, `item_sources_dir`, `fixture_html`, `app` (in-memory Procrastinate).
- `download` tested by swapping `httpx2.Client` for one with a `MockTransport`; no code change for testability.
- Size limit tested by lowering `MAX_BYTES`, not by sending 50 MB.
- Logins use the fixture's real 1.5M-iteration hash: a few slow tests. Faster hasher in test settings if it bites.
