# Kairos (working name): Implementation Guide

> Audience: an autonomous coding agent (and humans reviewing its work).
> Goal: build a **web-first goal-to-action planner** (PWA) with a **Chrome extension** for focus-mode site blocking.
> Read this file fully before writing code. Work milestone by milestone (Section 15). Do not skip acceptance criteria.
>
> **Part I (Sections 0–19)** is the core product (milestones M0–M9). **Part II (Sections 20–31)** adds the *Personal Mode* feature set (local companion app, automations, activity logging, audits) as milestones M10–M17. **Part III (Sections 32–38)** records the product decisions that supersede earlier assumptions: Kairos naming, Google + magic-link auth with real user management, plan-based AI gating, and hosting on Render. **Where Part III conflicts with Parts I or II, Part III wins.** Build Part I first.

---

## 0. Ground rules for the agent

1. **Original product.** Do not copy copy, branding, or UI from any reference product. All UI text is written fresh and lives in one i18n-ready file (`web/src/copy/en.ts`).
2. **No efficacy claims.** The UI must never say "science-proven" or "guaranteed". Allowed phrasing: "inspired by research on implementation intentions and time blocking."
3. **Deterministic core, AI at the edges.** The scheduler and trajectory engine are plain, unit-tested Python. AI only proposes, explains, and coaches. AI output never writes to the calendar or database without user approval.
4. **User approves every calendar write.** Nothing is written to Google Calendar until the user accepts a proposed plan.
5. **Narrowest Google scopes** (Section 8). Never request `calendar` or `calendar.events` (full access).
6. **Everything typed.** Python: full type hints, `mypy --strict` on `app/`. TypeScript: `strict: true`, no `any`.
7. **Small commits, tests with each feature.** Each milestone ends green: lint, types, unit tests, e2e smoke.
8. **Ask before inventing.** If a requirement is ambiguous, add it to `docs/OPEN_QUESTIONS.md` and pick the simplest option; do not stall.
9. **Personal Mode (Part II) is opt-in by feature flag** (`FEATURES`, see Section 20). Its features are individually flag-gated, and each device-level effect (hosts file, Do Not Disturb, screen overlay, window logging) must be **reversible, time-limited, and have a user escape hatch.**

### Stack decisions (and one correction)

| Concern | Choice |
|---|---|
| Backend | **FastAPI** (Python 3.12), Pydantic v2, async |
| ORM / migrations | **SQLAlchemy 2.0 (async) + Alembic** |
| DB | PostgreSQL 16 |
| Jobs | **Celery + Redis** (worker + beat) |
| Frontend | React 18 + **Vite** + TypeScript + **Tailwind CSS** |
| Data fetching | TanStack Query; typed client generated from FastAPI's OpenAPI (`openapi-typescript`) |
| Calendar UI | FullCalendar (timegrid + interaction) |
| PWA | `vite-plugin-pwa` (Workbox) |
| Extension | Chrome Manifest V3, TypeScript, built with Vite (`@crxjs/vite-plugin` or plain multi-entry) |
| LLM | Provider-agnostic interface; **Anthropic** default, **Gemini** adapter |
| Tests | pytest + httpx, Vitest + Testing Library, Playwright |
| Infra (dev) | Docker Compose |
| Hosting (prod) | **Render**: static site, web service, 2 background workers, managed Postgres, Key Value (Redis-compatible). See Part III |
| Transactional email | Provider behind an `EmailSender` interface (Resend, Postmark, or SES), used for magic links |

> **Correction to the original request:** Prisma and Drizzle are TypeScript ORMs and do not fit a FastAPI (Python) backend. Use **SQLAlchemy 2.0 + Alembic**, which is the standard equivalent. If the team later wants a TypeScript backend, swap to Drizzle. Do not use Prisma's Python client, which is not a dependable choice.

---

## 1. Product summary

A planner that connects **goals → weekly time blocks → focus sessions → honest feedback**.

**Core loop**
1. **Define** a goal using a structured wizard (the "GPS" frame: Goal, Plan, System).
2. **Plan**: the system proposes a realistic week around the user's real calendar availability. The user keeps, moves, or discards each block.
3. **Do**: start a focus session from a block; the Chrome extension blocks distracting sites during the session.
4. **Reflect**: the trajectory engine reports on-track / adjust / off-track per goal, and the coach suggests concrete fixes.

**Placeholder for the owner's own features:** see Section 16 (Extension points). Keep the codebase modular so those slot in without rewrites.

---

## 2. MVP scope

**In scope**
- Email/Google sign-in, sessions, account deletion
- Seasons, Goals (with GPS fields), Actions, Obstacles (if-then plans)
- Google Calendar: free/busy read + write to a dedicated app-created calendar
- Deterministic weekly scheduler with accept/edit/discard review UI
- Focus timer + session logging + self-rated focus (1–5)
- Progress check-ins and trajectory engine
- Weekly reflection + AI coach (structured suggestions + streaming chat)
- Background sync jobs
- PWA (installable, offline shell, cached reads)
- Chrome extension: pair with account, block sites during sessions, show timer

**Out of scope for MVP** (do not build)
- Native mobile apps, mobile app blocking
- Outlook / Apple calendars
- "Focus quality" scoring beyond the self-rating (*Part II adds a calendar + activity based efficiency score in M16*)
- Teams, sharing, payments (plan-based AI gating **is** in scope; billing is not. See Part III Section 34)
- Music, third-party integrations (Slack, meeting-note tools). *Partly reversed in Part II (Personal Mode), after M9.*

---

## 3. Repository layout (monorepo)

```
kairos/
├─ README.md
├─ IMPLEMENTATION.md              # this file
├─ docker-compose.yml
├─ .env.example
├─ Makefile                       # make dev | test | lint | migrate | seed
├─ docs/
│  ├─ OPEN_QUESTIONS.md
│  ├─ ARCHITECTURE.md
│  └─ PRIVACY.md
├─ api/
│  ├─ pyproject.toml
│  ├─ alembic.ini
│  ├─ alembic/versions/
│  ├─ app/
│  │  ├─ main.py                  # FastAPI app factory, middleware, routers
│  │  ├─ config.py                # pydantic-settings
│  │  ├─ db.py                    # async engine/session
│  │  ├─ security.py              # sessions, CSRF, encryption helpers
│  │  ├─ deps.py                  # current_user, db session deps
│  │  ├─ models/                  # SQLAlchemy models (one file per aggregate)
│  │  ├─ schemas/                 # Pydantic request/response models
│  │  ├─ routers/                 # auth, goals, plan, sessions, calendar, coach, ext, me
│  │  ├─ services/
│  │  │  ├─ scheduler/            # PURE: no I/O. slots.py, scoring.py, plan.py
│  │  │  ├─ trajectory.py         # PURE
│  │  │  ├─ calendar/             # google client, sync, publish
│  │  │  └─ focus.py
│  │  ├─ ai/
│  │  │  ├─ provider.py           # LLMProvider protocol + registry
│  │  │  ├─ anthropic_provider.py
│  │  │  ├─ gemini_provider.py
│  │  │  ├─ tasks/                # goal_refine.py, action_suggest.py, ...
│  │  │  └─ prompts/              # *.md prompt templates
│  │  └─ jobs/                    # celery_app.py, sync.py, nudges.py
│  └─ tests/
│     ├─ unit/                    # scheduler, trajectory, crypto
│     ├─ integration/             # DB + routers
│     └─ fixtures/
├─ web/
│  ├─ package.json
│  ├─ vite.config.ts
│  ├─ tailwind.config.ts
│  ├─ src/
│  │  ├─ main.tsx, App.tsx, router.tsx
│  │  ├─ api/                     # generated client + query hooks
│  │  ├─ features/                # goals, plan, focus, trajectory, coach, onboarding, settings
│  │  ├─ components/ui/           # buttons, dialogs, inputs (own small design system)
│  │  ├─ copy/en.ts
│  │  ├─ pwa/                     # sw registration, install prompt, offline banner
│  │  └─ lib/                     # time, tz, ext-bridge
│  └─ e2e/                        # Playwright
├─ extension/
│  ├─ manifest.json
│  ├─ src/{background.ts, popup/, blocked/, options/, api.ts, rules.ts}
│  └─ vite.config.ts
├─ companion/                     # Part II: desktop companion (Tauri v2: Rust shell + React UI)
│  ├─ src-tauri/                  # tray, global hotkey, windows, local SQLite outbox, OS adapters
│  └─ src/                        # capture bar, overlay, settings (shares components with web/)
└─ helper/                        # Part II: tiny privileged service (hosts file only)
```

---

## 4. Environment & local dev

`docker-compose.yml` services: `db` (postgres:16), `redis`, `api`, `worker`, `beat`, `web`. Hot reload for `api` (uvicorn `--reload`) and `web` (Vite).

`.env.example`:

```
# --- core ---
APP_ENV=dev
APP_BASE_URL=http://localhost:5173
API_BASE_URL=http://localhost:8000
SECRET_KEY=change-me-32+bytes
TOKEN_ENCRYPTION_KEY=base64-32-bytes       # for calendar refresh tokens (AES-GCM or Fernet)
DATABASE_URL=postgresql+asyncpg://kairos:kairos@db:5432/kairos
REDIS_URL=redis://redis:6379/0

# --- google ---
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
GOOGLE_CALENDAR_REDIRECT_URI=http://localhost:8000/calendar/callback

# --- llm ---
LLM_PROVIDER=anthropic                       # anthropic | gemini
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-sonnet-5-5            # keep configurable; never hardcode in code
GEMINI_API_KEY=
GEMINI_MODEL=
LLM_MAX_OUTPUT_TOKENS=1500
# per-user AI limits come from plans (Part III Section 34); this is the global kill switch
GLOBAL_AI_DAILY_CALL_CAP=500

# --- auth & users (Part III) ---
SIGNUP_MODE=closed                           # closed | invite | open
OWNER_EMAIL=you@example.com                  # seeded as role=owner
COOKIE_DOMAIN=localhost                      # prod: .yourdomain.tld
MAGIC_LINK_TTL_MIN=15
EMAIL_PROVIDER=console                       # console (dev) | resend | postmark | ses
EMAIL_API_KEY=
EMAIL_FROM=login@yourdomain.tld

# --- privacy toggles (Part II/III) ---
STORE_EVENT_TITLES=false
ACTIVITY_RAW_RETENTION_DAYS=30

# --- extension ---
EXTENSION_ID=                                 # for CORS + externally_connectable
```

Commands: `make dev` (compose up), `make migrate` (alembic upgrade head), `make test`, `make lint`.

---

## 5. Data model (SQLAlchemy / Alembic)

Conventions: UUID primary keys, `created_at`/`updated_at` (UTC, timezone-aware), soft-delete only where noted. All user-owned rows carry `user_id` and **every query filters by it** (add a repository helper that enforces this).

