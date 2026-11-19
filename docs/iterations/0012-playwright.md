# 0012 - Playwright

## Asked
- Fetch pages with a real browser (Playwright).
- Screenshots, PNG:
  - `-full`: the full page, capped at 20,000 px
  - `-head`: 1280×1280 of the top of the page
- Article page: "screenshots: full, head" links in the meta section.
- Every HTML page goes through the browser.
- Save both HTMLs, the plain fetch and the rendered page, to compare.
- A fetch log, separate from the item. Shape left to Claude, agreed in chat.

## Extrapolated
- The plain HTTP fetch stays first: it tells pages from PDFs and images, and is the fallback when the browser fails.
- A page where the plain fetch is blocked still goes to the browser; bot walls often let browsers through.
- Extraction uses the rendered HTML, falling back to the plain HTML.

## Plan
### Browser
- `browser` container: Microsoft's Playwright image plus the matching `playwright` package, running `playwright run-server`. Built from `docker/browser.Dockerfile`.
- Networks: its own internal network shared with the worker, and its own egress network. It can't reach Postgres, Ollama or the app.
- `playwright` Python package in the app, pinned to the server's version (1.65).
- `BROWSER_URL` setting, default `ws://browser:3000/`. Empty: no browser, plain fetch only.

### Fetch
1. HTTP GET, as now. Not HTML: done, as now.
2. HTML, or blocked (401, 403, 429, 503): browser visit.
   - 1280×1280 viewport, desktop Chrome user agent.
   - Load, wait for the network to go quiet, wait up to 15 s for a challenge page to clear.
   - `-head` screenshot.
   - Scroll to the bottom to load lazy content, back to the top, then the `-full` screenshot, cut at 20,000 px.
   - Rendered HTML taken from the DOM.
3. Extract from the rendered HTML; if that fails or there's none, from the plain HTML.

### Files
- Next to the item's HTML, as `ItemSource`, new kinds `rendered`, `screenshot_full`, `screenshot_head`:
  - `{name}.html`: plain fetch (as now)
  - `{name}-rendered.html`
  - `{name}-full.png`, `{name}-head.png`
- A retry replaces each kind.
- `reextract` uses the rendered HTML when there is one.

### Fetch log
- `FetchAttempt`, one row per try: item, method (`http` / `browser`), started, finished, outcome (`ok` / `blocked` / `no_content` / `error`), HTTP status, message.
- A retry adds rows; nothing is overwritten. Kept forever.
- Admin: read-only on each item, and its own list filtered by outcome and method.
- Item statuses unchanged.

### API and frontend
- Item detail gains `screenshots: {full, head}`, each a URL or null.
- The sources endpoint serves screenshots too (not the HTML files).
- Article page, in `reading-meta`: "Screenshots: full, head", linking to the PNGs.

### Tests
- Browser faked in unit tests: flow, fallbacks, files, log rows.
- Against the real `browser` container, skipped when it isn't running: a tall page gives a 1280×20,000 `-full` and a 1280×1280 `-head`.

## Out of scope
- Open Graph image (separate iteration).
- Metadata section rework (next).
- Logins and cookies, cookie banners, ad blocking, stealth.
- PDF export.
- Saving anything for a page whose extraction fails (as now).

---

## Claude Notes
- Code: `apps/items/browser.py` (the visit), `fetch.fetch` (flow and log), `FetchAttempt` model, migration `0006`.
- Browser image: Microsoft's `playwright/python:v1.65.2-noble` has the browsers but not the `playwright` package, so `docker/browser.Dockerfile` adds `playwright==1.65.2` and runs `playwright run-server` as `pwuser`. `init: true`, `shm_size: 1gb` (Chromium uses `/dev/shm`).
- App image: Playwright's Python package runs its bundled Node driver locally even when connecting remotely; it needs `libatomic1`, added to `docker/Dockerfile`.
- Networks: `browser` (internal: worker ↔ browser) and `browser-egress` (browser only). The browser isn't on `egress`, which Ollama shares.
- Visit: fresh context per visit (no cookies between saves), viewport 1280×1280, the plain fetch's desktop Chrome user agent, `en-US`. Load (45 s), network quiet (up to 10 s, often never), challenge check (up to 15 s), `-head`, scroll in 1,000 px steps to the bottom (up to 20,000 px) and back, network quiet again, `-full` clipped to 20,000 px.
- Blocked in the browser: a challenge page that doesn't clear in 15 s, or a last page load of 401/403/429/503. Last, not first: a challenge answers 403, then its script reloads the real page with 200. Challenge pages recognised by title (Just a moment, Attention required, Please wait, Access denied, DDoS-Guard, Security checkpoint) or text (Checking your browser, Verify you are human, Enable JavaScript and cookies to continue). Not Cloudflare's `challenge-platform` script: it's on many normal pages.
- Any Playwright or driver failure becomes `BrowserError`; the fetch logs it and falls back to the plain HTML.
- Plain fetch errors other than blocked (404, DNS, too large) fail the fetch as before; no browser attempt.
- Outcomes: `no_content` is set on the attempt whose HTML was extracted and failed. A fetch that fails still writes its attempts (saved in a `finally`).
- `download()` now returns a named tuple including the HTTP status.
- Screenshot links open in a new tab, like Original.
- Tests: `BROWSER_URL` is empty in all tests unless a test sets it (autouse fixture). Live tests run only where the browser is reachable, i.e. from the worker container: `docker compose run --rm worker pytest apps/items/tests/test_browser.py -k live`. One uses httpbin.org for a real 403, skipped if unreachable.
- Dev data: all 11 items re-fetched.
  - 9 through the browser, 3–18 s each.
  - Undoing the Colonial-Capitalistic Unconscious: the browser gets a challenge that doesn't clear (403); the plain HTML is used.
  - nabeelqu.co: blocked by Vercel's checkpoint in both (429). A first run saved the checkpoint page as the article (the challenge wasn't recognised and the first status was used); fixed, the item reset and re-fetched, now failed as blocked.
  - Screenshot sizes: `-full` 0.4–4.4 MB (about 2 MB typical), `-head` 0.1–1.2 MB. About 2.5 GB a year at 1,000 saves.
