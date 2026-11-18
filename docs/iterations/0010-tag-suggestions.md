# 0010 - Tag suggestions

## Asked
- Accepting and removing tags only on the article page.
- Click a dashed tag: accepts the suggestion, it becomes a real tag.
- Click ×: deletes the tag.
- Click a real tag: goes to that tag's list, like on the dashboard.
- Dashboard tags as now: suggestions dashed, yours solid, click filters. No adding or removing there.
- Tag list at `/tag/slug`, not `/?tag=slug`.

## Extrapolated
- Suggestions are the automatic tags: model and page.
- Accepting makes the tag yours (source `manual`). The API already does this when you add a tag that's on the item, so no backend change.
- × on a suggestion records a removal, as now, so it doesn't come back.

## Plan
### Frontend
- `TagInput` chips:
  - suggestion: a button. Dashed, hover "Suggested by the model/page · click to accept". Click → add it by name.
  - yours: a link to `/tag/slug`.
  - × on both, unchanged.
- Route `/tag/:slug` renders the dashboard filtered to that tag; dashboard tag links point there. "Show all" goes to `/`. `/?tag=` is dropped.
- The API filter stays `GET /items?tag=slug`. Django's SPA catch-all already serves `/tag/...`.
- Suggestions sort after your tags on the article page.

### Tests
- `sourceLabel` and sort order in `tags.test.ts`.
- Backend: an existing test covers model → manual on add. API checked against the running app.

## Out of scope
- Accept all / dismiss all.
- Accepting or removing tags on the dashboard.

## Review round 1
- The add-tag input always sits on its own line. On the iPhone, a new chip appearing beside it moved it, causing misfired taps.

---

## Claude Notes
- Accepting reuses `POST /items/{id}/tags`: adding a tag already on the item flips its source to `manual` (covered in `test_tagging.py`).
- Suggestion chip is a `<button>` ("Accept suggested tag x"); your tag is a `<Link>`. × stays a separate button in the chip.
- Hover on a suggestion: "Suggested by the model · click to accept" or "From the page · click to accept".
- Backspace in the empty input still removes the last chip; with the new order that's the last suggestion if there is one.
- The reading view underlines links; tag chip links are excluded with a more specific selector.
- `/tag/:slug` reuses the dashboard component. The page title line ("Tagged x · Show all") is unchanged.
- Round 1: `.tag-combo` is `flex: 1 0 100%`, so it wraps to its own line under the chips at any width.
