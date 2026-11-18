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

## Review round 2
- A tag left with no articles is deleted: when you remove its last link, or delete its last article. Existing empty tags cleaned up once.
- Adding a tag shows the chip at once, greyed; full colour once the server confirms.
- Tags don't reorder while you add or accept; a fresh page load sorts them.

## Review round 3
- iOS zoomed into the tag input and stayed zoomed. Inputs are at least 16px on touch screens.

---

## Claude Notes
- Accepting reuses `POST /items/{id}/tags`: adding a tag already on the item flips its source to `manual` (covered in `test_tagging.py`).
- Suggestion chip is a `<button>` ("Accept suggested tag x"); your tag is a `<Link>`. × stays a separate button in the chip.
- Hover on a suggestion: "Suggested by the model · click to accept" or "From the page · click to accept".
- Backspace in the empty input still removes the last chip; with the new order that's the last suggestion if there is one.
- The reading view underlines links; tag chip links are excluded with a more specific selector.
- `/tag/:slug` reuses the dashboard component. The page title line ("Tagged x · Show all") is unchanged.
- Round 1: `.tag-combo` is `flex: 1 0 100%`, so it wraps to its own line under the chips at any width.
- Round 2:
  - `tagging.delete_unused(user)` runs after a tag removal and an item delete. Migration `0005_delete_unused_tags` cleans existing ones. Removals store names, so a removed suggestion stays removed after its tag is gone.
  - Pending adds come from TanStack Query's `useMutationState` (mutation key `["item-tags", id]`), so several quick adds each show a chip. A failed add drops its chip and shows the error.
  - A pending chip has no ×, isn't a link, and Backspace skips it. An accepted suggestion greys in place, then turns solid.
  - `keepOrder`: the first render uses the sorted order; after that, chips keep their place and new ones go at the end.
- Round 3: iOS Safari zooms into inputs with text under 16px. Under `pointer: coarse`, inputs, textareas and selects get `max(16px, …)`. Not `maximum-scale=1` in the viewport: that blocks pinch zoom on Android.
