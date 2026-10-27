# Kairos

A personal planner for goals, weekly time blocks, focus sessions, and reflection. The core app runs locally; nothing is deployed.

The Users and invites screens are deferred. The repository includes account sign-in and personal settings, saved goal planning, a deterministic weekly scheduler, focus logging and progress check-ins. Google Calendar and AI coaching are optional server-side integrations. An unpacked Chrome focus extension is included. The detailed requirements remain in [IMPLEMENTATION.md](IMPLEMENTATION.md); implementation status and remaining acceptance work are tracked in [the roadmap](docs/ROADMAP.md).

## Run locally

Requirements: Docker Engine with Compose v2.24 or newer. Host-side checks additionally use Python 3.12, Node.js 22, and npm.

```sh
cp .env.example .env
make dev
```

Open [Kairos](http://localhost:5173), [API documentation](http://localhost:8000/docs), and [the local email inbox](http://localhost:8025). Use `localhost` consistently so the development sign-in cookie matches the app origin. Only local-machine ports are exposed.

The development account comes from `OWNER_EMAIL`, initially `owner@localhost.test`. Enter that address on the sign-in page, open its message in Mailpit, and confirm the sign-in link. Mailpit captures development email; it does not deliver messages to a real inbox. No password or sign-in bypass is used. Unknown addresses receive the same request response while signup is closed.

The API applies migrations before starting and seeds the owner and plans idempotently. Workers do not independently run migrations. `make migrate` can reapply pending revisions safely; `make seed-owner` checks owner setup. Deleting the owner prevents automatic account recreation on restart.

For the installable production build and offline shell, run `make preview` after the stack starts. `make dev` remains the hot-reload development command.

Stop with `make down`. PostgreSQL records remain in a named local volume.

## Use the core loop

Create a goal with one to five actions and an outcome measure. Choose working hours, add busy intervals if needed, and draft a week. Review proposed blocks before accepting them. Start a focus session, rate it when finished, record outcome progress, and save a weekly reflection. Time spent is effort evidence; it never becomes invented outcome progress.

Google sign-in, Google Calendar, and the coach remain unavailable until their credentials are configured. The manual planning and focus workflow works without them. See [configuration questions](docs/OPEN_QUESTIONS.md). Calendar consent is separate from sign-in; external calendar writes require explicit user approval.

To try the extension, follow [its local setup guide](extension/README.md). Nothing installs the extension or publishes it automatically.

## Verify changes

```sh
make install
make lint typecheck test build
make integration
cd web && npx playwright install chromium
cd .. && PLAYWRIGHT_EXTERNAL_SERVER=1 make e2e
make generate-api
```

Start the local stack before integration and browser checks. `make test` runs infrastructure/unit/provider-fake tests and web/extension tests without needing a database. `make integration` runs the complete backend suite with a nonempty test database URL inside Compose. Database tests create and remove their own schemas; they do not reuse application records. CI provisions PostgreSQL/Redis and runs these tests rather than silently skipping them.

Browser checks use the real local app, API, and Mailpit. `PLAYWRIGHT_EXTERNAL_SERVER=1` reuses the Compose web server. Without that flag, Playwright starts a host Vite server and still needs the API/Mailpit running.

`make generate-api` exports OpenAPI and regenerates frontend types. Both generated files are committed and checked for drift in CI. Python dependencies are pinned in `api/requirements.lock`; npm lockfiles pin the web and extension. CI also builds the local stack, checks migrations and workers, and audits dependencies. No CI job deploys or publishes anything. A workflow file is not evidence that remote CI has run; see the verification record for actual results.

See [architecture](docs/ARCHITECTURE.md), [privacy](docs/PRIVACY.md), [the demo](docs/DEMO.md), and [remaining work](docs/ROADMAP.md). Local production Lighthouse and offline checks have passed; see the verification report. Public deployment, live provider verification, and remaining Chrome manual QA remain separate acceptance gates.
