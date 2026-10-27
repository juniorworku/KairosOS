# Remaining work

Current scope is a personal productivity app. The Users, invites, and administration screens have been removed. Sign-in, personal settings, session controls, export, and account deletion remain. Existing account data has not been deleted.

## Backend first

The current pass is assigned in [Backend reliability](BACKEND_RELIABILITY.md), including a direct review of all ten reference screenshots. The first reliability pass is complete: manual planning, calendar recovery, focus completion/statistics, and grounded coaching context are covered by 151 passing backend tests. API contracts and web/extension types are current; see [Verification](VERIFICATION.md). This does not complete the remaining calendar/task feature model below.

The next calendar UI pass must expose direct block creation and editing, keep goals/tasks visible beside the week, and distinguish proposals from accepted work. Named external/all-day events, recurrence, independent tasks/support areas, historical trend data, and typed apply-able schedule recommendations still require backend work; they are not merely styling changes.

## External setup and later work

1. **Google Calendar:** configure OAuth credentials and the encryption key; verify real availability, publication, rescheduling, deletion, and reconnect behavior.
2. **Coaching:** configure an Anthropic or Gemini key/model; verify live suggestions, streaming replies, consent, and quota messages.
3. **Real email sign-in:** choose the owner email and sending service/domain. Local sign-in currently uses Mailpit.
4. **MVP device checks:** complete Chrome idle-worker/permission testing, phone installation and offline checks, and longer focus/sleep/restart usage. Recheck performance and accessibility after the visual refresh.
5. **Personal Mode (later):** desktop companion, quick capture, OS-wide blocking/DND, activity logging, calendar audits, retrospectives, and optional automations.
6. **Deployment (paused):** domains, hosting, email authentication, backups/restore, monitoring, and release checks. Nothing deploys automatically.

User administration and invitations are deferred until requested again. Backend ownership and authentication safeguards remain in place.

## Detailed milestones

The core local app now has implementation across M0–M9. Code being present is not the same as every milestone's acceptance criteria being complete. Actual check results belong in the verification record; external credentials, browser installation, and public launch remain separate gates.

| Milestone | Current implementation | Remaining acceptance work |
| --- | --- | --- |
| M0 | Monorepo, Compose, CI, typed API/UI, migrations and generated client | Remote CI results depend on a connected/pushed repository; no remote success is implied |
| M1 | Google OIDC and email-link flows, closed/invite/open signup, roles, sessions, CSRF, profile, export/delete; admin backend retained for later | Real Google client and real-domain email delivery verification; user/invite UI deferred |
| M2 | Seasons and typed saved goal aggregates with actions, obstacles, metric check-ins and editing | Planning aggregates use a documented JSON table deviation; per-aggregate normalization remains a future migration decision |
| M3 | Separate calendar consent, encrypted tokens, availability cache, sync and disconnect | Real OAuth/consent and provider scope verification with the owner's credentials |
| M4 | Pure deterministic scheduler, manual busy intervals, proposal reasons, capacity warning and review controls | Browser goal/draft/accept workflow verified locally; external calendar interaction remains credential-gated |
| M5 | Explicit calendar publish, deterministic event identity, moved/deleted reconciliation and periodic sync | Real Google calendar publication/move/delete/retry acceptance |
| M6 | Timed focus sessions, self-ratings, session history/stats, deterministic trajectory and duration calibration | Longer manual usage across sleep/restart and representative session history |
| M7 | Anthropic/Gemini adapters, structured suggestions/streaming, AI-off, audited plan quotas/global cap | Credentialed live provider checks and output-quality evaluation; Redis hot counters/nightly reconciliation differ from the current transactional PostgreSQL design |
| M8 | PWA manifest/shell/update prompt, narrow private offline cache/write queue, security and browser checks | Offline reload/replay verified; Pre-refresh Lighthouse: Today 96 performance/100 accessibility and Welcome 92/100; the refreshed UI has not been remeasured. Manual install/device matrix and public-host operational hardening remain |
| M9 | Unpacked Manifest V3 extension, pairing, navigation rules, alarms and pause/end controls | Five real Chromium lifecycle checks pass against a controlled API, including full browser/worker restart and offline escape/expiry. Idle-only suspension and the remaining [manual Chrome QA](../extension/QA.md), store disclosures, and distribution remain |
| M10–M17 | Personal Mode is deferred | Native companion/helper, activity logging, OS effects, automations, audits and interventions |
| D1/D2 | Deployment is explicitly deferred | Staging/production domains, provider verification, email authentication, backups/restore, monitoring and release approval |

Do not mark M8 complete based only on a manifest or claim Chrome timing/restart behavior from rule-unit tests. Manual core planning remains available without Google or AI keys. No staging, production or Chrome Web Store release runs from CI.
