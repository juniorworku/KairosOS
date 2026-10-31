# Features and integration catalog

Version 2.1 / 31 October 2026. Planned release scope; this catalog does not certify existing implementation.

## Release contract

The first released web product is an executive assistant across the commitment ledger, calendar guardian, briefing composer, goal engine and insights. Calendar/goals/tasks, meetings, then email is implementation order. Internal increments do not redefine the public release as a planner-only MVP.

## Five-engine feature inventory

Cadences below are proposed defaults from the requested workflow inventory, configurable within each template's allowed values and the user's timezone. All assistant actions remain reviewable proposals; detected facts and prepared reports may appear automatically within granted access.

| Engine | Fixed check or output profile | Default cadence/trigger | Result |
| --- | --- | --- | --- |
| Commitment ledger | Promise tracker | Daily and relevant source changes | Unresolved promises, owners, due dates and evidence |
| Commitment ledger | Waiting on them | Twice weekly | Outstanding requests and nudge drafts |
| Commitment ledger | Reply debt | Daily | Ranked unanswered requests with reply drafts |
| Commitment ledger | Meeting follow-through | After supplied notes arrive; evening recap | Proposed commitments/tasks and follow-up drafts |
| Commitment ledger | VIP watch | Configured threshold checks | User-selected VIP attention findings and draft replies |
| Calendar guardian | Calendar sentinel | Daily and relevant calendar changes | Double bookings, missing links and overloaded days |
| Calendar guardian | Focus rescue | Daily/weekly reservation check and relevant changes | Unified focus protection/recovery proposals; replaces separate focus guard/defense routines |
| Calendar guardian | Freed time | Meeting cancellation or shortened event | Suggested use of the newly available slot |
| Calendar guardian | Travel buffer | Relevant in-person event change | Proposed travel reservation, with route/duration assumptions visible |
| Briefing composer | Daily brief | Morning before configured delivery time | Priorities, obligations, meeting prep and pending decisions |
| Briefing composer | Meeting dossier | Before external meeting | Available relevant history, open threads and promises |
| Briefing composer | Friday wrap | Weekly review: wrap mode | Accomplishments, unresolved work and carry-forward decisions |
| Briefing composer | Week-ahead prep | Weekly review: preparation mode | Next week's decisions, constraints and proposed plan |
| Goal engine | Goal check-in and slipping-work checks | User-selected schedule or supported threshold | Outcome check-in, stalled work and specific proposed fixes |
| Goal engine | Season/GPS-style planning and weekly plan | On explicit planning request | Clarified goals, milestones, tasks, capacity-aware blocks and loops |
| Goal engine | Trajectory and velocity | After relevant recorded progress | Evidence-based trend with coverage and uncertainty |
| Insights | Where your week went | Weekly | Scheduled versus recorded effort, categories and trends |
| Insights | Inbox noise | Every two weeks | Email volume patterns and proposed rules |

Travel buffers must work with user-entered travel time or an explicitly chosen routing source; the assistant must not invent travel duration. Meeting and email coverage limitations remain visible. Relationship-cooling analysis is later scope, outside the stated first-release Insights inventory.

## Six starter template families

| Template family | Scope | Purpose and supported modes |
| --- | --- | --- |
| Daily brief | Global | Prepare the morning brief from shared facts and pending decisions |
| Daily check-out | Global | Evening reconciliation and `/done`; capture outcomes and unfinished work |
| Goal check-in | Per goal; ledger checks also allow global/area scope | Review progress and goal-specific next actions; promise/waiting checks use explicit scope exceptions |
| Overdue and slipping work | Global or per goal | Detect overdue commitments/tasks and repeatedly postponed work |
| Focus rescue | Global | Calendar-guardian checks and proposed protection/recovery |
| Weekly review | Global | Friday wrap and week-ahead prep modes using shared review data |

Daily coach sync is the interactive conversation that turns brief/context into an approved day. It preserves accepted blocks, respects fixed-time choices and does not run a new full-week rescheduler every morning.

### Confirmed workflow catalog

Confirmed 31 October 2026: reply debt, waiting-on-them, VIP watch, meeting follow-through and meeting dossiers run as built-in checks/output profiles inside the six templates. They are not additional top-level selectable templates. The five engines retain the full capability inventory above.

Each built-in check has registered trigger options, scope, deterministic criteria, outputs, context recipe and authority ceiling. Users tune and enable supported checks in the template setup rather than composing arbitrary automation. The [registered check mapping](AUTOMATION.md) supplies the design configuration; implementation must validate each schema and trigger. Family names do not restrict every check to the cadence implied by the family name.

## Template and loop contract

