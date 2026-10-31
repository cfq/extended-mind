# Iteration 0001 - Setup

Setup the system as defined in the SPECs.

Docker, Python, Django, etc. Get it all ready for me to configure.

---

## Claude Notes

Proposed scope (needs your OK):
- Dockerfile: one image for app + worker.
- `compose.yaml` + dev override: `app`, `worker`, `db`.
- Django project skeleton, settings from env vars.
- Ninja mounted at `/api/`, one `GET /api/health`.
- Procrastinate wired in, worker runs a no-op task.
- Admin at `/admin/`.
- `.env.example`.
- Commands for you to run: build, up, migrate, createsuperuser.

Deferred to later iterations:
- `proxy`, observability stack.
- React SPA + Node build stage.
- Extraction tools in the image (ffmpeg, Playwright, OCR…).

Questions:
- Python version: 3.13 or 3.14?
- Package manager: uv?
- Django project/package name: `extended_mind`?
- Settings: plain `os.environ` or `django-environ`?
- Lint/format: ruff? Tests: pytest + pytest-django?
- Task runner for commands: Makefile, justfile, or none?
- CI (GitHub Actions) now or later?
