.PHONY: dev down install test lint typecheck build e2e check migrate seed generate-api

PYTHON := api/.venv/bin/python

dev:
	docker compose up --build

down:
	docker compose down

install:
	python3 -m venv api/.venv
	$(PYTHON) -m pip install -r api/requirements.lock
	$(PYTHON) -m pip install --no-deps -e ./api
	cd web && npm ci

test:
	cd api && .venv/bin/python -m pytest
	cd web && npm run test

lint:
	cd api && .venv/bin/python -m ruff check app tests
	cd api && .venv/bin/python -m ruff format --check app tests
	cd web && npm run lint

typecheck:
	cd api && .venv/bin/python -m mypy app
	cd web && npm run typecheck

build:
	cd web && npm run build

e2e:
	cd web && npm run e2e

check: lint typecheck test build e2e

migrate:
	docker compose exec api alembic upgrade head

seed:
	@echo "Owner seeding ships with M1 authentication; M0 has no accounts."

generate-api:
	cd api && .venv/bin/python -m app.export_openapi
	cd web && npm run generate:api
