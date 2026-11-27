# 0022 - Backend layout

## Asked
- Tidy `apps/items`: proposal A. Subpackages inside `items`; models stay, no migrations, no behaviour change.

## Extrapolated
- Tests mirror the folders.

## Plan
```
items/
  models.py admin.py api.py schemas.py tasks.py ids.py
  pipeline/
    steps.py           # was steps.py
    flow.py            # the pass and single steps, from fetch.py
    download.py        # HTTP download, clean_url, FetchError, from fetch.py
    browser.py         # was browser.py
    extract.py         # trafilatura extraction (fetch.py) + cleanup.py + meta.py
    article_images.py  # was images.py
    originals.py       # was image_items.py
    sources.py         # was sources.py, + local_url and image_filename
  tagging/
    rules.py           # was tagging.py
    model.py           # was autotag.py
```

### Tests
```
tests/
  test_api.py test_ids.py test_item_types.py test_migrations.py
  test_reextract.py test_retry.py test_tasks.py
  pipeline/
    test_download.py       # clean_url, download (from test_fetch.py)
    test_flow.py           # fetch passes (rest of test_fetch.py)
    test_browser.py
    test_extract.py        # test_cleanup.py + test_meta.py
    test_article_images.py # was test_images.py
  tagging/
    test_rules.py          # was test_tagging.py
    test_model.py          # was test_autotag.py
```

---

## Claude Notes
- Pure move: no behaviour change, no migration. Same test count before and after (265 passed, 4 live skipped).
- `git mv` for every moved file, so history follows: `fetch.py` → `pipeline/flow.py` (then `download.py` and the extraction part split out), `cleanup.py` → `pipeline/extract.py` (then `meta.py` and the HTML tidying from `images.py` merged in).
- Where the tree needed a call:
  - `FetchError` lives in `download.py`: `extract.py` and `flow.py` both raise it, and `download.py` imports neither.
  - HTML tidying (`tidy_html`, srcset, lazy images) moved from `images.py` to `extract.py`: it's preparation for extraction, and it breaks an import cycle (`article_images` needs `extract` for the sharing image URL).
  - `local_url` and `image_filename` moved to `sources.py`: both article images and originals use them.
  - Renamed in the merge: `meta.parse` → `extract.parse_meta`, `meta.image_url` → `extract.sharing_image_url`.
  - `flow` calls `download.download(...)` through the module, so tests patch `download.download`.
  - Callers import `tagging.rules as tagging` and `tagging.model as autotag`, so call sites read as before.
  - `tasks.py`, `steps` retry map and the management commands stay where they were; only imports changed.
- Checked on dev: a new save went through every step; a step retry was accepted (202). Live browser tests pass from the worker.
