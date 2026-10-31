# Iteration 0001 - Setup

Setup the system as defined in the SPECs.

Docker, Python, Django, etc. Get it all ready for me to configure.

---

## Claude Notes

Scope (approved):
- Dockerfile: one image for app + worker. Python 3.14, uv.
- `compose.yaml` + dev override: `app`, `worker`, `db`.
- Django project `extended_mind`, settings via django-environ.
- Ninja at `/api/v1/`, one `GET /api/v1/health`.
- Procrastinate wired in, worker runs a no-op task.
- Admin at `/admin/`.
- ruff, pytest-django.
- `.env.example`.
- Makefile: build, up, migrate, createsuperuser, test, lint.

Deferred:
- `proxy`, observability stack.
- React SPA + Node build stage.
- Extraction tools in the image.
- CI.
- Production web server (runserver for now).

Small decisions:
- Project package is also the only Django app (`extended_mind`), so Procrastinate finds `tasks.py`.
- venv at `/opt/venv`, so the dev bind mount doesn't hide it.
- Dev deps in the image only with `DEV=true` (dev override).
- Postgres data bind-mounted to `${DATA_DIR:-./data}/postgres`, not a named volume.
- Default `BigAutoField` pks.
- `ping` task logs "pong"; `make ping` defers it.
