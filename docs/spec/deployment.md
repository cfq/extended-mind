# Deployment

Draft.

## Docker
- Everything runs in containers via Docker Compose; the host only needs Docker.
- One image, `extended-mind`, for app and worker (Python + extraction tools + built SPA).
- Third-party services use official images.

## Compose project
- Name: `extended-mind`.
- Services:
  - `proxy`: reverse proxy, TLS (choice TBD).
  - `app`: Django + Ninja, serves the SPA.
  - `worker`: Procrastinate, same image as `app`.
  - `db`: Postgres.
  - `prometheus`, `grafana`, `loki`, `alloy`, `node-exporter`.

## Networking
- `web`: `proxy`, `app`, `grafana`.
- `backend`: `app`, `worker`, `db`. Internal, no outside access.
- `observability`: `prometheus`, `grafana`, `loki`, `alloy`, `node-exporter`, plus `app` and `worker` to be scraped.
- `egress`: `worker`. Outbound internet only, nothing inbound.
- Outbound internet: `worker` (fetching, via `egress`), `app` (SES, via `web`).

## Exposed
- Only `proxy`, ports 80/443.
- Proposed domains:
  - `em.cfqs.com`: app.
  - `dashboard.em.cfqs.com`: Grafana, behind login.
- Everything else reachable only inside Compose networks.

## Config
- Environment variables only; one set per environment.
- Secrets never in the repo or the image.
- Base `compose.yaml` shared; per-environment override files.

## Environments
- Dev
  - Console email, no TLS, ports opened locally as needed.
- Prod
  - SES email, TLS, only the proxy exposed.
