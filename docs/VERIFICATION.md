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

## Connected Superfocus-inspired workflow — 28 October 2026

Three agents implemented calendar/review, Today/seasons/goals, and Focus/coaching. The primary agent integrated active-session continuity, exact-task navigation, cancellation-aware reads, monthly/yearly recurrence and complete workflow verification. The owner authorized restrained color: warm neutrals, lavender planning, green progress and source tints replace the monochrome-only restriction. No deployment was performed.

Final checks on the integrated source:

- **194 backend tests passed** against isolated PostgreSQL schemas in the final full run (317.05 seconds). New cases cover month-end and leap-day recurrence, intervals, DST wall time, bounded ranges, persisted series, occurrence notes, cancellation and series edits. The initial leap-day integration test incorrectly requested more than the allowed 366-day agenda window; it was corrected to page through bounded windows, with all original three-instance assertions retained.
- **64 frontend tests passed** across 12 files. Coverage includes saved season creation/assignment and preselection, next-action/resume priority, unified agenda and cached-provider warnings, due-task context/focus, draft decisions, explicit post-focus outcome writes, coaching consent/evidence and suggestion previews, review/date helpers and stale-read/offline-cache regression. TypeScript and ESLint passed without warnings.
- **All seven Playwright workflows passed** against the final Docker production web build (57.4 seconds). The main flow now navigates away during a running session, returns through the global strip, ends/rates it, saves an outcome check-in and opens its review week. The task flow follows Today’s due-task link, verifies exact task focus, schedules it explicitly and edits recurring occurrence notes. Other flows cover explicit move acceptance, offline replay, mobile Today/Plan overflow/keyboard/accessibility, all six workflow routes in both light/dark themes, date persistence across reload, and monthly/yearly event creation/persistence. No final workflow was skipped.
- Strict backend typing (44 source files), Ruff lint/format (63 files), generated OpenAPI/TypeScript contracts, patch whitespace checks and the Docker web production build passed. Local API/worker/beat were restarted to load recurrence support.
- Chrome visual checks inspected the populated Today-to-dated-plan handoff, selected goal/block styling, appointment/task source presentation and the revised hierarchy. Explicitly named temporary preview goal/block/task/event records were removed afterward. Screenshots use this disposable verification data, not invented production statistics.

The same two upstream Starlette/AnyIO deprecation warnings remain. Controlled coaching/provider tests are not live acceptance; pairing metadata is not proof of browser blocking. Multi-calendar/remote editing, other providers, native blocking/attention measurement and broader device checks remain in [the updated gap record](SUPERFOCUS_GAPS.md).

## Multi-calendar, native blocking and appearance — 28 October 2026

AI coaching was unchanged. Three agents implemented/reviewed calendar backend/UI and the Linux companion; the primary agent integrated native heartbeat/setup UI, appearance controls, cache protection and final verification. Deployment remains paused.

Final evidence:

- **207 backend tests passed** in the full isolated-PostgreSQL run (189.58 seconds), including multi-calendar selection/consent, encrypted owned-source details, provider ACL and ETag conflicts, stable create IDs, recurring-instance boundaries, linked-block reconciliation, and native report authentication, deadline validation, expiry, revocation and pending recovery. Strict mypy passes for 46 source files; Ruff lint/format passes for 67 files. Migration 0006 was applied to the local stack.
- **80 frontend tests passed** across 14 files. They cover calendar choices and explicit consent links, remote Save/Delete/version conflicts, retry identity, preserved all-day/DST/seconds, native freshness/error wording, visible light/dark persistence and existing workflows. Source changes also purge current-account memory/offline agenda snapshots on deselection and prevent late reads from restoring old sources or private data after logout. TypeScript/ESLint pass. DOM test workers are bounded to two to avoid jsdom/IndexedDB contention on small hosts; no assertions were relaxed.
- **13 native recovery tests passed together** (25.826 seconds), using real SIGSTOP/SIGCONT only on unique disposable copies of sleep. Coverage includes focus end, API outage, controller crash/freeze, lease/deadline, watchdog death, PID/boot/executable identity, pre-stopped exclusions, root refusal before file mutation, and retained/retried recovery intent after transient signal/identity failures. Ruff/compile checks pass.
- A **live local Kairos smoke test** paired the companion, started a temporary focus action, observed a disposable process stop, verified an authenticated blocking report, ended focus, observed resume and an idle report. The test credential was revoked; its temporary goal and processes/state directory were removed. No installed desktop application was suspended and no autostart/service was installed.
- **All nine Playwright workflows passed** against the final Docker web production build (41.9 seconds), without skips. Existing connected planning/focus/progress/review, tasks/recurrence/proposals and offline replay remain green. Added checks exercise visible desktop/mobile theme controls across reload and the Focus → native Settings anchor/keyboard focus/setup/audit path. Both themes and mobile Today/Plan retain accessibility/overflow coverage.
- **Four extension unit tests** and extension TypeScript pass. OpenAPI and TypeScript contracts are regenerated. Final production build/precache and patch whitespace checks pass. Chrome visual inspection confirms the warm-light palette and visible toggle; the local app is left in light mode.

Google scopes, calendar listing, conditional ETag writes and recurring-instance semantics were checked against official provider documentation. Controlled-provider tests are not live Google acceptance: no new Google permissions were granted and no real remote events were changed. Editing is intentionally limited to owned calendars; shared calendars supply availability only. Whole-series/all-following remote recurrence changes remain external. Native blocking is opt-in on Linux with exact local executable choices; other operating systems, real desktop apps and host packaging remain acceptance/future work. Helper reports are timestamped app-process counts, not attention measurements or independent OS proof. Both recovery processes being forcibly prevented from running requires the documented local recovery command. The same two upstream Starlette/AnyIO warnings remain.
