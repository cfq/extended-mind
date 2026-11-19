# 0013 - Plain HTML first, cookie banners

## Asked
- Extract from the plain HTML first; the rendered HTML only when that fails.
- Dismiss cookie banners in the browser, so screenshots aren't covered.
- Then re-extract the Wired article.

## Extrapolated
- Why: sites like Wired send the full article in the plain HTML, then their scripts add a consent dialog and cut the text at the paywall. The rendered page only helps pages built by JavaScript, where the plain HTML has no article.
- Both HTMLs are still saved.

## Plan
### Plain first
- Fetch: extract from the plain HTML; if it has no article (or the plain fetch was blocked), from the rendered HTML.
- `reextract`: same order.

### Cookie banners
- DuckDuckGo's `autoconsent` (MPL-2.0), the library Karakeep uses: rules for hundreds of consent managers. Injected into every page before it loads; it opts out where it can.
- The browser waits briefly for it before the screenshots.

## Out of scope
- Paywalls, logins, Patchright.

---

## Claude Notes
- Plain first, on the 11 saved articles: identical to rendered for 9 (The Machines differs by 14 words). Wired: plain 1,429 words, the full article; rendered 4,309 words, mostly consent dialog text, cut at the paywall ("You've read your last free article").
- A plain fetch whose HTML has no article now logs `no_content` on its `http` attempt, and the rendered page is tried.
- `reextract` tries each item's plain HTML, then its rendered HTML.
- autoconsent 17.4.0 (pinned; it releases daily), its `autoconsent.standalone.js` bundle: built-in rules, starts by itself, opts out by default. Fetched with `npm pack` in a build stage of `docker/Dockerfile`, copied with its licence to `/opt/autoconsent/` in the app image. The worker injects it with `add_init_script` (runs in every frame, before page scripts). `AUTOCONSENT_JS` setting; a missing file skips it.
- Wait: after the challenge check, poll the bundle's messages. Done on `optOutResult` or `autoconsentDone` (then 0.5 s for the banner to animate out); no `popupFound`/`cmpDetected` within 3 s means no banner; at most 10 s. Every browser visit is up to 3 s slower.
- The browser attempt's message says "Cookie banner dismissed." or "Cookie banner not dismissed." when there was one.
- Live tests (from the worker): a OneTrust banner page is dismissed before the screenshots; a page without one reports none.
