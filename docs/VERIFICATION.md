# Local verification — 2026-10-28

The working app has implementation across the core M0–M9 loop. This record distinguishes local automated evidence from credentialed provider and public-release acceptance.

## Passed

- Full backend suite: 106 tests against isolated PostgreSQL schemas, run inside the API container. Coverage includes authentication, scanner-safe and concurrent single-use links, account linking, CSRF/origin checks, ownership, admin/session revocation, deletion/export, deterministic scheduling/DST/capacity, focus concurrency/expiry, offline event idempotency, trajectory, quotas, provider mocks, calendar consent/publishing boundaries, extension bearer restrictions, and calendar publication/deletion races and linked-block lifecycle.
- Frontend: 19 component/storage tests for the plain app shell, wizard, suggestion request/review/apply boundary, account-scoped cache, ordered/idempotent replay, failed-write quarantine, and persisted offline session ending.
- Three Playwright production-build flows pass: goal wizard → check-in → draft/accept → focus/reload/end/rating → review/settings; mobile navigation with no horizontal overflow and WCAG A/AA axe checks; offline shell reload and exactly-once check-in replay.
- Extension: 4 rule unit tests and 5 real Chromium lifecycle checks pass against a controlled loopback API. The latter exercise native navigation blocking, full browser/worker restart, alarm expiry during outage, immediate offline pause, and original-session end replay. A temporary fixture manifest grants the test API; the packaged manifest remains unchanged.
- Ruff lint/format, strict mypy, TypeScript, ESLint, web production build, extension build, and generated API contract checks pass.
- Local production Lighthouse 12.8.2: signed-in Today performance **96**, accessibility **100**; Welcome performance **92**, accessibility **100**. No audit runtime errors or failing automated accessibility audits. Today FCP 1.4 s, LCP 2.0 s, TBT 150 ms, CLS 0.077 under the audit’s mobile throttling. This is evidence for these two local routes, not every device or future deployment.
- All seven Compose services start. PostgreSQL/Redis readiness, frontend API proxy, full Alembic migration chain, repeat migration, and worker connectivity are checked locally.
- Dependency audits reported zero known advisories for the locked Python, web, and extension dependencies during this build.

## Remaining acceptance gates

- Real Google sign-in/calendar consent, live event publication/reconciliation, and real-domain email delivery require configured credentials and domain setup. Local email-link sign-in is verified through Mailpit.
- Anthropic/Gemini adapters, streaming, consent and quota logic are tested with controlled responses; live model availability/output quality requires a configured key/model.
- The extension’s idle-only service-worker suspension, Chrome/OS matrix, permission prompts and store disclosures retain manual QA items. The automated recovery test restarts Chromium itself.
- PWA install/device testing and broader accessibility review extend beyond the local browser and two Lighthouse routes.
- CI is configured with real PostgreSQL/Redis and production-preview browser flows, but no remote GitHub Actions run is claimed. Nothing is deployed or published.
- Personal Mode M10–M17 and release D1/D2 remain deferred. JSON planning aggregates and transactional PostgreSQL quota reservations are documented deviations from the original normalized schema/Redis design.

The test suite emits two upstream Starlette/AnyIO deprecation warnings; all assertions pass.

## Visual refresh and personal scope

Users and invitation screens are removed; `/admin/*` redirects to Today. Sign-in and personal account controls remain. The refreshed UI passes 20 frontend tests, ESLint, TypeScript/production builds, and all three Playwright flows (planning/focus/review/settings, mobile accessibility, offline replay). The built dark dashboard and former admin-route redirect were also checked in Chrome. Self-hosted fonts are included in the offline precache. The Lighthouse measurements above predate this visual refresh and have not been remeasured. No deployment was performed.

## Backend reliability pass — 28 October 2026

Three domain agents and the primary integration agent completed the pass described in [Backend reliability](BACKEND_RELIABILITY.md). All ten root reference screenshots were viewed directly and mapped to explicit capabilities and missing work. No UI redesign or deployment was performed in this pass.

Final checks on the frozen source:

- **151 backend tests passed** against isolated PostgreSQL schemas (`docker compose exec -T -e TEST_DATABASE_URL=postgresql+asyncpg://kairos:kairos@db:5432/kairos api python -m pytest -q`). Includes production app composition, manual scheduling/conflict recovery, focus completion and replay, local-date statistics, check-in conflicts, reflection upserts, finite trajectory arithmetic, consented coaching and malformed-output retries, calendar pagination/recovery, and expired extension stops preserving newer sessions.
- **20 frontend tests**, **4 extension unit tests**, and **3 Playwright browser workflows** passed. Browser coverage includes planning/focus/review/settings, mobile accessibility, and offline check-in replay.
- Strict Python types (40 source files), web/extension TypeScript, Ruff lint/format, and patch whitespace checks passed. OpenAPI and generated TypeScript contracts were regenerated after the final request-schema changes.
- All seven local Compose services are running. API readiness confirms PostgreSQL and Redis; local worker and beat were restarted to load the updated calendar code.

