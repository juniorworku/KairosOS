# Roadmap and acceptance gates

The core local app now has implementation across M0–M9. Code being present is not the same as every milestone's acceptance criteria being complete. Actual check results belong in the verification record; external credentials, browser installation, and public launch remain separate gates.

| Milestone | Current implementation | Remaining acceptance work |
| --- | --- | --- |
| M0 | Monorepo, Compose, CI, typed API/UI, migrations and generated client | Remote CI results depend on a connected/pushed repository; no remote success is implied |
| M1 | Google OIDC and email-link flows, closed/invite/open signup, roles, sessions, CSRF, profile, export/delete, basic admin/plans | Real Google client and real-domain email delivery verification; final production configuration |
| M2 | Seasons and typed saved goal aggregates with actions, obstacles, metric check-ins and editing | Planning aggregates use a documented JSON table deviation; per-aggregate normalization remains a future migration decision |
| M3 | Separate calendar consent, encrypted tokens, availability cache, sync and disconnect | Real OAuth/consent and provider scope verification with the owner's credentials |
| M4 | Pure deterministic scheduler, manual busy intervals, proposal reasons, capacity warning and review controls | Record completed UI/calendar interactions in browser verification |
| M5 | Explicit calendar publish, deterministic event identity, moved/deleted reconciliation and periodic sync | Real Google calendar publication/move/delete/retry acceptance |
| M6 | Timed focus sessions, self-ratings, session history/stats, deterministic trajectory and duration calibration | Longer manual usage across sleep/restart and representative session history |
| M7 | Anthropic/Gemini adapters, structured suggestions/streaming, AI-off, audited plan quotas/global cap | Credentialed live provider checks and output-quality evaluation; Redis hot counters/nightly reconciliation differ from the current transactional PostgreSQL design |
| M8 | PWA manifest/shell/update prompt, narrow private offline cache/write queue, security and browser checks | Measured production-build offline/install checks and Lighthouse >=90 budgets; broader public-host security/operational hardening |
| M9 | Unpacked Manifest V3 extension, pairing, navigation rules, alarms and pause/end controls | Complete [manual Chrome QA](../extension/QA.md), including worker/browser restart and outage scenarios; store packaging/disclosures before any distribution |
| M10–M17 | Personal Mode is deferred | Native companion/helper, activity logging, OS effects, automations, audits and interventions |
| D1/D2 | Deployment is explicitly deferred | Staging/production domains, provider verification, email authentication, backups/restore, monitoring and release approval |

Do not mark M8 complete based only on a manifest or claim Chrome timing/restart behavior from rule-unit tests. Manual core planning remains available without Google or AI keys. No staging, production or Chrome Web Store release runs from CI.
