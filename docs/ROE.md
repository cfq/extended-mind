# ROE

Rules change in the files first (CLAUDE.md, SPEC, ROE). Re-read them.

## Roles
- cfq: owns product, writes iterations, approves, merges, also writes when needed.
- Claude: implements, comments. GitHub user `cfq-agent` via `gh`.

## Output
- Bare minimum everywhere: chat, docs, code.
- Decisions are kept in the documents, and Claude reads and comments on them.
- Claude doesn't generate or edit docs unless asked specifically.
- Docs: headings and bullets. No filler.

## Decisions
- Ask first: architecture, dependencies, data model, API/URL shape, UX flows, anything hard to undo.
- Small choices: Claude decides, records them in the iteration's Claude Notes.
- Big enough to change the overall picture: Claude proposes the spec change in Claude Notes; cfq edits the spec.
- Spec is living: it describes current intent. Iterations are the record.
- Unsure: ask.

## Iterations
- `docs/iterations/NNNNN-name.md`, free-form, no front matter, written by cfq.
- Claude adds only at the bottom, under `## Claude Notes`, after a `---` line.
- Branch name = iteration name.
- One iteration at a time.
- No code before cfq approves.

## Commands
- No running, testing or installing. Claude writes the code; cfq runs it.
- Claude gives the commands for cfq to run.
- Read-only commands are only for finding and navigating files.
- `git` and `gh` are allowed for branches, commits, pushes and PRs.
- Never use `git`/`gh` to run anything else (hooks, aliases, `gh api` workarounds, etc.).

## Git
- `main` protected. Branches only. cfq creates branches.
- Only work on the current branch, which is the current iteration md file, which will be the current PR.
- Since it's a shared branch, always pull before acting.
- No rebase or force-push.
- No commit trailers.
- Commit your doc edits alongside your work.
- No secrets committed.
- cfq merges. Claude might be asked to create a PR. 
- Commit messages should follow the format from https://cbea.ms/git-commit/:
  - Separate subject from body with a blank line
  - Limit the subject line to 50 characters
  - Capitalize the subject line
  - Do not end the subject line with a period
  - Use the imperative mood in the subject line
  - Wrap the body at 72 characters
  - Use the body to explain what and why vs. how
