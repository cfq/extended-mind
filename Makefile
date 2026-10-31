COMPOSE = docker compose -f compose.yaml -f compose.dev.yaml
RUN = $(COMPOSE) run --rm app

.PHONY: lock build up down logs migrate createsuperuser shell ping test lint format

lock:
	uv lock

build:
	$(COMPOSE) build

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

migrate:
	$(RUN) python manage.py migrate

createsuperuser:
	$(RUN) python manage.py createsuperuser

shell:
	$(RUN) python manage.py shell

ping:
	$(RUN) python manage.py procrastinate defer extended_mind.tasks.ping

test:
	$(RUN) pytest

lint:
	$(RUN) sh -c "ruff check . && ruff format --check ."

format:
	$(RUN) sh -c "ruff check --fix . && ruff format ."
