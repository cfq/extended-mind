# 0007 - Header cleanup

## Asked
- Header today: Extended Mind, Add, cfq, Settings, Log out.
- Merge profile, settings and log out; propose what goes where.
- On mobile "Extended Mind" shortens to "EM"; full name on larger screens.

## Plan
- Header: brand, Add, username.
  - Username links to `/settings`.
  - "Settings" and "Log out" leave the header.
- `/settings` becomes the one account page, top to bottom:
  - Account: username (links to the profile page), email
  - API tokens (unchanged)
  - Log out button
- `/user/{username}` profile page stays, unchanged; kept for a later social side. Reached from the username on `/settings`.
- Brand: "EM" at ≤600px wide, "Extended Mind" above. Full name kept for screen readers.

## Out of scope
- Dropdown menus, avatars, editing username or email.

---

## Claude Notes
- Username in the header links to `/settings`; on `/settings` it links on to `/user/{username}`.
- Log out on `/settings` styled as a danger button, at the bottom; still goes through `/logout`.
- Brand switches at 600px: two spans toggled in CSS, `aria-label="Extended Mind"` on the link, `EM` hidden from screen readers.
- No new tests: frontend-only, no DOM test setup. No API change.
