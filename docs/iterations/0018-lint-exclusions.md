# 0018 - Lint exclusions

## Asked
- `make lint` failed on `main`. Exclude migrations folders from ruff.

## Extrapolated
- Two hand-written tests with long lines: reformatted with `ruff format`, not excluded.

## Changes
- `backend/pyproject.toml`: `extend-exclude = ["**/migrations"]` under `[tool.ruff]`. Covers `ruff check` and `ruff format`.
- `apps/core/tests/test_spa.py`, `apps/users/tests/test_api.py`: wrapped by `ruff format`.

---

## Claude Notes
- Before: 38 errors. 36 E501 and 1 I001 in generated migrations, 2 E501 in the tests.
- `extend-exclude` keeps ruff's default excludes (`.venv`, `node_modules`, ...); `exclude` would replace them.
- The two tests slipped through because `make format` runs `ruff check --fix . && ruff format .`: an unfixable check error stops it before the formatter runs. Not changed here.
