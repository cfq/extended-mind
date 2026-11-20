# 0015 - Hardening

## Asked
- After the Vite exploit and the debug page leak: no dev port public again.
- Two sites behind nginx (configured by cfq, TLS done):
  - `em.cfqs.com`: production, `DEBUG=False`, gunicorn.
  - `dev-em.cfqs.com`: dev, `DEBUG=True`, runserver with reload, behind basic auth.
- Django ports on localhost only; nginx is the only way in.
- Vite on localhost only, not started by default.
- Dev and prod share one Ollama.
- `make install` for a fresh checkout or after a nuke.
- Env files named `.env.dev` and `.env.prod`; no plain `.env`.

## Extrapolated
- Prod runs a built image with no source mounted, so switching branches for dev never touches it. Prod is built from `main`.
- Dev and prod are separate Compose projects: own env file, data, database, secrets, job queues.
- Secure cookies and HSTS whenever `DEBUG` is off.

## Plan
### Ports
- Dev app: `127.0.0.1:8000`. Prod app: `127.0.0.1:8001`. Vite: `127.0.0.1:5173`.
- Vite behind a Compose profile (`vite`); `allowedHosts: true` removed. Reach it with `ssh -L 5173:localhost:5173`.

### Production stack
- `compose.prod.yaml` on top of `compose.yaml`: project `extended-mind-prod`, image `extended-mind-prod`, gunicorn, no bind mounts, no dev dependencies.
- `gunicorn` added to the backend dependencies.
- Env files: `.env.dev` for dev, `.env.prod` for prod (cfq creates both). The Make targets pass the right one to Compose (`--env-file`), and each overlay sets it for its containers.

### Data
- `data/dev/` and `data/prod/` (Postgres, item sources); `data/ollama/` shared. The fresh install starts dev in `data/dev/`.

### Shared Ollama
- `compose.ollama.yaml`, its own project: Ollama and the model pull, on a Docker network named `ollama` (internal).
- Both app stacks' `tagger` joins that network; `OLLAMA_URL` stays `http://ollama:11434`. Ollama leaves the app Compose files.

### Django
- When `DEBUG` is off: `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, HSTS (1 year, no subdomains, no preload).
- `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` already come from the env files.

### Make
- `make install`: Ollama stack up, `npm ci`, build, dev up.
- `make up`/`down`/`logs` keep working for dev; `make vite` starts Vite.
- `make prod-build`, `make prod-up`, `make prod-down`, `make prod-logs`, `make prod-createsuperuser`.

### Spec
- `docs/spec/deployment.md`: dev ports never public; both sites only through nginx; dev behind basic auth.

### Tests
- Settings: secure cookies and HSTS on when `DEBUG` is off, off when on.
- Compose config validates for dev, prod and Ollama; published ports are all on 127.0.0.1.
- Prod stack up locally: gunicorn answers on 127.0.0.1:8001 with `DEBUG=False`.

## Out of scope
- nginx config and certificates (done by cfq).
- Logging out sessions, new API token, new secrets (cfq, with the fresh install).
- Renaming the existing `.env` to `.env.dev` (cfq).
- nginx catch-all for unknown hosts.

## Env files (cfq)
- `.env.dev`: `DEBUG=True`, `ALLOWED_HOSTS=dev-em.cfqs.com,localhost`, `CSRF_TRUSTED_ORIGINS=https://dev-em.cfqs.com`, new random secrets.
- `.env.prod`: `DEBUG=False`, `ALLOWED_HOSTS=em.cfqs.com`, `CSRF_TRUSTED_ORIGINS=https://em.cfqs.com`, its own random secrets.

---

## Claude Notes
- Each overlay sets the env file and data paths itself, so Compose needs no variables: `docker compose -f compose.yaml -f compose.dev.yaml …` works without `--env-file`. The plan said the Make targets would pass `--env-file`; not needed.
- Compose merges volume mounts by container path, so `compose.prod.yaml` replaces the dev data mounts.
- Dev and prod share `extended-mind-browser` (built from the same Dockerfile).
- `make nuke*` still only touches the dev project (`extended-mind` label, `extended-mind` image, `data/dev`). The first nuke after this change needs `DATA_DIR=./data` for the old layout.
- `make npm` and `test-frontend` still work with Vite behind a profile: `docker compose run` starts a profiled service when it's named.
- `.gitignore`: `.env*` except `.env.example`. The template now covers both files; `SIGNUP_ENABLED` defaults to off in it.
- gunicorn 27.0.1, 3 workers, access log to stdout.
- HSTS from Django (`SECURE_HSTS_SECONDS`), not nginx, so it follows `DEBUG`.
- `check --deploy` on prod: three warnings, all by choice: no HSTS subdomains or preload; no `SECURE_SSL_REDIRECT` (nginx redirects).
- nginx (cfq): `em.cfqs.com` and `dev-em.cfqs.com` server blocks, linked in `sites-enabled`; the dev password file needs group `www-data` (nginx reads it per request and answers 500 when it can't).
- Checked on the server:
  - `make install` from scratch after `make nuke` (cfq).
  - Listening: only `127.0.0.1:8000` and `127.0.0.1:8001`.
  - `dev-em.cfqs.com`: 401 without the password, the app with it.
  - `em.cfqs.com`: 200, HSTS, `nosniff`, `X-Frame-Options: DENY`; `/api/v1/auth/session` 401.
  - A forged Host straight to 8001: plain 400, 143 bytes, no debug page.
  - Prod mounts only `data/prod/item_sources`.
- Prod was built from this branch to try it; rebuild from `main` after the merge (`make prod-build && make prod-up`).
