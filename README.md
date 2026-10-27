# Kairos

A calm workspace connecting goals, a realistic weekly plan, focus, and reflection. Inspired by research on implementation intentions and time blocking.

This repository currently implements **M0: foundation** from [IMPLEMENTATION.md](IMPLEMENTATION.md). The interface is a design preview; authentication, saved goals, scheduling, calendar integration, coaching, and focus logging are upcoming milestones. Nothing is deployed.

## Run locally

Requirements: Docker Engine with Compose v2.24 or newer. For development without containers: Python 3.12, Node.js 22, npm, and PostgreSQL/Redis for dependency readiness.

```sh
cp .env.example .env
make dev
```

Open the app at http://localhost:5173, API documentation at http://localhost:8000/docs, and Mailpit at http://localhost:8025. `GET /healthz` checks the API process; `GET /readyz` checks dependencies. Development ports bind to the local machine only.

After services start, initialize the schema:

```sh
make migrate
```

Stop services with `make down`. Database data persists in a named Docker volume.

## Checks

```sh
make install
make lint
make typecheck
make test
make build
cd web && npx playwright install chromium
cd .. && make e2e
```

`make generate-api` regenerates TypeScript types from the backend schema; see the architecture document for the generator contract. CI runs the foundation checks, not external Google or AI calls.

Python setup installs the exact resolved versions in `api/requirements.lock`, then installs the application without resolving dependencies again. CI also checks dependency advisories and boots the complete local Compose stack, applies the baseline migration twice, and checks API/web readiness and worker responsiveness.

See [architecture](docs/ARCHITECTURE.md), [roadmap](docs/ROADMAP.md), [open questions](docs/OPEN_QUESTIONS.md), [privacy](docs/PRIVACY.md), and the [local demo](docs/DEMO.md). Milestones are marked complete only after their acceptance checks have been verified.
