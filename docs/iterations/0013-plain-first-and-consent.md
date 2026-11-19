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
