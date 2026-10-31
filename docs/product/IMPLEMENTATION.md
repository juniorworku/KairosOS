# Implementation blueprint and release gates

Status: proposed plan, not authorization to implement or deploy. The first public web release is the complete five-engine executive assistant. Internal build increments are not standalone planner releases.

## Existing foundation and scope distinction

Repository documentation describes React/Vite/TypeScript, FullCalendar, FastAPI/Pydantic, PostgreSQL, Celery/Redis, goals/tasks, recurrence, Google integration, proposal review, focus logging, coaching and a Chrome extension. Reuse after targeted assessment, not a rewrite. Existing documented tests do not establish new feature/provider readiness.

A legacy Linux helper in this repository suspends configured executables; it is outside the newly agreed product scope. The new roadmap excludes native-app blocking. Do not claim a hosts-file helper already exists or silently ship legacy app suspension as the new feature. This documentation pass does not remove or alter existing code.

## Logical modules

Five domain engines share ingestion/context, proposal/approval, background scheduling and delivery infrastructure. Engines are ownership boundaries in the design, not five required microservices. Keep one maintainable modular application unless scaling evidence justifies separation.

Shared ingestion updates owner-scoped source records and rolling summaries. Commitment reconciliation produces candidates and evidence links. Guardian validates scheduling deterministically. Briefing composes engine outputs. Goal engine tracks outcomes/plans. Insights aggregates coverage-aware statistics. AI sees minimal authorized context packs and cannot execute effects. Template registry constrains trigger/check/output combinations and authority.

## Proposed durable records

| Record | Required contract |
| --- | --- |
| Source record/cursor | Owner, provider identity, source version/hash, sync cursor, coverage/freshness, permissions, tombstone |
| Summary/context | Subject/source versions, evidence IDs, prompt/model version, as-of, expiry and permission boundary |
| Commitment/task | Separate obligation and fulfillment task, accepted/candidate state, owner/beneficiary, due/review time, evidence and resolution |
| Plan/block | Goal/season link, version, accepted status, fixed-time flag, capacity/availability snapshot |
| Template/loop | Registered schema/version, profile, validated parameters, authority ceiling, context recipe, model tiers/caps, catch-up/stop rules |
| Loop run | Logical trigger key, source/time snapshot, state, budget reservation, output/evidence, sanitized errors |
| Proposal/approval | Typed effects, before/after, dependencies, versions/destinations, exact authorization, dismissal signature, partial results |
| Provider action | Stable operation ID, remote version/reference, pending/success/failed/unknown, reconciliation result |
| Delivery | Stable identity, tier, channels/attempts, consent/quiet-hour/cap decision, feed record |
| Usage ledger | Purpose/run/model, tokens/cache/estimated cost, reservation/actual/unknown flags, pricing version |

Use migrations and owner-scoped indexes/constraints. Decide normalization for high-volume source/run data rather than extending planning JSON indiscriminately. Preserve accepted data and evidence during recovery/migration.

## Internal build order

| Stage | Work | Exit evidence |
| --- | --- | --- |
| 0 | Finalize templates, UX, retention/consent, limits and scope | Walkthrough of full assistant journey; built-in check schemas validated and unresolved operational defaults approved |
| 1 | Calendar, goals and tasks; calendar-first shell; guardian/proposal foundation | Google read/sync/publication acceptance; fixed blocks, stale source, retry, conflicting/partial write checks |
| 2 | Shared context, registry, server loops, budgets and delivery; focus web flow | Closed-app brief, catch-up, dedup, costs, quiet hours, Chrome website expiry, timer/audio recovery |
| 3 | Meetings from supplied notes; commitment ledger and dossiers | Extraction/merge/resolution quality; provenance; task/draft approval; imported history coverage |
| 4 | Gmail; email commitments, reply/waiting/VIP, noise insights | Provider consent/verification, bounded ingestion, expired history recovery, approved draft/send, privacy lifecycle |
| 5 | Full engine integration and pilot | All F01-F21/N01-N08 evidence; real-use pilot and tuning before release decision |
| Later | Desktop timers for macOS/Windows/Linux; one-OS system website helper; other providers/capture/handoff | Separate platform gates; native-app/cross-device blocking remains excluded |

Stage 1/2 prototypes may be reviewed locally, but must not be presented as the requested full release. Meeting notes import satisfies the first release; bot-free recording is not a hidden dependency. Google Calendar is foundational and Gmail is the proposed initial mail provider; additional providers require later decisions.

## Consistency and execution

Calendar source events are observations, not proposals: display already-made external changes promptly, then propose Kairos corrections. Protect fixed blocks. Recheck owner, consent, proposal version, source freshness, current availability and dependencies before apply. Persist local intent and use a durable outbox or equivalent for external effects; no distributed transaction is implied. Stable keys and reconciliation prevent duplicate/unknown writes from being blindly retried.

Use server scheduler/worker jobs with leases and dedup, bounded retries and pause/version checks before delivery. Device owns session expiry and emergency unblock. Browser shutdown does not stop server loops and server failure does not prolong website rules. AI-off mode and budget kill switch preserve manual functionality and current deterministic findings.

## Acceptance and pilot

Trace every requirement to implementation issue and evidence. Test permission/ownership, unsupported template values, authority escalation, source injection, stale approvals, fixed blocks, dismissal suppression, dependent batch changes, cursor expiry, missed runs, DST/time progression, duplicate delivery, cost reservation races and device recovery. Use labeled examples to measure extraction, unresolved-vs-answered distinctions and grounding, not just schema validity.

Before pilot configure retention and numerical budgets, performance dataset/budgets, notification limits and supported Chrome/OS versions. Measure real usage for at least the proposed first week before tuning caps. Production release additionally needs applicable provider verification, operational monitoring, backup/restore, migration rollback, consent/privacy review and a separate deployment authorization. No tests, deployment or live provider changes are claimed by this documentation update.


## Verified platform dependencies

[Google Calendar sync](https://developers.google.com/workspace/calendar/api/guides/sync) uses paginated changes and invalidated-token recovery. Calendar push requires a public HTTPS receiver; notifications signal the need to synchronize rather than carrying the complete changed event. See [Calendar push](https://developers.google.com/workspace/calendar/api/guides/push). Polling can support local validation; closed-app production automation requires hosted workers/scheduler and monitoring, subject to later deployment authorization.

[Gmail sync](https://developers.google.com/workspace/gmail/api/guides/sync) requires history-expiry recovery. [Gmail push](https://developers.google.com/workspace/gmail/api/guides/push) requires Pub/Sub and renewable watches; configure renewal and polling/recovery fallback. [Gmail scope documentation](https://developers.google.com/workspace/gmail/api/auth/scopes) identifies restricted scopes and applicable verification/security-assessment dependencies for server-handled restricted data; validate audience, scopes and exceptions before setting a public launch date.

[Chrome declarative request rules](https://developer.chrome.com/docs/extensions/reference/api/declarativeNetRequest) apply within supported browser/profile capability, not native-app control. [Web push overview](https://web.dev/articles/push-notifications-overview) explains subscription/service-worker delivery; server jobs remain authoritative. [Document Picture-in-Picture](https://developer.chrome.com/docs/web-platform/document-picture-in-picture) may be an optional browser enhancement but does not replace the later cross-platform desktop companion contract.

Technical references checked 30 October 2026. These constraints inform implementation planning, not a claim that new connectors or desktop packages already exist.
