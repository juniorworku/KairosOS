# Remaining work

Current scope is a personal productivity app. The Users, invites, and administration screens have been removed. Sign-in, personal settings, session controls, export, and account deletion remain. Existing account data has not been deleted.

## Current feature pass

The initial reliability pass is followed by the [events/tasks/calendar implementation](AGENDA.md): unified agenda, independent tasks, local notes and daily/weekly/monthly/yearly recurrence, single-occurrence edits, explicit Google-details consent, manual block creation in the UI, and move/removal previews with acceptance. Draft week now explains empty results and avoids local recurring commitments.

The Plan UI exposes these workflows; they are no longer API-only. Final checks are recorded in [Verification](VERIFICATION.md). Owned Google calendar selection/editing and the opt-in Linux companion are implemented. Remaining calendar work includes shared-calendar detail/edit scope expansion, whole-series Google changes, ordinal weekday recurrence and broader device/live-provider acceptance. Deployment remains paused.

## Connected workflow pass

The [Superfocus comparison](SUPERFOCUS_GAPS.md) now tracks implemented connections and remaining boundaries. Today leads to accepted work and a unified agenda; seasons show recorded versus expected pace; calendar links retain date/goal/block/task context; draft additions/moves/removals share explicit review; focus completion offers an outcome check-in and the correct review week. Monthly/yearly local recurrence is wired through API and UI. Coaching uses visible evidence and explicit sharing consent. Final checks: 194 backend tests, 64 frontend tests and all seven browser workflows passed; see [Verification](VERIFICATION.md).

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
| M3 | Separate availability/details consent, encrypted tokens and event details, unified primary/local feed, sync and disconnect | Real OAuth/consent and provider scope verification with the owner's credentials |
| M4 | Deterministic scheduler, local recurring commitments, manual creation UI, explicit draft outcomes, move/removal previews and stale-safe acceptance | Browser goal/draft/accept workflow verified locally; external calendar interaction remains credential-gated |
| M5 | Explicit calendar publish, deterministic event identity, moved/deleted reconciliation and periodic sync | Real Google calendar publication/move/delete/retry acceptance |
| M6 | Timed focus sessions, self-ratings, session history/stats, deterministic trajectory and duration calibration | Longer manual usage across sleep/restart and representative session history |
| M7 | Anthropic/Gemini adapters, structured suggestions/streaming, AI-off, audited plan quotas/global cap | Credentialed live provider checks and output-quality evaluation; Redis hot counters/nightly reconciliation differ from the current transactional PostgreSQL design |
| M8 | PWA manifest/shell/update prompt, narrow private offline cache/write queue, security and browser checks | Offline reload/replay verified; Pre-refresh Lighthouse: Today 96 performance/100 accessibility and Welcome 92/100; the refreshed UI has not been remeasured. Manual install/device matrix and public-host operational hardening remain |
| M9 | Unpacked Manifest V3 extension, pairing, navigation rules, alarms and pause/end controls | Five real Chromium lifecycle checks pass against a controlled API, including full browser/worker restart and offline escape/expiry. Idle-only suspension and the remaining [manual Chrome QA](../extension/QA.md), store disclosures, and distribution remain |
| M10–M17 | Personal Mode is deferred | Native companion/helper, activity logging, OS effects, automations, audits and interventions |
| D1/D2 | Deployment is explicitly deferred | Staging/production domains, provider verification, email authentication, backups/restore, monitoring and release approval |

Do not mark M8 complete based only on a manifest or claim Chrome timing/restart behavior from rule-unit tests. Manual core planning remains available without Google or AI keys. No staging, production or Chrome Web Store release runs from CI.

## Calendar, native blocking and appearance pass

Owned-calendar selection and version-checked remote event editing now have API/UI implementations with separate consent. Shared calendars intentionally contribute availability only; recurring remote writes target single instances. `native/` provides an opt-in Linux companion with explicit executable configuration, authenticated pairing, independent recovery watchdog and expiring status reports. It has been exercised against the real local Kairos API with a disposable copied process; actual desktop applications and other operating systems remain device acceptance work. This does not complete the broader M10–M17 Personal Mode scope. Warm light is now the default, with persistent light/dark controls on desktop and mobile. AI coaching was left unchanged; deployment remains paused.