Every template defines its ID/version, supported trigger kinds (schedule, source event, threshold), scope filters, deterministic check library, allowed output/action types (brief, notification, draft, proposal), authority ceiling, stop condition, catch-up policy, context recipe, model tier per AI step and token/step/tool-call caps. Each loop stores template ID/version and validated chosen values. Template upgrades cannot silently change user authority or behavior; changed behavior needs a reviewable migration/confirmation policy.

Chat chooses a supported template/profile and fills typed fields. A confirmation preview names what runs, when, which sources it reads, what it may prepare and when it stops. Values can reduce the authority ceiling, never raise it. Unsupported requests show the nearest supported option and log the miss. Writing preferences such as brief length and tone affect prose only, not trigger/check/action logic.

## Approval and resolution

Bundle related changes into one review with dependencies. Replace obsolete proposals and remember dismissals until relevant facts change. Explicit approval covers the exact listed task, draft or calendar effects; correspondence never sends without exact per-message approval. Activated notifications use standing delivery authorization within their configured limits. External calendar publication identifies its destination. Accepted weekly blocks remain the baseline; new constraints or user priorities justify proposed adjustments. A fixed-time block is not moved by the assistant.

Commitments close using type-appropriate evidence. A personal task requires explicit completion; an incoming reply is evidence of a response, not proof that the request was resolved. Ambiguous meeting and email conclusions require confirmation. Goal completion follows its defined success measure. Reminders, elapsed time and sending a message do not automatically close the underlying obligation.

## Integration and platform boundary

| Integration/capability | First-release or later role | Verification boundary |
| --- | --- | --- |
| Google Calendar | First-release foundation: read availability/details as permitted, synchronize, publish approved changes | Preserve separate consent, source capabilities, version conflicts and real-provider acceptance |
| Gmail | First-release commitment extraction, reply/waiting/VIP checks, drafts and noise statistics | Proposed initial mail provider; least-privilege access, retention and provider verification required; additional providers later |
| Supplied meeting notes/transcripts | First-release meeting context, dossiers and follow-through | Select manual/import channel and retain attribution; do not imply automatic attendance/capture |
| Outlook calendar / Apple Calendar | Later calendar connectors | Validate supported protocol, read/write scope and conflict behavior before promising parity |
| Slack, Fathom, Granola | Later context/meeting connectors | Validate accessible source capabilities, consent and retention |
| Zoom / Meet / Teams / Webex capture | Later native audio capture | Local permission, supported OS/capture mechanism and recording notices; not a web-only promise |
| Chrome extension | First-release website blocking | Verify actual Chrome lifecycle and recovery behavior; no native-app blocking claim |
| Desktop companions | After web: macOS, Windows and Linux timer/session surface | Validate each OS; system-floating behavior is a device capability, not assumed browser parity |
| System-wide website helper | Later, one selected desktop OS first | User-approved bounded website rules, independent expiry and recovery; no application or cross-device blocking |
| External AI handoff | Later reviewed task/context transfer | Destination, context limits and completion/status contract required |

The repository contains a legacy opt-in Linux helper that can suspend configured native executables. That existing code is outside the revised launch product scope; it is not evidence of promised macOS/Windows/Linux native-app blocking, and this documentation revision does not remove or alter it.

## Background delivery and notifications

Loops run server-side while the UI is closed, with template-specific catch-up and deduplication. Store the result in the in-app feed first. Deliver through permitted web push, then email fallback according to configured preferences and delivery outcomes; do not send duplicate fallback messages merely because a user has not opened the app. Quiet, scheduled, nudge and urgent tiers obey quiet hours and daily limits, with any urgent exception explicitly configured.

Show next run, last run, partial-source warnings, missed-run handling and paused budget status. Delivery fallback rules are defined in Automation; exact catch-up windows and urgent-tier exceptions must be configured before activation. The device, not a server job, owns focus session expiry and unblock recovery.

## Shared context and budget behavior

Adapters sync each source once into owned people, threads, meetings, commitments, goals and summary records. Routines query this store, not providers directly. Hashes and rolling summaries limit AI work to changed material; a bounded initial backfill limits first-connection processing. Unchanged facts can reuse summaries, but deadline/time-threshold checks still run as time advances.

Use code for overdue/waiting calculations, conflict detection, ranking and capacity math. Use a lower-cost validated AI step for extraction/classification and a stronger model only for approved writing/coaching paths. Context packs have source references and token ceilings; sub-steps share structured results rather than raw transcripts.

Record tokens and cost per run, loop and purpose. Reserve daily-brief capacity separately from chat; cap each run/loop and support a global daily stop mechanism. Provide a usage meter and one near-80-percent alert. Numeric quotas follow pilot observation; hard safety caps must still exist during the pilot. Degrade from full output to dated cached summaries, deterministic digest and explicitly paused low-priority AI loops. Never represent a cached output as newly analyzed evidence.
