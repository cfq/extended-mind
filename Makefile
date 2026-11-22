# Dev (dev-em.cfqs.com): .env.dev, data/dev. Prod (em.cfqs.com): .env.prod,
# data/prod, built from main. Ollama: shared by both, data/ollama.
DEV = docker compose --project-directory . -f docker/compose.yaml -f docker/dev.yaml
PROD = docker compose --project-directory . -f docker/compose.yaml -f docker/prod.yaml
OLLAMA = docker compose --project-directory . -f docker/ollama.yaml
RUN = $(DEV) run --rm app
PROJECT = label=com.docker.compose.project=extended-mind-dev
DATA_DIR ?= ./data/dev

.PHONY: lock npm dev-build dev-up dev-down dev-logs makemigrations migrate dev-createsuperuser shell ping test test-backend test-frontend lint format
.PHONY: install ollama-up ollama-down vite prod-build prod-up prod-down prod-logs prod-createsuperuser
.PHONY: nuke nuke-ps nuke-network nuke-volumes nuke-images nuke-data

lock:
	cd backend && uv lock

# e.g. make npm ARGS="install some-lib"
npm:
	$(DEV) run --rm --no-deps frontend npm $(ARGS)

# Fresh checkout or after a nuke: dependencies exactly as locked, images,
# then the stack (migrations come up with it).
install: ollama-up
	$(DEV) run --rm --no-deps frontend npm ci
	$(DEV) build
	$(DEV) up -d
	@echo "Next: make dev-createsuperuser"

# Shared Ollama; pulls the tagging model if missing. Both stacks need it up.
ollama-up:
	$(OLLAMA) up -d

# Stop the dev and prod stacks first: their taggers hold the ollama network.
ollama-down:
	$(OLLAMA) down

dev-build:
	$(DEV) build

dev-up: ollama-up
	$(DEV) up -d

# Vite dev server on 127.0.0.1:5173; ssh -L 5173:localhost:5173 to use it.
vite:
	$(DEV) --profile vite up -d frontend

dev-down:
	$(DEV) down

dev-logs:
	$(DEV) logs -f

# No deps: doesn't need the database.
makemigrations:
	$(DEV) run --rm --no-deps app python manage.py makemigrations

migrate:
	$(RUN) python manage.py migrate

dev-createsuperuser:
	$(RUN) python manage.py createsuperuser

shell:
	$(RUN) python manage.py shell

ping:
	$(RUN) python manage.py procrastinate defer apps.core.tasks.ping

test: test-backend test-frontend

test-backend:
	$(RUN) pytest

# Node's built-in runner; no test dependencies.
test-frontend:
	$(DEV) run --rm --no-deps frontend node --test

lint:
	$(RUN) sh -c "ruff check . && ruff format --check ."

format:
	$(RUN) sh -c "ruff check --fix . && ruff format ."

# Production. Build from main: the image is what runs.
prod-build:
	$(PROD) build

prod-up: ollama-up
	$(PROD) up -d

prod-down:
	$(PROD) down

prod-logs:
	$(PROD) logs -f

prod-createsuperuser:
	$(PROD) run --rm app python manage.py createsuperuser

# Destructive. Scoped to the extended-mind-dev Compose project.
nuke-ps:
	docker ps -aq --filter $(PROJECT) | xargs -r docker rm -f

nuke-network: nuke-ps
	docker network ls -q --filter $(PROJECT) | xargs -r docker network rm

nuke-volumes: nuke-ps
	docker volume ls -q --filter $(PROJECT) | xargs -r docker volume rm

nuke-images: nuke-ps
	docker images -q --filter reference='extended-mind-dev*' | xargs -r docker rmi -f

# Postgres files are owned by the container user, so delete from a container.
nuke-data: nuke-ps
	@printf "Delete $(DATA_DIR)/postgres and item_sources? [y/N] " && read a && [ "$$a" = y ]
	docker run --rm -v $(abspath $(DATA_DIR)):/data postgres:18 rm -rf /data/postgres /data/item_sources

nuke: nuke-data nuke-network nuke-volumes nuke-images