The full backend run emits the same two upstream Starlette/AnyIO deprecation warnings. Provider regression tests use controlled responses; no live Google/model-provider acceptance is claimed. No new Chrome lifecycle or Lighthouse measurement is claimed by this pass. The prior Lighthouse numbers predate the visual refresh.

Manual block creation is now available through the API, but is not wired into the current UI. Named primary-calendar event feeds, independent tasks/support areas, recurrence/notes editing, proposal move/remove diffs, historical trend presentation and measured activity-based focus quality remain separate feature work. Exceptional calendar creation/encryption-key recovery constraints are documented in the reliability record.

## Agenda, tasks, recurrence and proposal pass — 28 October 2026

Implemented the workflows documented in [Events, tasks and week drafts](AGENDA.md). Three domain agents handled local persistence/recurrence, Google/unified feed, and UI; the primary agent implemented block notes, draft diagnostics, proposed move/removal acceptance, cross-domain checks, browser storage handling and full verification. No deployment was performed.

Final results:

- **188 backend tests passed** in isolated PostgreSQL schemas. Coverage includes task/event ownership and CRUD, single-occurrence overrides/cancellations, all-day/DST recurrence, local/Google feed composition, explicit details consent and encrypted cache/fallback, account export, draft outcomes, recurring commitment conflicts, pending destination reservations, stale proposal detection, and explicit/idempotent acceptance.
- **31 frontend tests passed**. These include event/task/proposal forms, occurrence-versus-series writes, manual creation, Google read-only display/hiding, account-scoped offline agenda reads and consent-cache purging in IndexedDB and React Query memory.
- **All five Playwright workflows passed** against the final local production preview: existing goal/draft/focus/review/settings; mobile navigation and Today/Plan accessibility; installed-shell offline replay; tasks/recurring events/occurrence notes; manual creation with explicit proposed-move acceptance. The mobile day view has no horizontal overflow, no automated WCAG A/AA violations, and keyboard PageUp/PageDown changes its timed scroll position. The production offline test waits for registration rather than skipping on a registration race. No final workflow was skipped.
- Strict Python types (44 source files), web/extension TypeScript, ESLint, Ruff lint/format, and patch whitespace checks passed. OpenAPI and TypeScript contracts are regenerated; agenda UI types derive from those schemas. The final Docker web production build passes.
- Additive migration `0005_google_event_details` was applied locally and repeated successfully. The API reports PostgreSQL/Redis ready. Local worker/beat services were restarted to load event-detail refresh support.
- Chrome visual checks verified Draft week's empty-account message/Add goal path, new event/notes/recurrence controls, saved recurring week occurrences and this-occurrence/entire-series editing controls. The explicitly named temporary visual-check series was removed; browser-test task/event/goal records clean up after themselves.

Mobile checking caught unlabeled built-in calendar icons and an unfocusable empty timed scroller. Plain navigation labels and focusable existing grid cells resolved these without overriding grid roles or disabling audit rules. Earlier failing checks were rerun; only the final passing results above are acceptance evidence.

Google provider tests use controlled responses. No live Google consent/event-data acceptance, remote calendar editing, multi-calendar selection, monthly/yearly recurrence, or new Lighthouse score is claimed. Deployment remains paused. The same two upstream Starlette/AnyIO deprecation warnings remain.

## shadcn/ui monochrome refresh — 28 October 2026

Migrated the app shell and page controls to the official shadcn/ui new-york component sources and Radix primitives, with neutral semantic tokens and dark default appearance. FullCalendar retains its scheduling behavior with matching monochrome styling. See [Interface design](DESIGN.md).

Final verification: **34 frontend tests passed**, TypeScript and ESLint passed, the Docker production web build passed, and **all five Playwright workflows passed** against that build (29.1 seconds). Coverage includes goal/draft/focus/review/settings, mobile overflow and accessibility, offline replay, tasks/recurrence/notes, and manual scheduling/proposed-move acceptance. Browser checks also inspected the dashboard, calendar and event dialog.

A deterministic regression reproduced an initial empty-week query being reused after drafting; canceling account-scoped pending reads before invalidation fixes the missing-proposals display. Mobile metric cards now fit a 390px viewport. Test selectors were updated to use the Calendar region after status labels became badges. Disposable records from interrupted local test runs were removed before the final passing suite.

Runtime dependency audit reported zero advisories. The full dependency audit reports four low-severity development-tool advisories through the Workbox/Rollup dependency chain; no forced dependency downgrade was applied. Backend code is unchanged by this refresh; the 188-test backend result above was not rerun. Deployment remains paused.
