COMPOSE = docker compose -f compose.yaml -f compose.dev.yaml
RUN = $(COMPOSE) run --rm app
PROJECT = label=com.docker.compose.project=extended-mind
DATA_DIR ?= ./data

.PHONY: lock build up down logs migrate createsuperuser shell ping test lint format
.PHONY: nuke nuke-ps nuke-network nuke-volumes nuke-images nuke-data

lock:
	cd backend && uv lock

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
	$(RUN) python manage.py procrastinate defer apps.core.tasks.ping

test:
	$(RUN) pytest

lint:
	$(RUN) sh -c "ruff check . && ruff format --check ."

format:
	$(RUN) sh -c "ruff check --fix . && ruff format ."

# Destructive. Scoped to the extended-mind Compose project.
nuke-ps:
	docker ps -aq --filter $(PROJECT) | xargs -r docker rm -f

nuke-network: nuke-ps
	docker network ls -q --filter $(PROJECT) | xargs -r docker network rm

nuke-volumes: nuke-ps
	docker volume ls -q --filter $(PROJECT) | xargs -r docker volume rm

nuke-images: nuke-ps
	docker images -q extended-mind | xargs -r docker rmi -f

# Postgres files are owned by the container user, so delete from a container.
nuke-data: nuke-ps
	@printf "Delete $(DATA_DIR)/postgres? [y/N] " && read a && [ "$$a" = y ]
	docker run --rm -v $(abspath $(DATA_DIR)):/data postgres:18 rm -rf /data/postgres

nuke: nuke-data nuke-network nuke-volumes nuke-images
