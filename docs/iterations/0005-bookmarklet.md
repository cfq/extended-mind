# 0005 - Bookmarklet

Saving the page I'm on with one click, from the bookmarks bar, and from iOS.

## Decisions
  - Bookmarklet opens a small popup on our own origin
    - `/save?url=<page URL>`
    - popup is same-origin, so the session cookie does the auth
    - no API token in the bookmark, no CORS, nothing injected into the page
  - `/save`
    - saves straight away, no confirm step
    - shows Saving… → Saved, then closes itself
    - on failure stays open and shows the error
    - no header, it's a popup
  - Not logged in
    - popup shows the login form
    - after login, carries on to the save
    - login now returns to wherever you were headed, for every page
  - Getting the bookmarklet
    - on `/add`, under the form
    - a link to drag to the bookmarks bar
    - built from the origin the app is served on, so it works wherever it's deployed
  - Same URL saved twice is two items, as in 0003
  - Token scopes or expiry
    - for the iOS Shortcut and scripts: save without opening a browser
    - `Authorization: Bearer em_…`, works on the items API
    - named, many per user, revocable
    - shown once on creation, only a hash stored
    - `/settings` page: create, copy, list, revoke; link in header
    - a token can't manage tokens: session only

## Backend
  - Model `ApiToken` in `apps/users`
    - `user`, `name`, `hint` (first 8 chars of the key), `key_hash` (SHA-256, unique), `created_at`, `last_used_at`
  - `TokenAuth`: Ninja `HttpBearer`; items router takes token or session
  - `GET /api/v1/tokens`, `POST /api/v1/tokens` (returns the key once), `DELETE /api/v1/tokens/{id}`
  - Admin: list and delete only

## Frontend
  - `lib/bookmarklet.ts`: builds the `javascript:` URL
  - `pages/Save.tsx`: the popup
  - `RequireAuth` passes the location to `/login`; `Login` goes back to it
  - `pages/Settings.tsx`: tokens

## Tests
  - Bookmarklet
    - is a `javascript:` URL, no spaces
    - opens `/save` on our origin, in one popup
    - page URL survives intact: query strings, fragments, spaces, unicode, nested URLs
  - SPA catch-all serves `/save`, `/settings`
  - Tokens
    - only a hash stored, keys unique
    - create (name required), list own without keys, delete own; others' → 404
    - token endpoints refuse bearer auth
    - items create/list/detail with a token, no CSRF needed, own items only
    - `last_used_at` updated
    - unknown, empty, wrong scheme, deleted, inactive user → 401
    - session without CSRF still rejected

## Out of Scope
  - API tokens
  - Sending title, selection or page HTML with the save
  - Browser extension, mobile share sheet
  - Tags or notes at save time
  - Sites whose CSP blocks bookmarklets

---

## Claude Notes

Written and built in one go at cfq's request; everything above is a proposal until reviewed.

Small decisions:
- Popup is `420x260`, window name `extended-mind`: a second click reuses the popup.
- Popup closes 800 ms after saving.
- `href` is set on the element, not in JSX: React refuses `javascript:` URLs.
- `/save` saves once under StrictMode's double effect (ref guard).
- Frontend tests use Node's built-in runner (`node --test`), which runs TypeScript as is: no new dependencies. 0004 left frontend tests out; this is the smallest way in. Vitest still open.
- `make test` runs both; `make test-backend` and `make test-frontend` run one each.
- Key: `em_` + 32 random bytes, url-safe base64. Plain SHA-256 is enough for random keys; no salt or slow hash.
- Wrong bearer token → 401 "Invalid or revoked token.", instead of falling through to session auth and failing CSRF with a 403.
- `last_used_at` written on every token request.
- Test files excluded from `tsconfig.json`: they import `node:` modules and we have no `@types/node`.

Not covered:
- `Save.tsx` and the login return have no tests: they need a DOM, which means new dependencies.
- The popup was not clicked through in a browser. The dev database has no user I can log in as.
- No real token used against the running app: ROE says no creating credentials. Checked bad and missing tokens only.

Found on the way:
- `make lint` fails on `main`: 21 ruff errors and 5 unformatted files, in migrations and 0004 tests. Not touched here.
