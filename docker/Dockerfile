FROM node:24-slim AS frontend

WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build


FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app/backend

ARG DEV=false
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --locked $([ "$DEV" = "true" ] || echo --no-dev)

COPY . /app
COPY --from=frontend /frontend/dist /opt/frontend

# Dummy env: settings need these to load, collectstatic doesn't use them.
RUN SECRET_KEY=build DATABASE_URL=sqlite://:memory: \
    python manage.py collectstatic --noinput

EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
