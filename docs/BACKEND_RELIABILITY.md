# Backend reliability pass

The target is a usable personal planning loop: save a goal and its actions, place work in a real week, move it without losing data, focus on it, record progress, and review what happened. UI redesign and deployment are paused during this pass. Three agents own separate domains; the primary agent owns integration, coaching context, reference review, and final validation.

## Assignments and order

| Owner | Work | Evidence required |
| --- | --- | --- |
| Planning agent (`plan_review`) | Goal/action integrity, manual block creation, scheduling preferences, conflict checks, repeat acceptance, concurrent busy changes | Deterministic scheduler tests and isolated PostgreSQL route tests |
| Calendar agent (`integrations`) | Google token/connection lifecycle, publication retries, move/delete reconciliation, availability failures | Controlled provider responses, persistence checks, explicit live-provider limits |
| Focus/progress agent (`backend`) | Session expiry/end/replay, block completion, local-date statistics, check-ins, trajectory arithmetic | Real database transitions and calculation regression tests |
| Primary agent | Trace production app/API wiring, inspect all references, enrich consented goal/progress context, regenerate contracts, integrate and run checks | Full app composition with PostgreSQL; frontend compatibility checks |

1. Reproduce concrete failures and identify missing capabilities.
2. Implement domain fixes with regression tests; preserve owner data and authentication.
3. Exercise the domains together through the production application's routers and error handlers.
4. Record passed checks and outstanding gaps separately.
5. Begin calendar UI work only after this backend pass. Do not deploy.

## What the screenshots required at the initial audit

All ten reference PNGs in the repository root were inspected directly on 28 October 2026. They are product references, not evidence that Kairos already implements the depicted behavior.

| Reference screenshots (time suffix) | Product behavior shown | Backend implications |
| --- | --- | --- |
| 4.17.05 | Specific coaching recommendations with Apply controls | Measured goal/action/progress context and validated, explicit mutations; text alone is insufficient |
| 4.17.23, 4.29.03 | Week proposal showing additions, moves, removals and approval | Reliable draft/accept semantics; an actual change-set model is still needed for move/remove proposals |
| 4.22.00 | Season goals and support-area tasks beside a calendar | Goal/action links; independent task inbox and support areas need a separate model |
| 4.22.30 | Named timed events, all-day events, overlaps, source markers | A complete event feed; Google free/busy intervals cannot supply event titles, notes or all-day semantics |
| 4.23.17 | Event details, notes, recurrence and Start | Persistent event metadata, recurrence rules and exceptions, linkage to focus sessions |
| 4.29.15 | Focus duration, sessions, measured quality and distraction breakdown | Reliable session timing now; measured activity/quality needs telemetry and must not be fabricated from a self-rating |
| 4.29.27 | Historical progress, projections and concrete adjustments | Reliable metric history/calculations; historical trend API and typed, validated recommendations remain distinct work |
| 4.29.37 | Shared active session across desktop and phone | Persisted active session and replay-safe writes; native clients and OS effects remain later work |
| 4.30.37 | Calendar and meeting-note integrations | Provider-specific consent, synchronization and recovery; logos are not implemented integrations |

## Scope at the initial audit

A FullCalendar week view is already used in the frontend, but its input is primarily goal blocks and background busy intervals. Restyling that grid cannot supply missing event or task behavior. This pass adds backend capability and repairs behavior; it does not claim parity with the reference product.

Google event-detail access requires an explicit consent design with the appropriate scopes. Current free/busy consent does not authorize reading private event details. Live Google and model-provider acceptance still require configured credentials. Independent tasks, recurring/all-day event editing, proposal move/remove diffs, native clients, meeting-note integrations, and measured focus quality are follow-up work.

## Implemented in this pass

| Trigger | Corrected behavior |
| --- | --- |
| Schedule an action directly rather than generating a whole week | `POST /api/v1/blocks` validates and persists a goal-linked local block; UI wiring is still next |
| Prefer an afternoon slot on an otherwise open day | Scheduler searches within free periods instead of considering only the first start; real instants preserve DST ordering |
| Several habits or actions already have accepted work | Existing days count toward habit spread, and duration calibration uses completed blocks for the same action |
| Edit/remove an action or change a block during focus | Stale proposals are cancelled; active linked focus protects destructive changes; owner locks serialize planning/busy mutations |
| End a short session on a longer block | Duration accumulates toward the block's budget; completion requires 90% of that budget, with manual outcomes preserved |
| Replay a check-in or session end with changed content | The API returns a conflict rather than silently changing or accepting a different event |
| End offline, after an automatic expiry or another device's end | Earlier valid endings reduce recorded time and can undo focus-induced completion; later retries cannot add time |
| Replay an extension stop after its original session expired | The exact owned session is corrected; unknown or older session IDs cannot stop a newer active session |
| Review a session spanning local midnight | Minutes split by local-date overlap; combined ranges count the session once |
| Ask for coaching with goal/progress consent | Context includes bounded action targets/finite-project estimates, latest metrics and measured weekly effort; private notes, calendar details and raw IDs are excluded |
| A successful Google event write is retried after its response is lost | Stable-ID recovery reads and verifies the existing event, preserving the user's remote move instead of overwriting it |
| Google sync expires a token during pagination or a later page fails | Partial pages are discarded or rolled back; a complete result is applied atomically |
| Google access expires or the app calendar disappears | Reauthorization state persists and publishing capability is reported honestly |

Goal list reads now batch check-ins instead of rescanning them once per goal. Extreme metric arithmetic returns bounded, JSON-safe progress; first-week evidence does not imply a reliable finish forecast. Reflections use Monday week keys and serialized upserts.

Live Google and coaching providers remain credential-gated. The automated provider tests use controlled responses. Final check results are recorded in [Verification](VERIFICATION.md).

Calendar recovery limits: losing or changing the token-encryption key prevents credential decryption. The current disconnect/account-deletion paths require restoring the original key or a deliberate operator-assisted cleanup; self-service recovery without that key is not implemented. If Google creates an app calendar but its response is lost, automatic creation retries are disabled to reduce duplicates, but a later fresh consent attempt can still leave an orphan calendar requiring cleanup. Neither limitation is claimed solved by database transaction locks.

## Follow-on event/task feature pass

The gaps above now have a working implementation for unified primary/local feeds, independent tasks, daily/weekly recurrence, event/block notes, manual creation in Plan, and proposed local goal-block moves/removals. Draft week now explains empty results and uses recurring local commitments as busy time. See [Events, tasks and week drafts](AGENDA.md) for current routes, semantics and remaining limits; the earlier audit table describes the starting point, not the current feature inventory. Deployment remains paused.
