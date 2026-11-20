# Deployment

## Rules
- No container port is public. Everything is published on `127.0.0.1` only.
- The only way in is nginx on the host (TLS, Let's Encrypt), proxying to those localhost ports.
- Dev is behind basic auth at nginx.
- Secrets never in the repo or the image. Each environment has its own env file and its own secrets.

## Docker
- Everything runs in containers via Docker Compose; the host needs Docker and nginx.
- App image for app, worker and tagger (Python, extraction tools, built SPA): `extended-mind` (dev), `extended-mind-prod` (prod).
- Browser image `extended-mind-browser` (Playwright server).
- Third-party services use official images.

## Compose projects
- `extended-mind` (dev): `compose.yaml` + `compose.dev.yaml`. Source mounted, runserver with reload, `DEBUG=True`. Env `.env.dev`, data `data/dev/`.
- `extended-mind-prod`: `compose.yaml` + `compose.prod.yaml`. Built image, no source mounted, gunicorn, `DEBUG=False`. Env `.env.prod`, data `data/prod/`. Built and run from `main`.
- `extended-mind-ollama`: `compose.ollama.yaml`. Ollama and the model pull, shared by both. Data `data/ollama/`.
- Services per app project: `app`, `worker`, `tagger`, `browser`, `migrate` (one-off), `db`. Dev also `frontend` (Vite, profile `vite`).

## Networking
- `web`: `app`.
- `backend`: `app`, `worker`, `tagger`, `migrate`, `db`. Internal.
- `egress`: `worker`. Outbound internet.
- `browser`: `worker`, `browser`. Internal.
- `browser-egress`: `browser` only. Outbound internet.
- `ollama` (external, from the Ollama project): `ollama`, both projects' `tagger`. Internal. Ollama also has its own egress, to pull models.

## Exposed
- nginx, ports 80 (redirects) and 443.
- `em.cfqs.com` → prod app, `127.0.0.1:8001`.
- `dev-em.cfqs.com` → dev app, `127.0.0.1:8000`, basic auth.
- Vite: `127.0.0.1:5173`, reached over SSH (`ssh -L 5173:localhost:5173`).
- nginx config lives outside the repo.

## Config
- Environment variables only, from `.env.dev` / `.env.prod` (template `.env.example`).
- With `DEBUG` off: secure cookies, HSTS.

## Later
- Email (SES), monitoring (Prometheus, Grafana, Loki, Alloy).