```
users
  id, email (unique), name, avatar_url, timezone (IANA, default 'UTC'),
  work_days (int[] 0-6), work_start (time), work_end (time),
  daily_max_focus_minutes (default 240), energy_peak ('morning'|'afternoon'|'evening'),
  plan_id (FK plans), role ('owner'|'admin'|'user'), email_verified_at,
  disabled_at, onboarding_completed_at, deleted_at
  # extra auth/plan tables: Part III Sections 33-34

auth_identities
  id, user_id, provider ('google'|'email'), provider_user_id (unique w/ provider)

sessions
  id, user_id, token_hash, expires_at, user_agent, ip_hash, revoked_at

calendar_connections
  id, user_id (unique), provider ('google'),
  scopes (text[]), refresh_token_enc (bytes), access_token_enc (bytes, nullable),
  access_expires_at, app_calendar_id (the dedicated calendar we create),
  busy_calendar_ids (text[]), events_sync_token (nullable),
  status ('active'|'needs_reauth'|'revoked'), last_synced_at, last_error

busy_intervals                       # cache of free/busy; NO titles stored
  id, user_id, start_at, end_at, source_calendar_id, fetched_at
  index (user_id, start_at, end_at)

seasons
  id, user_id, name, start_date, end_date, status ('planned'|'active'|'done')

goals
  id, user_id, season_id,
  title, outcome_statement,
  metric_name, metric_unit, metric_start, metric_target, target_date, start_date,
  why_facts, why_feelings, why_function,           # the "3 Fs"
  anti_goals (text[]),
  confidence_pct (0-100), follow_through_pct (0-100),
  priority (1-5), status ('active'|'paused'|'done'|'dropped')

actions                               # the 3–5 "major moves" per goal
  id, goal_id, user_id, title, kind ('habit'|'project'),
  weekly_minutes_target (nullable),     # habits & ongoing projects
  total_minutes_estimate (nullable),    # finite projects
  preferred_block_minutes (default 60), min_block_minutes (30), max_block_minutes (120),
  preferred_time_of_day ('morning'|'afternoon'|'evening'|'any'),
  requires_deep_focus (bool), position
  CHECK: max 5 active actions per goal (enforce in service + DB trigger/constraint test)

obstacles                             # "crystal ball" + if-then plans
  id, goal_id, user_id, risk_text, if_cue, then_response

progress_checkins
  id, goal_id, user_id, recorded_at, metric_value, note

time_blocks
  id, user_id, action_id, goal_id,
  start_at, end_at, planned_minutes,
  status ('proposed'|'accepted'|'published'|'completed'|'skipped'|'moved'|'cancelled'),
  google_event_id (nullable), google_etag (nullable),
  proposed_by ('scheduler'|'user'), reason (text),  # why the scheduler put it here
  moved_count (int default 0), week_start (date)
  index (user_id, start_at)

focus_sessions
  id, user_id, time_block_id (nullable), action_id (nullable),
  started_at, ended_at, planned_minutes, actual_minutes,
  self_rating (1-5, nullable), distractions_blocked_count (int default 0),
  blocklist_snapshot (text[])

blocklists
  id, user_id, name, domains (text[]), is_default

weekly_reflections
  id, user_id, week_start, wins, misses, adjustments, ai_summary (jsonb), created_at

extension_tokens
  id, user_id, token_hash, label, created_at, last_used_at, revoked_at

ai_calls                              # audit + cost control; no raw calendar data
  id, user_id, task, provider, model, input_tokens, output_tokens,
  latency_ms, status, created_at
```

**Migrations:** one Alembic revision per milestone at minimum. Never edit an applied revision.

---

## 6. Backend architecture

### 6.1 App structure
- `create_app()` in `main.py` registers routers, CORS (allow `APP_BASE_URL` and the extension origin `chrome-extension://$EXTENSION_ID`), security headers, request-id middleware, and structured JSON logging.
- Routers are thin; business logic lives in `services/`. **`services/scheduler/` and `services/trajectory.py` must not import DB, HTTP, or AI code.**

### 6.2 Authentication & sessions
- **Sign-in:** Google OIDC (scopes `openid email profile` only) **and email magic link, both at launch.** Full spec, account linking, signup modes, roles: Part III Section 33.
- **Sessions:** opaque random token stored hashed in `sessions`; sent as `HttpOnly; Secure; SameSite=Lax` cookie. CSRF: double-submit token header for state-changing requests from the web app.
- **Calendar consent is separate** from sign-in (incremental authorization, Section 8).
- **Extension auth:** pairing token (Section 11.3), sent as `Authorization: Bearer`. Extension tokens can only call `/ext/*` endpoints.
- Rate limit auth endpoints and AI endpoints (Redis token bucket).

### 6.3 REST API (all under `/api/v1`)

```
Auth
  GET   /auth/google/login            -> redirect
  GET   /auth/google/callback
  POST  /auth/magic/request           body: {email}   (always 202, same response)
  GET   /auth/magic?token=            -> confirmation page (does NOT consume)
  POST  /auth/magic/verify            body: {token}   -> sets session
  POST  /auth/logout
  GET   /me                           PATCH /me          DELETE /me   (full data deletion)

Planning objects
  CRUD  /seasons
  CRUD  /goals                        POST /goals/{id}/actions   etc.
  CRUD  /actions
  CRUD  /obstacles
  POST  /goals/{id}/checkins

Calendar
  GET   /calendar/connect             -> redirect to Google consent (calendar scopes)
  GET   /calendar/callback
  GET   /calendar/status
  POST  /calendar/disconnect          -> revoke token + delete cached busy data
  POST  /calendar/sync                -> enqueue immediate sync

Plan
  POST  /plan/draft                   body: {week_start}  -> proposed blocks + reasons
  GET   /plan/week?start=YYYY-MM-DD   -> blocks for the week
  POST  /plan/accept                  body: {block_ids[]} -> publish to Google
  PATCH /blocks/{id}                  (move/resize/skip/complete)
  DELETE /blocks/{id}

Focus
  POST  /focus/start                  body: {time_block_id?, planned_minutes, blocklist_id?}
  POST  /focus/{id}/end               body: {self_rating?}
  GET   /focus/active
  GET   /focus/stats?from&to
  CRUD  /blocklists

Trajectory & reflection
  GET   /trajectory                   -> per-goal status
  GET   /reflection/{week_start}      POST /reflection/{week_start}

Coach (AI)
  POST  /coach/goal-refine
  POST  /coach/suggest-actions
  POST  /coach/suggest-obstacles
  POST  /coach/weekly-review
  POST  /coach/chat                   -> SSE stream

Extension (token auth)
  GET   /ext/state                    -> {active_session, blocklist, ends_at}
  POST  /ext/event                    -> {type:'blocked', domain} counters
  POST  /ext/pair                     (from web session) -> one-time pairing code
  POST  /ext/pair/redeem              (from extension) -> bearer token
```

Return consistent error shape: `{ "error": { "code": "...", "message": "...", "details": {} } }`. Use pagination (`limit`, `cursor`) on list endpoints that can grow (blocks, sessions).

### 6.4 Background jobs (Celery)

| Task | Trigger | What it does |
|---|---|---|
| `sync_busy(user_id)` | beat every 15 min for active users; on-demand; after consent | Calls Google `freebusy.query` for the next 21 days, replaces `busy_intervals` for that window |
| `sync_app_calendar(user_id)` | beat every 10 min; on-demand | `events.list` on the app calendar with `syncToken`; detects user-moved/deleted blocks and updates `time_blocks` (`moved_count++`, status) |
| `publish_blocks(user_id, block_ids)` | after `/plan/accept` | Creates/updates events on the app calendar; stores `google_event_id`/`etag`; idempotent |
| `refresh_trajectories()` | nightly | Recompute and cache trajectory snapshots |
| `weekly_review_nudge()` | beat, per user's local Sunday evening | Create a draft reflection + notification record |
| `purge_deleted()` | nightly | Hard-delete accounts past grace period; purge expired sessions |

Requirements: tasks are **idempotent**, use exponential backoff on 429/5xx from Google, and set `calendar_connections.status='needs_reauth'` on `invalid_grant`. Use per-user locks (Redis) to avoid concurrent syncs.

---

## 7. Core algorithms (pure Python, heavily tested)

### 7.1 Duration calibration (planning-fallacy buffer)

```python
def duration_multiplier(history: list[tuple[int, int]],  # (planned_min, actual_min) for completed blocks
                        default: float = 1.3,
                        min_samples: int = 5) -> float:
    ratios = [a / p for p, a in history if p > 0 and a > 0]
    if len(ratios) < min_samples:
        return default
    ratios.sort()
    median = ratios[len(ratios) // 2]
    return max(1.0, min(2.0, median))
```

Apply to each action's estimate when computing how much time a week needs. Show the multiplier to the user in settings ("Your tasks tend to take 1.4x longer than planned") and let them override it.

### 7.2 Free-slot computation
Input: week range, `busy_intervals`, work days/hours (user tz), existing accepted blocks, buffer (default 10 min around events), minimum slot length (30 min).
Output: sorted list of free `Slot(start, end)` in UTC, with the local hour/weekday attached for scoring. Handle DST by doing arithmetic in the user's IANA timezone and converting to UTC at the end. **Write a DST-week test.**

### 7.3 Weekly quota per action
- `habit` / ongoing `project`: `weekly_minutes_target × duration_multiplier`
- finite `project`: `remaining_minutes / weeks_left_in_goal`, then × multiplier
- Sum quotas; if total exceeds available focus capacity (`daily_max_focus_minutes × work_days`), **do not silently drop**: reduce lowest-priority actions first and emit a `capacity_warning` with the dropped minutes.

### 7.4 Slot scoring and placement (greedy)

```
for action in actions sorted by (goal.priority desc, deficit desc, requires_deep_focus desc):
    need = quota[action]
    while need >= min_block:
        best = argmax over free slots of score(action, slot)
        block_len = clamp(preferred_block, min_block, min(max_block, slot.length, need))
        place block at slot (start aligned to :00/:30), split the slot remainder
        record reason string
        need -= block_len
```

