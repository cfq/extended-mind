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
