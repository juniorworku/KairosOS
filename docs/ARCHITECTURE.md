# Architecture

## Runtime and boundaries

Kairos is a web-first planner. React 18, Vite, strict TypeScript, Tailwind, TanStack Query, and FullCalendar provide the UI. FastAPI/Pydantic v2, async SQLAlchemy, Alembic, PostgreSQL 16, Redis, and Celery provide the server. Original user-facing web copy lives in `web/src/copy/en.ts`.

Compose runs PostgreSQL, Redis, API, one worker service, one beat service, web, and Mailpit. Web/API/Mailpit UI ports bind to `127.0.0.1`. PostgreSQL and Redis are internal to the Compose network. The API applies migrations before serving in local development; worker and beat never apply migrations. Hosted migration orchestration is deferred with deployment.

The API exposes liveness at `/healthz` and actual database/Redis readiness at `/readyz`. A same-origin Vite proxy forwards `/api`, `/healthz`, and `/readyz`. Cookie authentication uses the browser's app origin; localhost development does not require third-party cookies.

## Accounts

Signup defaults to closed. The configured owner and owner/free/plus plans are seeded idempotently. A minimal hash-only seed marker prevents a deliberately deleted owner account being recreated on restart. Changing `OWNER_EMAIL` does not promote an existing user automatically.

Email sign-in stores SHA-256 hashes of random, expiring, single-use tokens. GET confirmation never consumes a token; POST verification atomically consumes it. Local delivery uses Mailpit SMTP; Resend and authenticated STARTTLS SMTP are supported for later real email configuration. Hosted email delivery queues through Celery; arguments and errors are redacted. Redis rate limits fail closed on outage. A daily task removes expired/revoked authentication records.

Google OIDC uses authorization code + PKCE, browser-bound state, nonce, and JWT signature/issuer/audience/expiry validation. Only verified emails can link identities. Sign-in uses `openid email profile` scopes; calendar consent is separate. No local or production authentication bypass exists.

Opaque sessions are stored hashed, with a session-bound CSRF token, rolling 30-day expiry, and a 90-day absolute limit. Hosted cookies are Secure/HttpOnly/SameSite=Lax; localhost development cookies omit Secure. Every user-owned domain endpoint depends on the authenticated user and filters ownership. Roles gate administration. Disabling a user revokes sessions and extension credentials immediately. Plan changes pass through one audited service.

## Persistence

Accounts, plans, sessions, integration credentials, availability intervals, extension tokens, and AI audit records use dedicated tables. The current planning implementation stores typed domain aggregates in `planning_records`, with explicit `user_id`, record kind, JSON payload, and timestamps. Pydantic validates aggregate shapes; the database also enforces the goal action cap. This is a deliberate deviation from the guide's separate table per planning aggregate. Referential and cross-record rules are enforced in services; expanding the product or increasing data volume should revisit normalized tables and query indexes through new migrations.

Migrations are frozen revisions. Do not edit an applied revision. All timestamps transport UTC; working-hour and calendar calculations use the user's IANA timezone.

## Deterministic planning

The scheduler and trajectory modules contain no database, HTTP, or AI calls. Scheduling respects availability, accepted work, blackout intervals, minimum durations, daily capacity, preferences, and planning buffers. Every proposal has a reason; capacity shortfalls are surfaced. Accepting a local plan and publishing to Google Calendar are separate actions. Trajectory comes from dates, recorded outcome metrics, and effort totals. AI never decides status or writes a schedule.

## Optional integrations

Calendar tokens are encrypted with a configured Fernet key. Availability uses the minimum free/busy scope; writing asks separately for the app-created calendar scope. Only the dedicated Kairos calendar receives approved blocks. Sync reconciles moved/deleted events and avoids duplicate publication. Calendar jobs run periodically under database row locks; provider errors are sanitized. Live Google consent, sensitive-scope verification, and real remote reconciliation still require credentialed acceptance checks.

Anthropic and Gemini adapters validate structured output, retry invalid responses once, and support streamed coaching. User text is treated as data. The provider receives the user's submitted text and, when requested, a compact redacted goal/trajectory context. It never receives auth credentials or raw calendar event details. Per-user AI-off and unconfigured-provider states keep the manual app usable.

AI quota reservations use PostgreSQL transactions/advisory locks and the audit table as the source of truth. This differs from the planned Redis hot counters plus nightly reconciliation. The local implementation favors a single authoritative reservation path; Redis counter reconciliation is not claimed implemented. Provider credentials, available model names, output limits, and the global cap remain configuration.

The Manifest V3 extension uses account pairing, token-limited endpoints, declarative navigation rules, storage, and local alarms. No page content/history is read. Basic blocking needs no broad host access; an optional reminder-page redirect asks for host permission. The local deadline owns unblock behavior during API outages. Immediate web-to-extension sync requires configuring the unpacked extension ID; polling is the fallback. Manual Chrome lifecycle QA remains a gate.

## Browser storage and builds

The PWA shell uses prompt-based service-worker updates. Private cached reads and the narrow offline write queue live in IndexedDB; logout/account changes clear private browser data. Auth, AI responses, and arbitrary mutations must not be service-worker cached. Production-build offline/install behavior and Lighthouse budgets need their own measured checks.

OpenAPI is exported without connecting to infrastructure. The generated TypeScript schema is committed, regenerated after endpoint changes, and checked for drift. Python and npm dependency locks are committed. Tests cover pure calculations, real isolated PostgreSQL ownership/security cases, fake provider contracts, web behavior, browser workflows, and extension rule generation.

No deployment or publishing is configured. Personal Mode, companion/helper processes, activity collection, OS automation, and interventions remain deferred.