`score(action, slot)` = weighted sum of:
- **Time-of-day fit** (action preference, else user's `energy_peak`; deep-focus work gets a heavier weight on the peak window)
- **Historical completion rate** for `(weekday, hour bucket)` for this user (default neutral until ≥ 10 samples)
- **Spread bonus** for habits (prefer different days; penalize two blocks of one habit on the same day)
- **Fragmentation penalty** (avoid leaving unusable slivers < min slot)
- **Anti-goal penalty**: user-defined blackout windows (e.g., "no work after 8pm") are hard exclusions, not penalties
- **Daily cap**: hard stop at `daily_max_focus_minutes`

Every placed block stores a human-readable `reason` ("Morning slot, you complete 80% of morning blocks"). The UI shows it.

### 7.5 Trajectory engine

```python
@dataclass
class Trajectory:
    goal_id: UUID
    status: Literal["on_track", "adjust", "off_track", "insufficient_data"]
    expected_fraction: float      # time-elapsed fraction, or milestone-weighted
    actual_fraction: float        # (metric_now - start) / (target - start), clamped 0..1.2
    effort_ratio: float | None    # focus minutes done / planned-to-date
    projected_finish: date | None
    reasons: list[str]            # deterministic, machine-generated

def compute(goal, checkins, focus_minutes_done, focus_minutes_planned_to_date, today) -> Trajectory:
    elapsed = (today - goal.start_date).days
    total = (goal.target_date - goal.start_date).days
    expected = clamp(elapsed / total, 0, 1)
    actual = clamp((latest_metric - goal.metric_start) / (goal.metric_target - goal.metric_start), 0, 1.2)
    if elapsed < 7 or not checkins:
        return insufficient_data(...)
    ratio = actual / expected if expected > 0 else 1.0
    status = "on_track" if ratio >= 0.9 else "adjust" if ratio >= 0.7 else "off_track"
    projected = goal.start_date + timedelta(days=elapsed / actual) if actual > 0 else None
    ...
```

Support `direction` (increase/decrease metrics), and milestone-based goals via weighted milestones. **The status is never decided by AI.** The coach receives the computed `Trajectory` plus recent data and produces explanations and suggestions only.

---

## 8. Google Calendar integration (narrowest scopes)

**Principle:** request the minimum, ask at the moment of need, and never read event titles.

| Need | Scope |
|---|---|
| Sign-in | `openid`, `email`, `profile` (non-sensitive) |
| Read availability (no event details) | `https://www.googleapis.com/auth/calendar.events.freebusy` |
| Create/manage our own calendar and its events | `https://www.googleapis.com/auth/calendar.app.created` |

- **Do not request** `calendar`, `calendar.events`, or `calendar.readonly`. If `freebusy.query` rejects `calendar.events.freebusy` in testing, the fallback is `calendar.freebusy`; verify against current Google docs during Milestone 3 and record the decision in `docs/ARCHITECTURE.md`.
- All Calendar scopes are in Google's *sensitive* tier, so a public launch requires **OAuth app verification** (privacy policy, homepage, scope justifications, demo video). While in "Testing" mode you can add up to 100 test users with no verification. Plan the verification submission in Milestone 8.
- **Flow:** `GET /calendar/connect` builds the consent URL with `access_type=offline`, `prompt=consent`, `include_granted_scopes=true`, and a signed `state`. The callback exchanges the code, stores tokens **encrypted**, creates the dedicated secondary calendar named "Kairos" (stores `app_calendar_id`), and enqueues `sync_busy`.
- **Free/busy source:** call `freebusy.query` for the user's `primary` calendar (and any additional calendar IDs the user selects in settings). Cache intervals only, never titles or attendees.
- **Write path:** accepted blocks become events in the app calendar only. Users see them overlaid in their normal Google Calendar. Set `extendedProperties.private.kairos_block_id` on each event for reconciliation.
- **Reconciliation:** `sync_app_calendar` uses `syncToken`. If the user drags a block in Google, update `time_blocks.start_at/end_at`, increment `moved_count`. If deleted, mark `cancelled`. Surface repeated moves to the coach ("rescheduled 3 times").
- **Disconnect:** revoke the token at Google, delete `busy_intervals`, keep the app calendar (offer to delete it).
- **Token security:** AES-GCM/Fernet with `TOKEN_ENCRYPTION_KEY`; never log tokens; rotate-key procedure documented in `docs/ARCHITECTURE.md`.
- **Personal Mode widens read scope** (event details for the calendar audit, Part II Section 24.1) by adding a read-only events scope. Also note: Google may expire refresh tokens after about 7 days for external apps left in "Testing" status. For a personal deployment, plan to set the consent screen to "In production" (unverified, single user) or otherwise handle re-auth gracefully. **Verify the current rule** when implementing M3.

---

## 9. AI layer

### 9.1 Provider interface

```python
class LLMProvider(Protocol):
    async def generate_structured(self, *, task: str, system: str, user: str,
                                  schema: type[BaseModel], max_tokens: int) -> BaseModel: ...
    async def stream_text(self, *, task: str, system: str, messages: list[Msg],
                          max_tokens: int) -> AsyncIterator[str]: ...
```

- `get_provider()` reads `LLM_PROVIDER`. Models come from env, never hardcoded.
- **Structured output:** Anthropic via tool-use with the Pydantic JSON schema; Gemini via its response-schema/JSON mode. Always **validate with Pydantic**; on failure, retry once with the validation error appended, then return a typed `AIUnavailable` error. The UI must degrade gracefully (manual path always works).
- Log every call to `ai_calls` (tokens, latency, status). Enforce **plan-based quotas** (Part III Section 34) before every call.

### 9.2 Tasks

| Task | Input | Output schema |
|---|---|---|
| `goal_refine` | rough goal text, optional deadline | `{outcome_statement, metric_name, metric_unit, suggested_target, clarifying_questions[]}` |
| `suggest_actions` | refined goal, available weekly hours | `{actions: [{title, kind, weekly_minutes, rationale}] (max 5)}` |
| `suggest_obstacles` | goal + actions | `{obstacles: [{risk, if_cue, then_response}] (max 5)}` |
| `weekly_review` | computed trajectories, focus stats, move counts, reflection notes | `{summary, wins[], risks[], suggestions: [{type, target_id, text, proposed_change?}]}` |
| `coach_chat` | conversation + compact user context | streamed text |

`proposed_change` is data the UI can apply with one click **after** user confirmation (e.g., "move block X to mornings"). The server validates it through the normal endpoints.

### 9.3 Prompt rules
- Prompts live in `api/app/ai/prompts/*.md`, versioned in git.
- User-provided text (goals, notes) is passed as **data inside delimiters**; the system prompt states it must not be treated as instructions.
- Send the minimum context: no emails, no calendar event details (we don't have them), no tokens.
- Tone: practical, concise, non-judgmental. No medical/clinical claims. No guilt language on missed blocks.
- Golden-file tests with a **fake provider** for deterministic CI; a small optional live-eval script (not in CI).

---

## 10. Frontend (React + Tailwind PWA)

### 10.1 Routes
```
/                    redirect -> /today or /welcome
/welcome             sign-in
/onboarding          GPS wizard (multi-step, resumable)
/today               today's blocks, active focus session, quick check-in
/plan                week view (FullCalendar timegrid), draft/review panel
/goals               list; /goals/:id detail (actions, obstacles, trajectory, check-ins)
/focus               focus timer + blocklist picker
/review              weekly reflection + AI summary
/coach               chat
/settings            profile, work hours, calendar, blocklists, extension pairing, data export/delete
```

### 10.2 GPS wizard (onboarding & new goal)
1. **Goal:** outcome, metric + target, date. AI "refine" is optional, never blocking.
2. **Why (3 Fs):** facts, feelings, function (three short text fields with examples).
3. **Anti-goals:** list of things to avoid / protect.
4. **Plan:** 1–5 actions (hard cap in UI and API). Show weekly time total vs. available capacity.
5. **Confidence check:** two sliders (confidence in the goal; likelihood of following the plan). If either < 80, show a gentle prompt to simplify (reduce actions or scope); user can proceed anyway.
6. **Obstacles:** top risks with if-then responses (AI suggestions optional).
7. **System:** pick preferred times, default block length, blocklist, calendar connect (skippable).

### 10.3 Plan review UX
- "Draft my week" calls `/plan/draft`; proposed blocks render in a distinct style with their `reason`.
- Per-block: keep / discard / drag to move / resize. Bulk "Accept all that remain".
- Show `capacity_warning` prominently if present.
- Accepting calls `/plan/accept`; show per-block publish status; handle partial failure with retry.

### 10.4 State & data
- TanStack Query for server state; minimal client state (Zustand) for the timer UI.
- Optimistic updates for drag/move with rollback on error.
- Times: store/transport ISO-8601 UTC; render in the user's timezone via `Intl`/`date-fns-tz`.

### 10.5 Design & accessibility
- Tailwind with a small token layer (`colors`, `spacing`, `radius`) in `tailwind.config.ts`; light/dark via `prefers-color-scheme` + manual toggle.
- WCAG 2.1 AA: keyboard operable calendar actions, visible focus, `aria-live` for timer milestones, color-independent status (icon + text).
- Mobile-first layouts; the week view collapses to a day view under 640px.

### 10.6 PWA
- `vite-plugin-pwa` with `registerType: 'prompt'` (show "Update available" toast).
- Manifest: name, short_name, icons (192, 512, maskable), `display: standalone`, `theme_color`, `start_url: /today`.
- Workbox: precache app shell; `StaleWhileRevalidate` for GET API reads of goals/blocks; **never cache** auth, mutation, or AI endpoints. Offline: show cached Today/Plan read-only with a banner; queue check-ins and focus-session end events in IndexedDB and replay on reconnect (background sync where supported, fallback on `online` event).
- Install prompt component; push notifications are **not** in MVP (stub the hook).
- Lighthouse PWA/performance/accessibility budget in CI: all ≥ 90.

---

## 11. Chrome extension (Manifest V3)

### 11.1 Purpose
During an active focus session, block the user's chosen domains and show the remaining time. Outside sessions it does nothing.

### 11.2 Manifest (essentials)

```json
{
  "manifest_version": 3,
  "name": "Kairos Focus",
  "version": "0.1.0",
  "action": { "default_popup": "popup/index.html" },
  "background": { "service_worker": "background.js", "type": "module" },
  "permissions": ["storage", "alarms", "declarativeNetRequest"],
  "optional_host_permissions": ["<all_urls>"],
  "web_accessible_resources": [{ "resources": ["blocked/index.html"], "matches": ["<all_urls>"] }],
  "externally_connectable": { "matches": ["https://YOUR_APP_DOMAIN/*", "http://localhost:5173/*"] }
}
```

- Prefer `declarativeNetRequest` dynamic rules over `webRequest` blocking (MV3).
- A plain `block` action needs no host access, but gives users a browser error page. A `redirect` to the extension's `blocked/index.html` page needs host access; request it **at runtime** via `optional_host_permissions` when the user first enables blocking, so the install prompt stays minimal. Verify current DNR host-permission behavior when implementing and record it in `docs/ARCHITECTURE.md`.

### 11.3 Pairing flow (no cookies in extension)
1. In web `/settings`, user clicks "Connect extension" → `POST /ext/pair` returns a 6-digit one-time code (TTL 5 min, single use).
2. In the extension popup the user enters the code → `POST /ext/pair/redeem` returns a long-lived bearer token (stored hashed server-side; in `chrome.storage.local` client-side).
3. Tokens are revocable from settings. Extension tokens can only call `/ext/*`.

### 11.4 Runtime behavior
- **Start/stop sync:** the web app sends `chrome.runtime.sendMessage(EXTENSION_ID, {type:'SESSION_START', sessionId, endsAt, domains})` (via `externally_connectable`). The service worker installs DNR rules and sets a `chrome.alarms` alarm for `endsAt`.
- **Resilience:** service workers sleep and restart. On every wake, call `GET /ext/state` to reconcile (rules must match server truth). Also re-check on `chrome.runtime.onStartup`.
- **End:** on alarm or `SESSION_END`, remove rules. If the server says no active session, remove rules.
- **Blocked page:** shows the active goal/action, time left, and two buttons: "Back to focus" and "End session early" (which calls the API and records it).
- **Rule IDs:** reserve a fixed ID range for our dynamic rules; always replace the full set atomically via `updateDynamicRules({removeRuleIds, addRules})`.
- **Rule shape:**

```ts
{ id: 1000 + i, priority: 1,
  action: { type: 'redirect', redirect: { extensionPath: '/blocked/index.html?d=' + encodeURIComponent(domain) } },
  condition: { requestDomains: [domain], resourceTypes: ['main_frame'] } }
```

- **Privacy:** the extension never reads page content or browsing history; it only counts blocked-navigation events per domain (sent to `/ext/event`).
- Provide an options page for the default blocklist and a "pause 5 minutes" escape hatch (logged).

### 11.5 Packaging
Build to `extension/dist`; `make ext-zip` produces a Chrome Web Store upload. Document the store listing requirements (privacy policy URL, single-purpose description, permission justifications) in `docs/PRIVACY.md`.

---

## 12. Security, privacy, compliance

- HTTPS only outside dev; HSTS; strict CSP on the web app (no inline scripts; `connect-src` limited to the API).
- Validate all input with Pydantic; parameterized queries only (SQLAlchemy).
- Enforce row ownership in a shared repository layer; add tests that user A cannot read user B's objects on every router.
- Secrets only via env; no secrets in logs; scrub PII from error reports.
- **Data minimization:** only free/busy intervals are stored from Google. No event titles/attendees/locations. *(Applies to the standard build. In Personal Mode, Section 28 overrides this for locally stored data.)*
- **User rights:** `GET /me/export` (JSON), `DELETE /me` (immediate token revoke + deletion within a grace window).
- AI: disclose in the privacy policy that goal text and computed stats are sent to the chosen provider; allow users to disable AI features (app still fully usable).
- Dependency scanning (`pip-audit`, `npm audit`) in CI; pin versions; Dependabot enabled.
- Rate limiting and basic abuse protection on public endpoints.

---

## 13. Observability

- Structured JSON logs with request IDs; Celery task logs include `user_id` (hashed) and task name.
- Error tracking hook (Sentry-compatible) behind an env flag.
- Metrics: sync success rate, publish failures, AI latency/validation-failure rate, active sessions. Expose `/healthz` (liveness) and `/readyz` (DB + Redis).

---

## 14. Testing strategy

**Unit (must be exhaustive):** scheduler (empty week, full week, DST transition week, overlapping busy intervals, capacity overflow, daily cap, anti-goal blackouts, determinism: same input → same output), duration calibration, trajectory edge cases (zero range, decreasing metrics, no check-ins), encryption round-trip.

**Integration:** each router with an authenticated test client; ownership isolation; Google client mocked with recorded fixtures (no live calls in CI); Celery tasks with eager mode; idempotent publish (run twice → no duplicate events).

**AI:** fake provider returning fixtures; tests for invalid-JSON retry, rate-limit enforcement, and graceful degradation.

**Frontend:** component tests for the wizard (hard cap of 5 actions, confidence prompt), plan review interactions, timer logic.

**E2E (Playwright):** sign-in (mock OIDC) → wizard → draft week → accept → start/end focus session → trajectory updates. Run in CI against Docker Compose.

**Extension:** unit tests for rule generation; manual QA checklist in `extension/QA.md` (service-worker restart mid-session, multiple windows, session ending while offline).

CI (GitHub Actions): lint (ruff, eslint), types (mypy, tsc), unit + integration, e2e, Lighthouse, build extension.

---

## 15. Milestones (execute in order)

Each milestone: implement → tests → update docs → demo script in `docs/DEMO.md`.

*Part II adds M10–M17 (Section 29). Start them only after M9 is complete.*

### M0: Foundation
- Monorepo, Docker Compose, CI, linting, `/healthz`, Alembic baseline, generated TS client pipeline, Tailwind + base UI kit.
- **Done when:** `make dev` starts everything; CI green on an empty feature.

### M1: Auth & profile
- Google OIDC sign-in **and magic-link sign-in**, account linking by verified email, sessions (list/revoke), CSRF, roles (`owner`/`admin`/`user`), `SIGNUP_MODE`, owner seeding, `/me`, settings (timezone, work hours), account export/delete, minimal `/admin` (users, plans, invites). Full spec: Part III Sections 33-34.
- **Done when:** a user can sign in/out, edit work hours, delete account; ownership-isolation test harness exists.

### M2: Goals domain & GPS wizard
- Seasons, goals, actions (cap 5), obstacles, check-ins; wizard UI with confidence prompt; goals list/detail.
- **Done when:** a goal with 3 actions and 2 obstacles can be created, edited, paused; cap enforced at API and UI.

### M3: Calendar read (free/busy)
- Google connect flow (`calendar.events.freebusy`), encrypted tokens, `sync_busy` job, `/calendar/status`, disconnect, needs-reauth handling.
- **Done when:** after connecting, busy intervals appear in the DB within a minute; disconnect purges them; scope decision recorded.

### M4: Scheduler & plan review
- Pure scheduler with full unit tests; `/plan/draft`; week UI with accept/discard/move; `capacity_warning`.
- **Done when:** draft is deterministic, respects busy time/work hours/caps, every block has a reason; works with calendar not connected (manual busy input).

### M5: Calendar write & reconciliation
- Add `calendar.app.created`; create "Kairos" calendar; `publish_blocks`; `sync_app_calendar` with sync tokens; moved/deleted detection.
- **Done when:** accepted blocks show in Google; dragging one in Google updates the app within the sync interval; publish is idempotent.

### M6: Focus sessions & trajectory
- Focus timer, session logging, self-rating, stats; trajectory engine + UI; duration calibration feeds the scheduler.
- **Done when:** completing sessions changes trajectory and next week's draft multiplier (with ≥5 samples).

### M7: AI coach
- Provider abstraction (Anthropic + Gemini), the five tasks, SSE chat, `ai_calls` logging, quotas, one-click apply of validated suggestions, AI-off mode.
- **Done when:** all AI features work with the fake provider in CI and with a live key locally; disabling AI leaves the app fully usable.

### M8: PWA & hardening
- Manifest, service worker, offline reads, queued writes, install prompt, Lighthouse budgets; security headers; rate limits; Google OAuth verification package (privacy policy page, scope justification doc, demo script).
- **Done when:** installable on desktop and Android Chrome; offline Today view works; Lighthouse ≥ 90.

### M9: Chrome extension
- Pairing, DNR rules, blocked page, state reconciliation, web↔extension messaging, options page, Web Store package.
- **Done when:** starting a session in the web app blocks listed domains within 2 s, ends on time even after service-worker restart, and QA checklist passes.

---

## 16. Extension points (for the owner's custom features)

Keep these seams so new features don't touch the core:

- **Feature modules:** backend `app/features/<name>/{models,schemas,router,service}.py`, auto-registered; frontend `web/src/features/<name>/` with a route entry in `router.tsx`.
- **Scheduler hooks:** `ScoringRule` protocol, so custom rules (e.g., energy tracking, travel time) can add terms to `score()` without editing core code.
- **AI tasks:** add a file in `ai/tasks/` + prompt in `ai/prompts/`; register in a task registry.
- **Events:** emit domain events (`block_completed`, `goal_status_changed`, `session_ended`) through a tiny internal dispatcher so features can subscribe.
- **Feature flags:** simple table or env-driven flags for staged rollout.

Record planned custom features in `docs/ROADMAP.md` before building them.

---

## 17. Definition of done (global)

- All acceptance criteria for the milestone met; no TODOs left without a linked issue.
- Lint, types, unit, integration, and e2e pass in CI.
- New endpoints appear in OpenAPI and the TS client is regenerated.
- Ownership and error-shape tests cover new routes.
- Docs updated (`ARCHITECTURE.md`, `PRIVACY.md` if data handling changed, `OPEN_QUESTIONS.md`).
- No secrets, tokens, or personal data in logs or fixtures.

---

## 18. Decisions and open questions

**Decided** (details in Part III Section 32):
- Product name: **Kairos**.
- Users: the owner is the only user today, but the app has real user management (Google + magic link, roles, signup control).
- Pricing: none yet; **AI usage is gated by plan**, with no billing code.
- Hosting: **Render** with managed Postgres and Key Value.
- Magic-link email login ships at launch alongside Google.

**Still open:** custom domain, email provider, Render region, plan names/limits, Chrome Web Store account, and the Part II questions (Section 31). Part III Section 38 consolidates them.

---

## 19. First instruction to the agent

> Start with **M0**. Create the repository structure in Section 3, `docker-compose.yml`, `.env.example`, CI workflow, and a minimal FastAPI app with `/healthz`, a React + Tailwind shell, and the OpenAPI → TypeScript client generation step. Write `docs/ARCHITECTURE.md` capturing the decisions in Section 0. Stop after M0's acceptance criteria are met and summarize what you built and any deviations.

---
---

# PART II: Personal Mode Extensions (personal-productivity features, local-first data handling)

These features turn the product into a **personal operating system for one person**. They are built **after M9**. They reuse Part I's data model, scheduler, trajectory engine, AI layer, and extension.

## 20. Personal Mode (feature set and flags)

*Updated by Part III: the app is hosted on Render and has real user management. "Personal Mode" now means the personal-productivity feature set below, not a separate single-user build.*

**Config**

```
SEASON_LENGTH_WEEKS=12
WEEK_STARTS_ON=monday
FEATURES=capture,hosts_block,dnd,slack,home_env,activity_log,calendar_audit,retro,intervention
```

Rules:
- **`user_id` on every table** is now actually used; all queries are scoped by it. Signup is controlled by `SIGNUP_MODE` (default `closed`; see Part III).
- **Feature flags** (`FEATURES`) are global switches; a user's **plan** (Part III Section 34) can further restrict which features they may use. Every Part II feature degrades cleanly when off.
- **Local-first data handling.** Because the API is public on Render, sensitive raw data stays on the user's machine: the companion keeps raw window titles in its local encrypted database and uploads only classified, title-less segments (Section 23.3, Part III Section 36).
- **Secrets.** Platform secrets live in Render environment groups. Per-user integration credentials (e.g., a Slack token) are stored **encrypted per user** server-side (Part III Section 36). Companion-only secrets (helper socket secret, Home Assistant token) live in the OS keychain. Nothing is committed; a secret scanner runs in pre-commit and CI.

## 21. Architecture with the desktop companion

A browser tab cannot register an OS-wide hotkey, edit the system `hosts` file, toggle Do Not Disturb, or read the foreground window. Those need a **local companion**.

```
 Browser PWA ──────────┐
 Chrome extension ─────┼──► FastAPI ──► Postgres / Redis / Celery
 Companion (Tauri) ────┘        ▲
      │  local socket            │ Slack / Calendar APIs (server-side jobs)
      ▼
 Helper (privileged, hosts file only)
```

**Companion app (`companion/`, Tauri v2)**: unprivileged, runs at login, lives in the tray. Responsibilities:

| Capability | Notes |
|---|---|
| Global hotkey → capture bar | Tauri global-shortcut plugin; configurable key combo |
| Local SQLite outbox | Offline-safe capture; syncs to API |
| Focus-session effects | Executes local effects (hosts block via helper, DND, smart-home scene) |
| Active-window logger | Foreground app + title, idle detection |
| Intervention overlay | Always-on-top window (Section 24.3) |
| Server link | Pairs like the extension (code → bearer token). `GET /companion/state` on start and reconnect; `GET /companion/stream` (SSE) for live events (`session_start`, `session_end`, `intervention`) |

**Helper (`helper/`)**: a small privileged service (launchd daemon on macOS, Windows service, systemd unit on Linux) that does **one thing**: add/remove a sentinel-delimited block in the hosts file. See Section 23.1 for its constraints. The companion talks to it over a local-only socket authenticated with a secret created at install time.

**Primary OS is an open question** (Section 31). Implement behind an `OsAdapter` interface (`set_dnd`, `foreground_window`, `idle_seconds`, `flush_dns`, `lock_overlay_support`) with macOS and Windows implementations first and Linux best-effort. Wayland on Linux restricts reading other apps' windows; document this limitation.

**Hosted API note.** The companion and extension talk to the **hosted API over HTTPS** (`API_BASE_URL`), not to localhost. Design for that: the capture outbox tolerates API downtime and Render cold starts; `/companion/stream` (SSE) must reconnect with backoff and fall back to polling `/companion/state` every 60 s; LAN-only effects (Home Assistant) run in the companion because the cloud server cannot reach your LAN.

**Focus orchestration (server side).** On `/focus/start`, the API creates one `session_effects` row per enabled effect for the chosen **focus profile** and publishes them to the companion and extension. Rules:
- Effects are independent. **A failing effect never blocks the session**; it reports `failed` with an error.
- `teardown` is idempotent and always attempted on end, on timeout, and on companion startup if no active session exists.
- Cloud-reachable effects (Slack/Teams) run as Celery jobs; local/LAN effects (hosts, DND, Home Assistant) run in the companion.

**Focus profiles** let different work types trigger different effects (e.g., *Deep work*: hosts block + DND + lights + playlist; *Admin*: DND only). Each block/action can reference a profile.

---

## 22. Phase 1: Clarity & Planning

### 22.1 Fixed 12-week seasons
- `SEASON_LENGTH_WEEKS=12` is a constant, not a form field. `create_season(start_date)` aligns the start to `WEEK_STARTS_ON`, sets `end_date = start + 12 weeks - 1 day`, and rejects any other length.
- Only one `active` season at a time. At week 11, propose the next season and a carry-over list (unfinished goals).
- Helper `week_index(season, date) -> 1..12`, used by milestones, trajectory, and reflections.
- Season-end flow: auto-generate a season retrospective (Section 24.2) and archive the season.

### 22.2 AI milestone parser (velocity-aware)

**Goal:** turn a vague goal into 12 weekly milestones that respect the user's *measured* pace.

1. **Velocity (pure Python, `services/velocity.py`):**
   - `weekly_focus_capacity`: median completed focus minutes per week over the trailing 4 weeks (fallback: planned capacity from work hours × 0.5 when fewer than 3 weeks of data).
   - `block_completion_rate`: completed / accepted blocks, trailing 4 weeks.
   - Per goal: median weekly metric delta and median weekly minutes spent.
   - `confidence`: `high` (≥ 4 weeks of data), `medium` (2–3), `low` (< 2). Low-confidence output is labeled in the UI.
2. **LLM call** (`POST /coach/milestones/parse`): input is the goal text (or `goal_id`), `season_id`, and the velocity summary. Output schema:

```python
class Milestone(BaseModel):
    week_index: int            # 1..12
    title: str
    metric_target_value: float
    estimated_minutes: int
    rationale: str

class MilestonePlan(BaseModel):
    milestones: list[Milestone]    # one per week, 12 max
    assumptions: list[str]
    feasibility_notes: list[str]
```

3. **Deterministic validation after the LLM:** exactly one milestone per week index ≤ 12; metric values progress monotonically toward the target and the final week reaches it (within tolerance); each week's `estimated_minutes` ≤ `weekly_focus_capacity × 1.15`, else mark that week `stretch`; total minutes across goals ≤ capacity × 12. On failure, retry once with the validation errors appended, then return the plan with flags instead of silently fixing it.
4. **User review:** show an editable table; nothing is saved until the user confirms.
5. **Downstream use:** saved `milestones` drive the scheduler's quota for finite projects (Section 7.3) and the milestone-weighted `expected_fraction` in the trajectory engine (Section 7.5).
6. **Providers:** add an optional **OpenAI adapter** to the provider interface alongside Anthropic and Gemini (`LLM_PROVIDER=openai`). Same structured-output + Pydantic-validation contract.

### 22.3 One-key fast capture
- **Companion:** global hotkey (default `Ctrl/Cmd+Shift+Space`, configurable) opens a small borderless always-on-top window with a focused text input. `Enter` saves and closes; `Esc` cancels. Target: window visible in under ~150 ms.
- **Quick syntax (parsed client-side, unit-tested):** `#goal-slug` assigns a goal, `@25m` sets an estimate, `!1`..`!3` sets priority. Everything else is the title. Unparsed tokens stay in the title.
- **Offline-first:** write to the local SQLite `capture_outbox` with a client-generated UUID, then sync via `POST /tasks/capture` (idempotent on that UUID). Retry with backoff.
- **Fallbacks:** web route `/capture` (PWA), and a `chrome.commands` shortcut in the extension that opens a capture popup when the companion isn't running.
- **Inbox triage (web `/inbox`):** assign to goal/action, schedule into a block, split, or delete. Untriaged items older than 3 days are highlighted.

---

## 23. Phase 2: Focus & Execution

### 23.1 Hosts-file shifter (privileged helper)
Blocks distraction sites system-wide (all browsers and apps) during sessions.

**Helper contract:** only these commands, over an authenticated local socket:
- `block(domains[], until_ts)`: writes a block delimited by `# >>> KAIROS BEGIN` / `# <<< KAIROS END`, mapping each domain (plus `www.` variant) to `127.0.0.1` and `::1`; flushes the DNS cache.
- `unblock()`: removes only that sentinel block.
- `status()`.

**Safety requirements (all mandatory):**
1. The helper **never edits anything outside the sentinel block** and validates domains against a strict hostname regex (no whitespace, newlines, or wildcards).
2. **Self-expiry:** the helper stores `until_ts` locally and removes the block itself when it passes, even if the API or companion is dead. Maximum block duration cap (default 4 h).
3. **Crash recovery:** on helper start, expire stale blocks. On system boot, same.
4. Back up the original hosts file once (`hosts.kairos.bak`); write atomically (temp file + rename).
5. **User escape hatch:** a tray item and a CLI command (`kairos-helper unblock`) that always work without the API.
6. The helper accepts commands only from the companion's secret; it opens no network port.
7. Never block domains on a user-maintained **allowlist** (e.g., the app's own domain, calendar, work tools).
8. Tests use a **temporary hosts file path**; the real file is never touched in CI.

Notes: browsers may cache DNS or use encrypted DNS, so the extension's `declarativeNetRequest` rules (M9) remain the primary in-browser layer; the hosts block covers other apps. Verify behavior per OS/browser and document it.

### 23.2 OS and workplace automations
Implemented as **adapters** under a common `Effect` interface (`apply(session)`, `teardown(session)`), each flag-gated and independently failing.

| Effect | Where it runs | Approach |
|---|---|---|
| **Do Not Disturb** | Companion (`OsAdapter.set_dnd`) | macOS: run a user-created Shortcut (`shortcuts run "Kairos Focus On/Off"`) because there is no public toggle API. Windows: best-effort (Focus Assist has no stable official API; implement behind the interface and document limits). Linux/GNOME: `gsettings` notification banners. **Verify each per OS version.** |
| **Slack** | Server job | Personal user token. Set a status text/emoji **with an expiration** (auto-clears if teardown fails) and set snooze (`dnd.setSnooze`) for the session length; teardown ends snooze and clears status. Required scopes are minimal (profile write, dnd write); document them. |
| **Teams** | Server job, *optional/late* | Microsoft Graph presence APIs; work/school accounts may require admin consent. Treat as best-effort and only build if actually needed (Section 31). |

Tokens are read from the keychain/env and **never logged**. Each effect writes its result to `session_effects`.

### 23.3 Active-window logger
- Companion samples the foreground app and window title every **2 s** and idle seconds from the OS. A segment is closed when app/title changes or idle > 5 min (idle segments are stored as `idle`).
- **Browser tab titles/domains** come from the extension (it needs the `tabs` permission and is **off by default in incognito**) because OS window titles for browsers are noisy and lose the domain. The extension sends `{domain, title_hash_or_title, ts}` to the companion/API only when logging is on.
- Segments are merged (same app + title + contiguous) to keep storage small. **Classification against `app_rules` happens inside the companion**, using raw titles held in its local encrypted DB. Only **title-less** segments (`app_name`, `domain`, `category`, times) are batched to `POST /activity/segments`. Rules are authored in the web app and synced down to the companion.
- **Rules table (`app_rules`)** maps patterns (app name, title regex, domain) → category (`productive` | `neutral` | `distraction`), optionally tied to an `action_id` so "VS Code" counts as on-task only for the coding action. Rules are user-editable with a "test this rule against my last 7 days" preview.
- **Controls:** a pause hotkey and tray toggle ("Pause logging"), a built-in exclusion list (password managers, banking, private windows), and a one-click "delete today's activity".
- **Retention:** raw titles kept for `ACTIVITY_RAW_RETENTION_DAYS` (default 30), then reduced to app/domain/category aggregates.

### 23.4 Smart-home environment trigger
- **Single integration: Home Assistant REST API** (long-lived access token in keychain) rather than one adapter per vendor. Users keep their lights/speakers in HA.
- A focus profile references an HA **scene** or **script** to run on start and another on end (e.g., `scene.deep_work`, `scene.normal`), plus an optional media-player entity and playlist/URI.
- Runs in the companion (LAN access). Timeouts of 3 s; failures reported, never blocking.
- Optional later: Spotify Web API playback directly (requires an active device and a Premium account); skip unless HA media control isn't enough.

---

## 24. Phase 3: Alignment & Auditing

### 24.1 Bi-directional calendar audit and focus-efficiency score

**Data in.** Add a read-only events scope for the audit (`calendar.events.owned.readonly` preferred over `calendar.events.readonly` or `calendar.readonly`; verify availability and tier in current Google docs). Keep `calendar.app.created` for writes. A job `sync_events` caches events into `calendar_events_cache` (id, start, end, title (encrypted; stored only if `STORE_EVENT_TITLES=true`, default off), is_meeting, attendee_count, response_status, calendar_id). `is_meeting` = has other attendees or conferencing link. **Apple Calendar** is a later adapter behind a `CalendarSource` interface (CalDAV, or EventKit via the macOS companion).

**Efficiency formula (pure, `services/efficiency.py`):**

```
for each focus block B (accepted/published/completed) in the period:
    meeting_overlap = minutes of B overlapping accepted meetings
    available       = planned_minutes(B) - meeting_overlap      # meetings win; flagged as 'conflict'
    on_task         = minutes of B overlapping activity segments with
                      category == 'productive' AND (rule.action_id is None OR rule.action_id == B.action_id)
                      excluding idle
    drift[category] = minutes of B in other categories

efficiency = sum(on_task) / sum(available)        # 0..1, None if denominator is 0
```

Also report separately (not added to the score): `unplanned_productive_minutes` (productive time outside blocks), `conflict_minutes`, and top drift apps/domains. Document in the UI that this is a **proxy**, because deep thinking away from the screen is not captured.

**UI:** a day/week timeline with three lanes (planned blocks, calendar events, actual activity), an efficiency trend, and a "why was this low" drilldown listing the largest drift segments.

### 24.2 Hyper-contextual retrospectives

**Inputs**
1. **`personal_profile`**: a user-editable Markdown document (habits, known weaknesses, triggers, what has worked before, how you want to be coached). Versioned; the latest version is injected into the system prompt.
2. **Deterministic stats** for the week and trailing 4 weeks: trajectories, efficiency, completion rate, postpone events (by weekday, time of day, goal, task category), top drift categories, intervention history.
3. **Prior commitments**: last week's AI-suggested changes the user accepted; the retrospective must report whether they were followed.

**Privacy gate (mandatory):** raw window titles, event titles, and URLs **never leave the machine**. Before any LLM call, build a **redacted summary**: aggregates by category/app/domain-category, counts, and durations, with identifiers replaced by labels. Run the redactor (emails, URLs/query strings, numbers that look like IDs, names from a denylist) over any free text the user wrote. Unit-test it with property-style tests. Provide a setting to preview exactly what will be sent.

**Output schema**
```python
class Retro(BaseModel):
    summary: str
    patterns: list[str]                 # grounded in provided stats only
    wins: list[str]
    commitments_review: list[dict]      # {commitment, status, evidence}
    suggestions: list[dict]             # {type, target_id, text, proposed_change?}
    next_week_focus: str
```

Rules: the model may only cite numbers present in the input; post-validate that quoted figures exist in the stats payload, else regenerate once. Tone follows the profile. A weekly Celery job drafts it Sunday evening (local time); the user edits and saves it into `weekly_reflections`.

### 24.3 Aggressive repetition interventions

**What counts as a postponement:** a task's scheduled block is skipped or moved after being accepted, or the user taps "later" on it. Each event is recorded in `postpone_events` and increments `tasks.postpone_count`.

**Trigger:** `postpone_count > INTERVENTION_POSTPONE_THRESHOLD` (default 3, so the 4th postponement). A task enters `needs_split`.

**Flow (state machine, unit-tested):**
`needs_split → overlay_shown → steps_submitted → resolved` (or `bypassed` / `timed_out`).

1. The companion shows a **full-screen, always-on-top overlay on all displays** (web fallback: a blocking modal in the PWA) naming the task and how many times it was postponed.
2. The user must enter **at least 2 micro-steps, each estimated ≤ 5 minutes**. A "suggest a split" button calls the AI (optional; user edits). Validation is deterministic: no empty steps, each estimate ≤ 5.
3. On submit: create `task_steps`, reset `postpone_count`, and schedule the **first step** into the next free slot (small block), then dismiss the overlay.

**Safety rules (mandatory; this feature must never trap the user):**
- It is an **application overlay, not an OS lock.** It must never interfere with the OS login/lock screen, volume, or emergency access.
- **Escape hatch:** hold a visible "Not now" button for 10 seconds, or type a short phrase. It logs a `bypassed` event, snoozes the task for 2 hours, and is limited to 3 bypasses/day (then the overlay is shown as a dismissible banner instead).
- **Hard time cap:** auto-dismiss after 15 minutes and snooze.
- **Never show** during a calendar event marked as a meeting, while a focus session is mid-flow (queue it for the session end), outside the user's work hours, or more than once per 2 hours.
- Fully configurable (threshold, cooldowns) and fully disable-able via `FEATURES`.

---

## 25. Data model additions

```
tasks
  id, user_id, goal_id (nullable), action_id (nullable), title, notes,
  estimate_minutes (nullable), priority (1-3), status ('inbox'|'todo'|'doing'|'done'|'dropped'|'needs_split'),
  postpone_count (int default 0), client_uuid (unique, for idempotent capture),
  source ('companion'|'web'|'extension'), captured_at, completed_at

task_steps
  id, task_id, user_id, title, estimate_minutes (CHECK <= 5), position, done_at

postpone_events
  id, user_id, task_id, time_block_id (nullable), reason ('skipped'|'moved'|'later'), occurred_at

milestones
  id, goal_id, user_id, season_id, week_index (1..12), title, metric_target_value,
  estimated_minutes, status ('planned'|'done'|'missed'), flag ('ok'|'stretch'), rationale

focus_profiles
  id, user_id, name, effects (jsonb)     # e.g. {hosts:true, dnd:true, slack:true, ha_scene:"scene.deep_work", ...}
  block_domains (text[]), allow_domains (text[]), default_minutes

session_effects
  id, focus_session_id, effect, status ('pending'|'applied'|'failed'|'reverted'),
  error, applied_at, reverted_at

activity_segments
  id, user_id, started_at, ended_at, source ('os'|'browser'), app_name,
  domain (nullable),                       -- raw titles stay in the companion's local DB, never uploaded
  category ('productive'|'neutral'|'distraction'|'idle'|'unclassified'),
  rule_id (nullable)
  index (user_id, started_at)

app_rules
  id, user_id, match_type ('app'|'title_regex'|'domain'), pattern, category, action_id (nullable), priority

calendar_events_cache
  id, user_id, google_event_id, calendar_id, start_at, end_at, title_enc (nullable; off by default),
  is_meeting (bool), attendee_count, response_status, updated_at

personal_profile
  id, user_id, version, markdown, created_at           # append-only versions

intervention_events
  id, user_id, task_id, outcome ('resolved'|'bypassed'|'timed_out'), shown_at, resolved_at

companion_devices
  id, user_id, name, os, token_hash, created_at, last_seen_at, revoked_at
```

Also: `time_blocks.task_id` (nullable FK); `weekly_reflections.ai_summary` stores the `Retro` JSON; `extension_tokens` gains `kind` ('extension'|'companion') or is replaced by `companion_devices` for the companion.

## 26. API additions (under `/api/v1`)

```
Tasks / capture
  POST  /tasks/capture                (idempotent on client_uuid)
  CRUD  /tasks                         POST /tasks/{id}/postpone    POST /tasks/{id}/split
  GET   /inbox

Seasons / milestones
  POST  /seasons                       (length fixed by config)
  POST  /coach/milestones/parse        CRUD /milestones
  GET   /velocity

Focus orchestration
  CRUD  /focus-profiles
  GET   /focus/{id}/effects            POST /focus/{id}/effects/{effect}/retry

Companion
  POST  /companion/pair  |  POST /companion/pair/redeem
  GET   /companion/state  |  GET /companion/stream (SSE)
  POST  /activity/segments  |  DELETE /activity?from&to  |  CRUD /app-rules
  POST  /companion/effects/{effect}/report

Audit & retrospectives
  GET   /audit/efficiency?from&to      GET /audit/timeline?date=
  GET   /profile   PUT /profile
  POST  /retro/generate                GET /retro/preview-payload   # shows exactly what would be sent to the LLM
  GET   /interventions                 POST /interventions/{task_id}/resolve|bypass
```

## 27. Background jobs additions

| Task | Trigger | What it does |
|---|---|---|
| `sync_events(user_id)` | every 15 min + on demand | Cache calendar events for audit (Section 24.1) |
| `slack_apply/teardown(session_id)` | session start/end | Status + snooze with expiration |
| `compact_activity()` | nightly | Merge segments, apply retention (raw → aggregates) |
| `nightly_efficiency()` | nightly | Precompute daily efficiency snapshots |
| `weekly_retro_draft()` | Sunday evening local | Build redacted payload, call LLM, store draft |
| `intervention_scan()` | every 5 min | Find tasks over the threshold, check cooldown/meeting/work-hours rules, push `intervention` event |
| `effects_watchdog()` | every minute | Revert any effect whose session has ended or expired (belt and braces) |

## 28. Security & privacy for Personal Mode

This section **overrides** Section 12's data-minimization line for locally stored data. The principle changes to: *collect more locally, send almost nothing off the machine, and keep everything deletable.*

| Risk | Required mitigation |
|---|---|
| Privileged helper abuse | Single-purpose command set, sentinel-only edits, strict domain validation, local-socket auth, no network listener, self-expiry, documented uninstall |
| Window/tab titles are sensitive | Encrypt `title_enc` at rest, exclusion list, pause hotkey, private windows excluded, retention job, one-click delete; extension logging off by default in incognito |
| LLM data egress | Redacted aggregates only, payload preview (`/retro/preview-payload`), setting to disable LLM features, no raw titles or event titles ever in prompts |
| API keys and credentials | Render env groups for platform secrets; per-user integration credentials encrypted at rest; companion secrets in OS keychain; never logged or committed; secret scanner in pre-commit and CI |
| Screen overlay | Not an OS lock, escape hatch, time cap, meeting/work-hours suppression, bypass logging |
| Local database | Companion SQLite encrypted (SQLCipher or OS-protected storage) holds raw window titles; managed Postgres (Render) holds only title-less activity, encrypted credentials, and app data; confirm backup encryption in the chosen Render plan |
| Public exposure | API is public on Render: closed signups by default, rate limits on auth and AI routes, strict CORS, HSTS, admin routes role-checked, no PII in logs |

## 29. Milestones (Part II)

Each follows the Section 15 workflow. All features are flag-gated.

### M10: Personal Mode & fixed seasons
- Feature flags (`FEATURES`) + per-plan feature entitlements, keychain/env secret loading, pre-commit secret scan; fixed 12-week seasons with `week_index` and next-season proposal.
- **Done when:** disabled features return a clean "not enabled" response; creating a season with any length other than 12 weeks is rejected; flags disable features cleanly.

### M11: Velocity & AI milestone parser
- `services/velocity.py`, `milestones` table, OpenAI adapter, parse endpoint, deterministic validation, editable review UI.
- **Done when:** with fixture history the parser output passes validation or returns flagged weeks; saved milestones feed the scheduler quota and trajectory; low-confidence labeling works.

### M12: Companion shell, pairing, fast capture, inbox
- Tauri app (tray, autostart), pairing, `GET /companion/state` + SSE, global hotkey capture bar, local outbox, `/tasks/capture`, inbox triage UI, `chrome.commands` fallback.
- **Done when:** hotkey capture works from any app, offline capture syncs after reconnect exactly once, and quick-syntax parsing tests pass.

### M13: Privileged helper & focus orchestration
- Helper service + installer/uninstaller, hosts shifter with all Section 23.1 safety rules, `focus_profiles`, `session_effects`, orchestrator, `effects_watchdog`.
- **Done when:** starting a session blocks listed domains system-wide; the block self-removes at expiry even with the API and companion killed; the helper test suite passes against a temp file; the escape hatch works.

### M14: Automations
- `OsAdapter.set_dnd` (primary OS first), Slack effect with status expiration, Home Assistant scene/media effect, per-effect retry UI. Teams only if requested.
- **Done when:** a session start/end toggles DND, Slack, and the HA scene; any single effect failing leaves the others and the session working; teardown always runs.

### M15: Activity logger & rules
- OS logger with idle detection, browser source via extension, segment merging, `app_rules` with preview, pause/exclusion/delete controls, retention job.
- **Done when:** a day of activity is logged within storage budget, categories apply per rules, pause and delete work, and incognito/excluded apps are never logged.

### M16: Calendar audit & efficiency score
- Events scope + `sync_events`, `calendar_events_cache`, `services/efficiency.py` with fixtures, timeline UI, trend and drilldown.
- **Done when:** the efficiency formula matches hand-computed fixtures (including meeting conflicts, idle, and multi-action rules) and the timeline overlays three lanes correctly.

### M17: Retrospectives & interventions
- `personal_profile` editor, redactor with tests, payload preview, weekly retro job with commitments review and figure-grounding check; postpone tracking, intervention state machine, companion overlay with all safety rules, web fallback.
- **Done when:** the LLM payload contains no raw titles/URLs (verified by tests and preview); a task postponed past the threshold triggers the overlay only when suppression rules allow; the escape hatch, time cap, and daily bypass limit all work.

## 30. Testing additions

- **Helper:** temp-file tests for block/unblock idempotency, sentinel-only edits, malicious domain strings, expiry, crash-restart recovery. **Never run against the real hosts file in CI.**
- **Orchestrator:** effect isolation (one failing effect), teardown idempotency, watchdog reverts stale effects.
- **Intervention state machine:** every transition, cooldowns, meeting/work-hours suppression, bypass limits, hard cap.
- **Efficiency:** fixture-driven (meeting overlap, idle, multi-category, rule precedence).
- **Redaction:** property-style tests that no email/URL/ID-like string survives into the payload.
- **Milestone parser:** fake provider returning valid, invalid, and over-capacity plans; verify retry and flagging.
- **Capture:** quick-syntax parser table tests; outbox idempotency (replay the same UUID twice).
- **Manual OS matrix** in `companion/QA.md`: hotkey registration, DND per OS, helper install/uninstall, overlay on multiple displays, sleep/wake behavior.

## 31. Open questions (Part II)

1. **Primary OS** (macOS, Windows, Linux)? It decides the first `OsAdapter` and DND approach.
2. Do you actually use **Teams**, or is Slack enough?
3. Is **Apple Calendar** required, or is Google enough for the audit?
4. Do you run **Home Assistant** (or will you)? If not, which smart-light/speaker brand, so a direct adapter can be scoped.
5. ~~Remote access~~ **Resolved:** the app is hosted on Render (Part III Section 35).
6. Which LLM provider should be default for retrospectives, given they use your most personal summaries?
7. Should the intervention threshold count only skipped/moved blocks, or also "later" taps on inbox items?

---
---

# PART III: Product Decisions (Auth, Plans, Hosting)

This part records decisions made after Parts I and II were written. **Where it conflicts with an earlier section, this part wins.** Earlier sections have been edited to point here.

## 32. Decisions log

| # | Decision | Consequences for the build |
|---|---|---|
| 1 | Product name is **Kairos** | Use it in UI copy, package names, extension name, email templates. Do a trademark/domain check before any public marketing. |
| 2 | The owner is the only user today, but the app needs **proper user management with Google sign-in** | Build real multi-user-capable auth, roles, sessions, and an admin screen. Default `SIGNUP_MODE=closed`, owner seeded, invites optional. The "single-user" shortcuts in Part II are removed (Section 20 updated). |
| 3 | **No pricing model yet; gate AI usage by plan** | Plans, entitlements, and quota enforcement are in scope. **No billing code.** Plan changes go through one service so billing can plug in later. |
| 4 | **Host on Render** with managed Postgres and Redis | Public API, so privacy defaults tighten (Section 36). `render.yaml` Blueprint, custom domain, two background workers. Companion/extension use the hosted API. |
| 5 | **Magic-link email login at launch**, in addition to Google | Needs a transactional email provider and a sending domain with SPF/DKIM/DMARC. Spec in Section 33. |

*Interpretation note:* "just for me, but proper user management" is read as "built like a real multi-user product, with signup locked down." If you instead want open public signup, change `SIGNUP_MODE` to `open`; no code changes should be needed.

---

## 33. Authentication & user management

### 33.1 Methods and account linking
- **Google OIDC** (Authorization Code + PKCE, `state` and `nonce`). Require `email_verified == true`.
- **Email magic link** (Section 33.3).
- **One user per verified email.** If the same email signs in via both methods, link both to the same `users` row via `auth_identities` (`provider='google'` or `'email'`). Never auto-link an *unverified* email.

### 33.2 Signup modes and roles
- `SIGNUP_MODE=closed` (default): only existing users can sign in. The owner is created by `make seed-owner` / a startup task from `OWNER_EMAIL`.
- `SIGNUP_MODE=invite`: a valid, unexpired, unused invite for that email is required to create an account.
- `SIGNUP_MODE=open`: anyone with a verified email may sign up (lands on the default plan).
- **Never reveal whether an email has an account.** Sign-in attempts from non-eligible emails get the same UI response as eligible ones (for magic link: "If this email can sign in, we sent a link.").
- **Roles:** `owner` (one or more; can do everything), `admin` (manage users/plans/invites, no role changes to owners), `user`.
- **Admin screen (`/admin`, role-gated, minimal):** user list (email, role, plan, last seen, AI usage this period), change plan, disable/enable user, revoke all sessions, create/revoke invites. Every admin action writes to `audit_log`.
- Disabling a user revokes their sessions, extension tokens, and companion tokens immediately.

### 33.3 Magic-link specification
**Request (`POST /auth/magic/request {email}`):**
1. Normalize the email (trim, lowercase). Validate format.
2. **Rate limits (Redis):** 1 request/min and 5/hour per email; 20/hour per IP. Over-limit still returns the generic 202 (log internally).
3. If the email is eligible (existing user, or allowed by `SIGNUP_MODE`), generate a token: 32 random bytes, URL-safe. Store **only its SHA-256 hash** in `magic_link_tokens` with `email`, `expires_at` (now + `MAGIC_LINK_TTL_MIN`, default 15), `created_ip_hash`, `consumed_at=NULL`. Invalidate older unconsumed tokens for that email.
4. Send the email through `EmailSender` (async, via a Celery task so the HTTP response time doesn't leak eligibility). Respond `202` with an identical body either way.

**Link:** `https://app.<domain>/auth/confirm?token=...`.

**Confirm page + verify (scanner-safe):** many email security scanners and link previewers issue a `GET` on every link. Therefore:
- Opening the link **only renders a confirmation page** with a "Sign in to Kairos" button. It must **not** consume the token.
- The button sends `POST /auth/magic/verify {token}`, which checks hash, expiry, and `consumed_at IS NULL`, then consumes it **atomically** (single UPDATE ... WHERE consumed_at IS NULL RETURNING), creates the user if allowed, links identity, sets `email_verified_at`, creates the session, and redirects.
- Cross-device is allowed (request on a laptop, open on a phone). Optionally show the user a 4-digit "match code" on both screens in a later iteration; not required for launch.

**Redirects:** any `next=` parameter must be validated against an allowlist of in-app paths (no open redirects).

**Email sending:**
- `EmailSender` protocol: `send(to, subject, text, html)`. Implementations: `ConsoleSender` (dev; prints the link), plus one of Resend / Postmark / SES chosen by `EMAIL_PROVIDER`.
- Templates in `api/app/email/templates/` (plain-text + simple HTML), fully original copy, no tracking pixels, no link-click tracking on the sign-in link.
- From address on your own domain (`EMAIL_FROM`); publish **SPF, DKIM, and DMARC** records before launch and verify delivery to Gmail/Outlook/iCloud inboxes (not spam).
- In Docker Compose, add Mailpit so developers can read emails locally.

### 33.4 Sessions
- Opaque token, hashed in DB, `HttpOnly; Secure; SameSite=Lax`, `Domain=$COOKIE_DOMAIN` (e.g., `.yourdomain.tld`) so the web app (`app.`) and API (`api.`) share it. Rolling 30-day expiry, absolute max 90 days.
- Settings page lists active sessions (device, last used) with revoke and "sign out everywhere."
- CSRF token required on state-changing requests; CORS allows only the web origin (`allow_credentials=true`).

### 33.5 Data model additions

```
magic_link_tokens
  id, email, token_hash (unique), expires_at, consumed_at, created_ip_hash, created_at

invites
  id, email, invited_by (user_id), role ('user'|'admin'), plan_id, expires_at, used_at, revoked_at, token_hash

audit_log
  id, actor_user_id, action, target_type, target_id, metadata (jsonb), ip_hash, created_at
```

### 33.6 Frontend
- `/welcome`: "Continue with Google" button + email field ("Email me a sign-in link"). After submit: a neutral "Check your email" screen with a resend cooldown timer.
- `/auth/confirm`: the confirmation page above.
- `/admin/*`: users, invites, audit log (owner/admin only).
- All copy in `web/src/copy/en.ts`.

### 33.7 Tests
Token single-use under concurrency (two simultaneous verifies: exactly one wins); expiry; hash-only storage; `GET` on the link does not consume; identical response for eligible vs. ineligible emails (body and status); rate limits; account linking (Google then magic link, and reverse); closed/invite/open behaviors; disabled user cannot sign in and loses sessions; open-redirect rejection; admin role checks on every admin route.

---

## 34. Plans and AI usage gating (no billing)

### 34.1 Concepts
- A **plan** defines **quotas** (numbers per period) and **entitlements** (feature booleans). Users have exactly one plan.
- Placeholder plans (names and numbers are **tunable config, not decisions**): `owner` (effectively unlimited), `free` (small quotas), `plus` (larger quotas). Seed them from `api/app/plans.py` on startup; edits go through a migration or admin tool.
- **No payments.** `PlanService.set_plan(user, plan, actor)` is the **only** code path that changes a plan (called by admin actions now, by billing later). It writes to `audit_log`.

### 34.2 Metered resources

| Metric | Unit | Period |
|---|---|---|
| `ai.calls` | calls | day |
| `ai.output_tokens` | tokens | month |
| `ai.retro` | weekly retrospectives generated | month |
| `ai.milestone_parse` | parser runs | month |
| `ai.chat_messages` | coach chat turns | day |

Entitlements (booleans): `feature.companion`, `feature.activity_log`, `feature.calendar_audit`, `feature.retro`, `feature.intervention`, `feature.smart_env`. A feature works only if it is both in the global `FEATURES` flag **and** granted by the user's plan.

### 34.3 Enforcement
- `entitlements.require(user, metric, cost=1)` runs **before** every LLM call and returns `429` with `{code:"quota_exceeded", metric, limit, used, resets_at}`.
- Counters live in Redis (fast, atomic `INCRBY` with period-keyed expiry) and are **reconciled nightly** against `ai_calls` rows (source of truth). After each call, record actual tokens.
- Add a **global kill switch**: `GLOBAL_AI_DAILY_CALL_CAP` across all users; when hit, all AI endpoints return a clean "AI temporarily unavailable" while the rest of the app works.
- Background jobs (weekly retro, milestone suggestions) count against the same quotas and **skip gracefully** when exceeded: the weekly retrospective falls back to a **stats-only** version with no LLM text.
- The UI shows a small usage meter in settings and a clear message on quota errors ("You've used today's AI allowance. It resets at ..."). No dark patterns.

### 34.4 Data model additions

```
plans
  id, key ('owner'|'free'|'plus'), name, quotas (jsonb), entitlements (jsonb), is_default

usage_counters       -- optional persisted snapshots; Redis is the hot path
  user_id, metric, period_key, count, updated_at   (PK: user_id, metric, period_key)
```

### 34.5 Tests
Quota boundary (limit-1, limit, limit+1), period rollover, concurrent calls cannot overshoot by more than a documented tolerance, nightly reconciliation corrects drift, global cap, feature entitlement + flag intersection, background job skip path, plan change audit entry.

---

## 35. Hosting on Render

### 35.1 Topology

| Render resource | Type | Purpose |
|---|---|---|
| `kairos-web` | Static site | React/Tailwind PWA build, served at `app.<domain>`, SPA rewrite to `index.html` |
| `kairos-api` | Web service (Docker) | FastAPI at `api.<domain>`; `/readyz` health check |
| `kairos-worker` | Background worker | `celery worker` |
| `kairos-beat` | Background worker | `celery beat`, **exactly one instance, never scaled out** |
| `kairos-db` | Managed Postgres | Application data |
| `kairos-kv` | Key Value (Redis-compatible) | Celery broker + rate-limit/quota counters |

Render Blueprint types: `web`, `worker`, `cron`, `keyvalue` services plus a separate `databases` list; free instance types are **not** available for background workers or cron jobs, so budget for paid instances for the worker and beat. Use a paid (non-spin-down) plan for the API so scheduled syncs and SSE aren't interrupted. **Verify current plan names, prices, regions, and backup/point-in-time-recovery features on Render's pricing page before choosing.**

### 35.2 Custom domain is required
Use `app.<domain>` for the web app and `api.<domain>` for the API so the session cookie (`Domain=.<domain>`, `SameSite=Lax`) is same-site. Browsers may treat the default `*.onrender.com` hostnames as unrelated sites, which breaks cookie sessions; verify this, but plan on a custom domain regardless since it is also needed for OAuth verification, email SPF/DKIM/DMARC, and the extension's `externally_connectable` list.

### 35.3 `render.yaml` (starting point: validate before use)

```yaml
databases:
  - name: kairos-db
    plan: basic-256mb            # choose after checking current plans
    region: frankfurt            # pick the region closest to you; verify availability

services:
  - type: keyvalue
    name: kairos-kv
    plan: starter                # verify
    region: frankfurt
    maxmemoryPolicy: noeviction  # broker data must never be evicted
    ipAllowList: []              # internal access only

  - type: web
    name: kairos-api
    runtime: docker
    dockerfilePath: ./api/Dockerfile
    dockerContext: ./api
    region: frankfurt
    plan: starter                # paid, no spin-down; verify
    healthCheckPath: /readyz
    preDeployCommand: alembic upgrade head
    envVars:
      - key: DATABASE_URL
        fromDatabase: { name: kairos-db, property: connectionString }
      - key: REDIS_URL
        fromService: { type: keyvalue, name: kairos-kv, property: connectionString }
      - fromGroup: kairos-secrets

  - type: worker
    name: kairos-worker
    runtime: docker
    dockerfilePath: ./api/Dockerfile
    dockerContext: ./api
    region: frankfurt
    dockerCommand: celery -A app.jobs.celery_app worker -l info -c 2
    envVars:
      - key: DATABASE_URL
        fromDatabase: { name: kairos-db, property: connectionString }
      - key: REDIS_URL
        fromService: { type: keyvalue, name: kairos-kv, property: connectionString }
      - fromGroup: kairos-secrets

  - type: worker
    name: kairos-beat
    runtime: docker
    dockerfilePath: ./api/Dockerfile
    dockerContext: ./api
    region: frankfurt
    dockerCommand: celery -A app.jobs.celery_app beat -l info
    numInstances: 1
    envVars:
      - key: REDIS_URL
        fromService: { type: keyvalue, name: kairos-kv, property: connectionString }
      - fromGroup: kairos-secrets

  - type: web
    name: kairos-web
    runtime: static
    buildCommand: cd web && npm ci && npm run build
    staticPublishPath: web/dist
    routes:
      - type: rewrite
        source: /*
        destination: /index.html
```

Notes for the agent:
- **Validate with the Render CLI / Blueprint validator** and fix field names against the current Blueprint spec; treat the file above as a template, not gospel. Create the `kairos-secrets` env group in the dashboard (it holds secrets that must not be in git).
- Render's Postgres URL uses the `postgresql://` scheme; `config.py` must **normalize it to `postgresql+asyncpg://`** for SQLAlchemy.
- **Migrations** run via `preDeployCommand`. Because the API, worker, and beat deploy independently, make every migration **backward-compatible** (expand → deploy → contract in a later release).
- **Beat must be a single instance.** Also guard each scheduled task with a Redis lock so an accidental second beat can't double-run jobs.
- **Environments:** create a `staging` and a `production` environment (separate Blueprints or projects, separate databases, separate Google OAuth clients and email sender). Never point staging at production data.
- **CI gate:** deploy to staging only from `main` after CI passes (use Render's checks-gated auto-deploy if available; otherwise deploy via the Render API from the CI job). Promote to production manually.
- **Secrets:** `TOKEN_ENCRYPTION_KEY`, `SECRET_KEY`, OAuth secrets, `EMAIL_API_KEY`, LLM keys. **Keep an offline backup of `TOKEN_ENCRYPTION_KEY`** in a password manager: losing it makes stored calendar tokens unrecoverable.
- **Backups:** confirm what the chosen Postgres plan provides (retention, point-in-time recovery). Run and document a **restore drill** before launch.
- **Observability:** Render logs + optional Sentry; an external uptime monitor on `/readyz`; alert on worker or beat being down and on a growing Celery queue.
- **Long-lived connections:** the companion SSE stream may be cut by infrastructure timeouts. Implement client reconnect with backoff and the 60-second polling fallback (Section 21).
- **Cold starts / deploys:** the extension and companion must tolerate brief API unavailability (retry with backoff, never end a focus session or remove blocks just because the API is unreachable; local timers own the end time).
- **Google OAuth for hosted:** set authorized redirect URIs to the `api.<domain>` callbacks (staging and prod), publish the consent screen status appropriately, and note the refresh-token-expiry caveat for apps in "Testing" status (Section 8).
- **Extension & companion config:** `API_BASE_URL` per environment; extension `externally_connectable` and server CORS include the production and staging web origins.

---

## 36. Data handling on a public host (what changes from Part II)

1. **Raw window titles never leave the companion.** Classification happens locally; the server stores title-less segments (Sections 23.3, 25).
2. **Calendar event titles are not stored by default** (`STORE_EVENT_TITLES=false`). The audit needs times and `is_meeting` only. If enabled, titles are encrypted at rest and never included in LLM prompts.
3. **Per-user integration credentials** (e.g., Slack token) are stored in `integration_credentials`, encrypted with `TOKEN_ENCRYPTION_KEY`, decrypted only inside the job that uses them, never logged, and deleted on disconnect or account deletion.

```
integration_credentials
  id, user_id, provider ('slack'|'teams'|...), secret_enc (bytes), scopes (text[]),
  expires_at (nullable), created_at, revoked_at
```

4. **LLM egress** stays redacted aggregates only, with a payload preview (Section 24.2). AI features can be disabled per user.
5. **Account deletion** cascades to all tables including `activity_segments`, `calendar_events_cache`, credentials, tokens, and sessions; Google tokens are revoked at Google. Provide `GET /me/export` before deletion.
6. **Logs:** no emails, tokens, magic-link URLs, window titles, or event titles in application logs. Use hashed user IDs.
7. **Privacy policy** page (needed for Google OAuth verification and the Chrome Web Store) must accurately describe the above. If you ever have users in the EU/UK, data-protection law applies; get proper advice before opening signup.

---

## 37. Milestones (additions)

### M1 (extended): Auth & user management
Magic link + Google, account linking, signup modes, roles, session management, admin screen, audit log, Mailpit in Compose, `EmailSender` with `ConsoleSender` and one real provider.
**Done when:** all Section 33.7 tests pass; a fresh account can sign in by either method; `closed` mode blocks unknown emails with an identical response; admin can disable a user and sessions die immediately.

### M1.5 (new) = D1: Render staging
Dockerfile for API/worker/beat, `render.yaml`, env groups, custom staging domains, DNS, SPF/DKIM/DMARC, Google staging OAuth client, health checks, migrations via `preDeployCommand`, CI gating.
**Done when:** sign-in works end-to-end on staging (Google and magic-link emails landing in a real inbox), the worker and beat run, and a deploy with a migration succeeds without downtime errors.

### M7 (extended): AI coach with plans
Plans, entitlements, quota enforcement, global kill switch, usage meter UI, nightly reconciliation, background-job skip behavior.
**Done when:** Section 34.5 tests pass and a `free` user hits a clean quota message while the rest of the app keeps working.

### D2 (new, after M8): Production launch
Checklist (all must be true):
- Custom domains live with HTTPS and HSTS; cookies verified across `app.` and `api.`.
- SPF, DKIM, DMARC passing; magic links deliver to Gmail, Outlook, and iCloud inboxes.
- Google OAuth consent screen configured, redirect URIs correct, verification submitted if needed.
- `SIGNUP_MODE=closed`; owner account seeded; no other accounts.
- Secrets rotated from staging; `TOKEN_ENCRYPTION_KEY` backed up offline.
- Postgres backup/restore drill completed and documented.
- Rate limits, quotas, and the global AI kill switch tested in production config.
- Privacy policy and account export/delete verified.
- Uptime monitor and alerting live; Sentry (if used) receiving events.

---

## 38. Remaining open questions

1. **Domain name** for `app.` / `api.` (blocks staging DNS, email authentication, OAuth redirect URIs, and the extension manifest).
2. **Email provider**: Resend, Postmark, or SES (any works behind `EmailSender`).
3. **Render region** closest to you (the template assumes Frankfurt; confirm what's available) and which paid instance sizes to start with.
4. **Plan names and numeric limits** (placeholders until you decide; they are config only).
5. **Primary OS** for the companion (macOS / Windows / Linux), which decides the first DND approach.
6. **Teams** needed, or Slack only? **Apple Calendar** needed, or Google only? **Home Assistant** available?
7. **Default LLM provider** for retrospectives (they use your most personal summaries).
8. **Chrome Web Store** developer account owner, for the extension listing.
9. Do you want **invites** enabled from day one, or strictly closed signup until you decide to open it?
