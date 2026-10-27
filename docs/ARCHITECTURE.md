# Architecture

## M0 scope

The repository follows the supplied monorepo plan. M0 provides a typed FastAPI application, React/Vite/Tailwind shell, SQLAlchemy/Alembic baseline, dependency health checks, Celery wiring, local Docker Compose, generated API types, and automated foundation checks. The UI contains clearly identified preview content; it does not imply persistent product functionality.

The implementation guide's Section 19 directs work to stop after M0. Product behavior in M1–M9 and Personal Mode in M10–M17 remains roadmap work. The user's instruction prohibits deployment, so no hosting resources or release automation are created.

## Technology decisions

- Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 async, Alembic, PostgreSQL 16.
- Redis with Celery worker and one beat process. Jobs have no production responsibilities yet.
- React 18, Vite, strict TypeScript, Tailwind, and original UI copy in `web/src/copy/en.ts`.
- OpenAPI is the API contract; `npm run generate:api` creates the frontend schema types. Commit generated output and regenerate when endpoints change.
- pytest/httpx, Ruff, strict mypy, ESLint, TypeScript, Vitest, and Playwright provide checks.

The scheduler and trajectory will be pure Python services with no persistence, HTTP, or AI imports. AI may suggest changes, but deterministic code owns schedule constraints and trajectory status. A user must approve every external calendar write.

## Local services

Compose runs PostgreSQL, Redis, API, worker, beat, web, and Mailpit. Only web, API, and the Mailpit browser UI expose ports, bound to `127.0.0.1`. The API source is mounted at `/app`; the web source is mounted at `/app` with dependencies in a named volume. Compose overrides database/Redis addresses for container networking. Host execution must use `localhost` connection strings instead.

`/healthz` is liveness; `/readyz` checks PostgreSQL and Redis. Database revisions run explicitly via `make migrate`, rather than being applied independently by worker/beat. Only one beat service should run.

## Security boundaries for later milestones

Real authentication must precede exposing user data. Closed signup, verified Google/email identities, hashed opaque sessions, CSRF, ownership-scoped queries, account export/deletion, and owner/admin roles belong to M1. A local preview is not an authentication bypass for production.

Google sign-in uses identity scopes only. Calendar consent is separate; use minimum availability scope and app-created-calendar scope, verifying current official documentation at M3/M5. Store encrypted tokens and free/busy intervals only. Provider credentials never belong in frontend bundles or source control.

Part III of the guide supersedes earlier assumptions. Render is the intended eventual host, not an authorized deployment now. Personal Mode stays disabled and unimplemented until core milestones are complete.
