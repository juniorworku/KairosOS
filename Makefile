.PHONY: dev preview extension-e2e down install test unit integration lint typecheck build e2e check migrate seed seed-owner generate-api ext-zip

PYTHON := api/.venv/bin/python

dev:
	docker compose up --build

preview:
	KAIROS_WEB_COMMAND="npm ci && npm run build && npm exec vite preview -- --host 0.0.0.0 --port 5173" docker compose up -d web

extension-e2e:
	cd extension && npm run build && npm run test:e2e

down:
	docker compose down

install:
	python3 -m venv api/.venv
	$(PYTHON) -m pip install -r api/requirements.lock
	$(PYTHON) -m pip install --no-deps -e ./api
	cd web && npm ci
	cd extension && npm ci

unit:
	cd api && .venv/bin/python -m pytest tests/unit tests/integration tests/auth/test_security.py tests/auth/test_google.py tests/integrations/test_services.py

test: unit
	cd web && npm run test
	cd extension && npm run test

integration:
	docker compose exec -T -e TEST_DATABASE_URL=postgresql+asyncpg://kairos:kairos@db:5432/kairos api python -m pytest

lint:
	cd api && .venv/bin/python -m ruff check app tests
	cd api && .venv/bin/python -m ruff format --check app tests
	cd web && npm run lint

typecheck:
	cd api && .venv/bin/python -m mypy app
	cd web && npm run typecheck
	cd extension && npm run typecheck

build:
	cd web && npm run build
	cd extension && npm run build

e2e:
	cd web && npm run e2e

check: lint typecheck test build integration e2e

migrate:
	docker compose exec -T api alembic upgrade head

seed: seed-owner

seed-owner:
	docker compose exec -T api python -m app.auth.seed

ext-zip:
	cd extension && npm run build
	$(PYTHON) -c "from pathlib import Path; from zipfile import ZipFile, ZIP_DEFLATED; base=Path('extension/dist'); archive=ZipFile('extension/kairos-focus.zip','w',ZIP_DEFLATED); [archive.write(path,path.relative_to(base)) for path in base.rglob('*') if path.is_file()]; archive.close()"

generate-api:
	cd api && .venv/bin/python -m app.export_openapi
	cd web && npm run generate:api
