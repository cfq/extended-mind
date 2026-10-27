# 0001 Backend Python Framework

- Status: accepted
- Date: 2026-10-30

## Context
- The service will be tightly integrated with the web interface
- There will be a lot of web development
- There will be a need for an API but it will be closely following the contours
- Apps in other platforms will be implementing the same functionality
- There will be a worker process, but running in parallel asynchronously
- In scope: multi-user auth, admin panel, background worker sharing the models

## Options
- Django + Ninja
  - + Models + migrations (preferred over SQLAlchemy + Alembic).
  - + Auth, sessions, CSRF, password reset, admin built in.
  - + Worker uses the same models (Procrastinate Django integration).
  - − Heavier; async weaker.
- FastAPI + SQLAlchemy + Alembic + SQLAdmin
  - + Lighter, explicit, natural API-first fit.
  - − Auth hand-rolled; admin thinner; models/migrations less liked.
- Server-rendered (Jinja + HTMX/Alpine, or web components)
  - − Rich widgets duplicated across server and client templates.
- Node-rendered (Astro / React Router) + Python API
  - − Two runtimes in production.

## Decision
- Django for models, migrations, auth, admin, worker.
- Django Ninja for the JSON API.
- React SPA (Vite), built to static files, served same-origin.
- Admin and some monitoring together in Django admin.
- Prometheus and Grafana for monitoring.
- Loki for logging.

## Consequences
- Pages need JS.
- JS build step; Node at build time only.
- Same-origin session + CSRF for the SPA; API tokens for other clients.
- Templates only for emails.
- Weak async doesn't matter: slow work runs in the worker.
