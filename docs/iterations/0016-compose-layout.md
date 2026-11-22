# 0016 - Compose layout

## Asked
- Move the Compose files out of the repo root, under `docker/`.
- Base file neutral: only what dev and prod share.
- Make targets named per stack: `dev-*` like `prod-*`.
- Dev and prod with their own project and image names, browser included.
- `make ollama-down`; `make ollama` renamed `ollama-up`.
- `make dev-up` starts Ollama, like `prod-up`.

## Extrapolated
- Makefile passes `--project-directory .` so `.env.*` and `./data` still resolve from the root.
- Allowlist in `.claude/settings.json`, comments and the deployment spec follow the renames.

## Changes
### Files
- `compose.yaml` → `docker/compose.yaml`
- `compose.dev.yaml` → `docker/dev.yaml`
- `compose.prod.yaml` → `docker/prod.yaml`
- `compose.ollama.yaml` → `docker/ollama.yaml`

### Neutral base
- `docker/compose.yaml` sets no project name, images or data paths.
- Each overlay sets its project name, images, env file, data paths, ports.

### Names
| | Dev | Prod |
|---|---|---|
| Project | `extended-mind-dev` | `extended-mind-prod` |
| App image | `extended-mind-dev` | `extended-mind-prod` |
| Browser image | `extended-mind-dev-browser` | `extended-mind-prod-browser` |

### Make targets
- `build`, `up`, `down`, `logs`, `createsuperuser` → `dev-build`, `dev-up`, `dev-down`, `dev-logs`, `dev-createsuperuser`.
- `COMPOSE` variable → `DEV`.
- `ollama` → `ollama-up`; new `ollama-down`.
- `dev-up` depends on `ollama-up`.
- `nuke*` scoped to project `extended-mind-dev` and images `extended-mind-dev*`.
- Unchanged: `install`, `test*`, `lint`, `format`, `shell`, `migrate`, `makemigrations`, `ping`, `vite`, `npm`, `lock`.

### Cutover
- Old project `extended-mind` and images `extended-mind`, `extended-mind-browser` removed by hand.
- Data in bind mounts under `data/`, unaffected.

---

## Claude Notes
- Prod and dev shared the `extended-mind-browser` tag. A dev build retagged it, so the next `prod-up` would run a browser from whatever branch dev was on. Breaks once Playwright is bumped on a branch: server and client versions must match.
- Neutral base: a data mount added to the base used to land in prod with a dev path unless `prod.yaml` overrode it. Now a forgotten mount is missing, not wrong.
- `docker compose config` compared before and after each step:
  - Move: identical for dev, prod and Ollama.
  - Neutral base: same mounts; dev `migrate` now also mounts `data/dev/item_sources` through the `x-dev` anchor. Harmless; avoiding it means listing volumes per service.
  - Names: only project, image and network names differ.
- `ollama-down` fails while a stack's tagger is attached to the `ollama` network; noted in the Makefile.
- `nuke-images` filters with `--filter reference=` so the wildcard matches.
- `TODO.md` still says `make up` and `make createsuperuser`; left for cfq.
