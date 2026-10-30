# Templates, background operation and approvals

## Fixed declarative templates

A template is a versioned typed specification, not generated code. It declares supported schedule/event/threshold triggers, scope filters, deterministic checks, output profiles, authority ceiling, stop conditions, context recipe, model tier per step, token cap and catch-up policy. A user's loop stores template ID/version and validated parameters. User values may reduce authority, never increase it. Unknown fields/actions fail validation.

Six user-facing template families: Daily brief, Daily check-out, Goal check-in, Overdue and slipping work, Focus rescue, Weekly review. The mapping of specialized assistant checks to fixed profiles within these six families is a proposed catalog arrangement pending user confirmation. All listed executive-assistant capabilities remain required in the first web release regardless of final catalog labels.

Chat fills the typed form, explains the preview and waits for activation confirmation. Unsupported requests identify the limitation, offer the closest supported configuration and record a redacted miss for product discovery. Free-text preferences such as short briefs or lead with money matters affect prose only; typed priorities determine checks/ranking. They cannot modify logic, sources, cadence, tools or action authority.

## Registered profile mapping — proposed catalog arrangement

| Family | Fixed checks/output profiles | Trigger and context |
| --- | --- | --- |
| Daily brief | Morning overview; VIP watch; meeting dossier | Morning schedule; VIP wait threshold; before-meeting event. Reads accepted priorities, open commitments, calendar and source-linked relationship/thread summaries. |
| Daily check-out | Evening reconcile; meeting follow-through; `/done` | Evening or meeting-note-ready event. Reads new meeting evidence, decisions, candidate commitments and today's tasks. |
| Goal check-in | Progress, trajectory, promise tracker, waiting-on-them | Scheduled/threshold checks scoped to a goal or selected commitment/area; global ledger profile has no mandatory goal. Reads outcome measures, tasks and relevant unresolved commitments. |
| Overdue and slipping work | Overdue tasks, repeated postponements, reply debt | Scheduled or threshold; global or goal scope. Reads due/wait dates, meaningful move history, urgency/VIP settings and unresolved replies. |
| Focus rescue | Focus guard + defense; sentinel checks; freed time; travel buffer | Calendar change or periodic check. Reads current availability, fixed blocks, capacity, travel fields and selected goals. |
| Weekly review | Friday wrap; week-ahead prep; time-use; inbox noise | Weekly modes; inbox-noise profile can use biweekly cadence. Reads shared review record and aggregate statistics. |

Family names do not force one daily/weekly cadence on every registered profile. Profiles have their own schema-approved trigger choices. Users can enable multiple instances; deduplication prevents the same finding being reissued across profiles. This grouping is an explicit draft choice, not a claim the user has approved specialized mapping.

## Authority and review

Automatic under granted permissions: ingestion, structured candidate extraction, deterministic checks, in-app draft previews, reports and permitted notifications. AI cannot create accepted obligations or execute external side effects on its own.

Proposed effects: accepted task creation from inference; external mailbox draft creation/update; calendar addition/move/removal; follow-up message sending. Review lists exact items/destinations and dependencies. Approving a draft is distinct from approving sending. Direct user commands authorize only the clearly requested scope. Every assistant schedule adjustment requires approval, including its own blocks.

Related effects share a batch review with itemized choices. A dependent effect cannot apply unless its prerequisites are approved/applied. Before applying, check owner, permissions, source/version/freshness, availability and locks. Superseded/expired or meaningfully changed effects require renewed review. Partial external success is reported; unknown outcomes reconcile before retry.

A dismissal records a meaningful finding signature, not just its generated wording. Suppress equivalent proposals until relevant source facts/constraints change. Time-based thresholds can constitute a declared change only when the template explains it; daily reruns alone are not a reason to revive dismissed suggestions.

## Server runs and catch-up

Server scheduler and source-event processing run independently of the browser. Store a logical trigger key, input snapshot, template version, planned time, actual time, freshness, budget reservation and outcome. Lease/lock execution to prevent duplicate processing. Recheck pause/stop and template version before emitting outputs. Retry transient failures with bounded backoff; surface persistent failure and recoverable partial results.

| Profile type | Missed-run rule | Obsolescence rule |
| --- | --- | --- |
| Morning brief | Coalesce to latest relevant local-day run; regenerate fresh deterministic facts | Label late; no old morning push after the configured usefulness window |
| Evening check-out | Offer one most recent reconciliation | Do not auto-complete or replay every missed evening |
| Goal/overdue checks | Evaluate current conditions once on recovery | Suppress conditions no longer true; preserve meaningful unresolved findings |
| Meeting dossier | Run only before meeting within configured lead/usefulness window | After start, skip prep delivery; use follow-through when notes are available |
| Meeting follow-through | Process each unprocessed eligible note revision within configured retention | Revisions update candidates/deduplicate rather than duplicate accepted work |
| Calendar rescue | Check current availability and pending proposals | Expired slots/conflicts are not actionable; replace affected proposals |
| Weekly modes | Coalesce per review period and mode | Do not send a stack of historical summaries; history remains inspectable |

Exact brief times, lead windows, catch-up maximums, DST policy and retention are configuration gates before launch. A reasonable proposed DST default is once per intended local run, shifting nonexistent local times forward and not duplicating ambiguous-time runs; validate and approve the policy before implementation.

## Notification contract

In-app feed is the durable record. Web push is the first out-of-app channel when permitted/available. Email is an opt-in fallback for eligible items when push is unavailable or delivery fails; lack of read acknowledgment alone does not trigger duplicate email. A push-service acceptance is not proof of human receipt. Delivery channels share a stable notification identity.

Tiers: quiet (feed only), scheduled (digest window), nudge (actionable time-sensitive finding), urgent (user-enabled urgent condition). Quiet hours and daily interruption limits apply; urgent does not bypass them unless the user explicitly configures that exception. Coalesce related findings and preserve pending decisions after notification suppression. Email defaults to a minimal summary/link rather than sensitive source content.

Manual app access, feed reading, approval and emergency device unblock never depend on AI budget. Notification transport failure is separate from run success and remains visible.
