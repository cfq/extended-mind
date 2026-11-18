# Scrapers research

How open source save/archive apps fetch and extract content. Read from source, 2026-11-18.

## Karakeep
- Fetch:
  - Plain HTTP probe first (30s, 2 MB cap) for content type; PDF/image become asset bookmarks.
  - HTML via Chrome with patchright (Playwright fork).
  - Doesn't launch Chrome: connects to an external Chrome (CDP) or browserless.
  - No browser configured: plain fetch.
- Anti-bot:
  - Ghostery adblocker, autoconsent for cookie banners, cookie file.
  - Waits up to 15s for challenge pages to clear (`waitForChallengeToClear`).
  - No stealth plugin.
- Extraction:
  - Separate subprocess with memory and time limits.
  - metascraper with custom Reddit and Amazon plugins.
  - Defuddle for readable content (unverified).
  - Flags challenge pages as not readable.
  - Readable HTML inline in the DB, or as an asset above a size threshold.
- Archiving:
  - Screenshot (on by default), PDF (off).
  - Full-page archive via `monolith` (off).
  - Banner image download.
  - Video via `yt-dlp` with size cap and timeout.
- Extension: SingleFile capture uploaded as a precrawled archive; rendered offline with JS off and requests blocked; no live fetch.
- Failures:
  - Queue retries, per-domain rate limit, then `crawlStatus = failure`.
  - Best-effort steps (screenshot, PDF, archive) log and skip.
- Post-processing: AI tagging/summaries (OpenAI/Ollama), Tesseract OCR, Meilisearch, embeddings.
- SSRF checks on every request and redirect.
- Code: `apps/workers/workers/crawlerWorker.ts`, `crawler/localCrawler.ts`, `utils/browser.ts`, `video/localVideoDownloader.ts`.

## Linkwarden
- Playwright: launches Chromium or connects to remote via CDP. Desktop Chrome device preset.
- Header check first; images and PDFs handled separately.
- Readable: `@mozilla/readability` + jsdom + DOMPurify, stored as JSON; text in DB.
- Archives per link:
  - Full-page JPEG screenshot (after autoscroll)
  - PDF
  - `monolith` single-file HTML
- Optional Wayback Machine submission.
- Failures: missing artifacts set to `"unavailable"`; monolith errors don't fail the link.
- Code: `apps/worker/lib/archiveHandler.ts`, `lib/browser.ts`, `lib/preservationScheme/`.

## ArchiveBox
- Plugin-based extractors, ordered by numeric prefix:
  - title, SingleFile, readability, mercury
  - wget/WARC, screenshot, PDF, DOM
  - yt-dlp, git, archive.org, favicon, headers
- Per-plugin config: `{PLUGIN}_ENABLED`, `{PLUGIN}_TIMEOUT`, `{PLUGIN}_BINARY`.
- `ArchiveResult` row per extractor run:
  - plugin, status (succeeded / failed / skipped / noresults), outputs, start/end
  - linked `Process` with exit code
- Logins via Chrome user data dir ("personas"). Configurable user agent.
- Outputs are plain files per snapshot.

## Wallabag
- Plain HTTP via graby (php-readability + ftr-site-config).
- ftr-site-config: ~4,000 per-site text files.
  - XPath for `body`, `title`, `author`, `date`.
  - `strip`, `strip_id_or_class`, `find_string`/`replace_string`.
  - `http_header(...)`, e.g. Medium fetched with a crawler UA.
  - Lookup: exact host, wildcard, HTML fingerprint (e.g. WordPress/Blogger generator), global, default.
- Extraction order: site rules, then hNews/Instapaper/schema.org heuristics, then Readability.
- Fixes lazy-load image attributes.
- Images downloaded by `DownloadImages.php`: re-encoded, SVG sanitised, original `src` kept on failure.
- Failure: never throws; stores an error message and flags the entry not parsed.
- Accepts client-sent HTML and skips fetching.

## Readeck
- go-readability fork (Readability.js 0.6 compatible).
- JS content scripts per site (HN, Reddit, YouTube, Substack, Bluesky, Fediverse…); overridable.
- Each bookmark is one immutable ZIP: HTML and images.
- YouTube embeds kept as thumbnail links; transcripts saved.
- Per-bookmark diagnosis panel with the extraction log.
- Extension can send content and resources (multipart).
- Internals unverified: only README, go.mod and changelog read.

## Omnivore
- Puppeteer content-fetch service; own Readability fork.
- ~20 per-site handlers: Twitter, YouTube, Medium, Wikipedia, TikTok, Bloomberg, Substack and others.
- Per-domain failure counter in Redis; 24h fetch cache.
- Original HTML uploaded to storage before processing.
- Extension sends page content (`originalContent`) with the URL.

## Takeaways for us
- Client-sent HTML is the standard fix for bot walls (Karakeep, Wallabag, Omnivore). SingleFile capture is the strongest form.
- Playwright fallback: separate Chrome/browserless container, worker connects remotely. Fits Compose.
- Failure log: ArchiveBox's `ArchiveResult` pattern, one row per attempt/step.
- Save raw HTML before extracting (Omnivore). Closes the `no_content` gap.
- Per-site rules: ftr-site-config is reusable, with trafilatura as fallback.
- Social: little prior art beyond `yt-dlp`. Omnivore's handlers are the main reference; `gallery-dl`/`instaloader` are unexplored.
- Already aligned: trafilatura ≈ Readability/Defuddle; Procrastinate covers retries; screenshots and `monolith` archives match the spec.
