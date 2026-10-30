# UI/UX screen specifications

Design version: 2.0 / 30 October 2026. Clean Tech is the single visual direction. This revision includes full assistant workflows, approval hygiene and web-first website-only focus controls. Dimensions below are proposed design targets to validate in a prototype.

## 1. Visual system

White #FFFFFF surfaces; light gray #F6F7F9 canvas; charcoal #17191F primary text; slate #596170 secondary text; subtle #E2E5EB borders. Deep purple #6438E8 is the sole vibrant accent for primary actions, selected controls, links and focus indicators. Pale purple #F0EBFF is a tint of that same accent. Use neutral labels and outlines for event categories, not additional hues. Success, warning and error states use explicit text and icons so meaning never depends on color.

Use a clean sans-serif typeface, 32-40 px major headings, 20-24 px screen headings, 14-16 px body and 12-13 px supporting metadata. Minimum sizes and contrast require device verification. Use an 8 px spacing rhythm with 4 px fine adjustments; 16-24 px panel padding, 8 px event corners and 12 px panel corners. Borders supply separation; shadows are reserved for floating surfaces. One primary action per decision context.

## 2. Screen S01 / Welcome and context

Purpose: establish the user's intent without forcing a long setup interview.

Layout: slim brand header, centered content column, progress indicator and a visible Save and exit action. Present two starting choices: plan a goal, or organize existing work. Explain what the assistant will prepare. Google Calendar and Gmail connection follow with separate permissions; manual availability and supplied meeting notes remain available. Declining connections shows reduced assistant coverage honestly.

Steps: choose intent; select planning horizon; describe the desired outcome; connect sources or continue manually. Next advances only after required information is supplied. Retain entries when navigating back. Connection denial explains what remains usable.

Components: intent cards, horizon selector, text field, source connector, progress stepper, inline validation and primary Continue button.

## 3. Screen S02 / Goal clarification

Purpose: turn a broad ambition into an actionable brief.

Layout: structured goal form with a compact conversational follow-up area. Show known answers as editable fields, not buried only in a transcript. Ask for success measure, current position, deadline, available time, priority, constraints and dependencies. Distinguish required answers from optional coaching context.

Steps: capture goal; ask the most relevant unanswered question; summarize assumptions; let user correct; generate the proposed plan. Do not require every possible question for a simple one-day task. AI unavailable state offers a manual goal and task form.

Components: outcome fields, date picker, capacity input, editable answer chips, question card, draft-save status and Generate plan action.

## 4. Screen S03 / Plan review and activation

Purpose: make the assistant's proposal concrete and reviewable.

Layout: outcome summary above milestone/task list; calendar preview alongside on wide screens; proposed loops below. Each item shows purpose, estimate, date or frequency, and assumptions. A capacity summary explains unused time or overcommitment.

Steps: inspect the plan; expand supporting reasons; edit tasks or timing; choose proposed items; review listed effects; approve. External publication names the calendar destination and effects explicitly. Keep local acceptance and remote publication distinct unless a single approval explicitly includes both.

No capacity: offer reduce scope, extend deadline or change availability. Rejected suggestions leave accepted work intact. Changed availability invalidates affected suggestions and asks for renewed review.

Components: milestone list, task editor, capacity summary, calendar preview, loop settings card and approval summary.

## 5. Screen S04 / Calendar home

Purpose: manage priorities and real-world time in one workspace.

Desktop: goals/tasks on the left, calendar in the center and collapsible coach on the right. With coach closed, use approximately 26% / 74%; constrain sidebar to a usable range. At 1440 px, an illustrative open layout is 272 px sidebar, 760 px calendar, 312 px coach, two 24 px gutters and 24 px outer margins on each side, totaling 1440 px. Collapse the sidebar or overlay the coach when the calendar becomes too narrow. This is a prototype target, not a fixed rule.

Left: quick capture; expandable season goals with tasks; support areas; calendar/source filters. Center: date navigation, Day/Week, all-day row, hourly grid, current-time marker, source freshness and proposal strip. Right: today's sync, pending decisions, follow-ups and contextual chat.

Steps: expand a goal; drag a task into time or use Schedule; inspect event; edit through popover; start focus. Dragging assistant-proposed changes does not bypass proposal review. Direct user edits identify any external save effects. Clicking a blank slot creates an explicit task/event/block choice.

Five- or seven-day display is a user preference; default seven-day week follows the reference. Work-hour display can be expanded. Source labels distinguish Google events, local events and goal blocks without a category rainbow. Keep this time fixed is visible on blocks; routine proposals respect it. Show third-party calendar edits as observed facts immediately, then offer corrective proposals if needed.

## 6. Screen S05 / Daily coach sync

Purpose: agree on today's core work before focus.

Panel structure: concise daily brief; today's constraints; proposed top priorities; proposed time blocks; pending decisions; chat input. Start with actual goals and available time. Ask about changed capacity and blockers. Explain priority tradeoffs briefly, with evidence links available on demand.

Steps: review the precomputed server brief; correct priorities; tell coach today's capacity; preserve accepted blocks and fixed times; inspect only justified proposed differences; approve individual changes or the enumerated batch; start selected task. Skipping sync preserves the existing plan. The assistant does not interpret a conversational acknowledgment as blanket authorization for unspecified changes.

Components: brief card, priority list, capacity prompt, proposal cards, evidence disclosure and Start focus action.

## 7. Screen S06 / Proposal review

Purpose: approve every assistant-proposed schedule adjustment.

Layout: compact summary strip in calendar; detailed drawer for review. Each change shows action type, previous state, proposed state, reason, affected task, source and destination. Additions use a dashed outline; moves show old/new positions with labels; removals remain visible until approved.

Steps: select a proposal; inspect before/after; edit or dismiss; approve; revalidate current calendar; apply; report local and external outcomes separately. A stale proposal shows the conflict and offers a refreshed version. Failure must preserve accepted state or explain any partial effects.

Components: change card, before/after comparison, dependencies, selection checkbox, destination summary, Apply selected, conflict banner and retry/reconcile action. Repeated approval is idempotent. Bundle related changes, supersede obsolete alternatives and remember equivalent dismissals until relevant facts change. Task adoption and external mailbox draft creation are reviewable effects; an internal generated preview is not an accepted task or sent message.

## 8. Screen S07 / Focus workstation and floating timer

Purpose: protect attention while keeping essential controls accessible.

Workstation: task title and intended outcome, timer, pause/end controls, Chrome website-blocking status and optional audio. Do not show native-app or cross-device protection. Hide nonessential calendar and chat content during focus, while allowing intentional return to planning. Starting a session uses only configured supported blocking rules.

Floating timer: compact neutral surface with purple active indicator, task label, elapsed/remaining time and pause/end. Drag handle, minimize and keyboard move controls; restore a safe position on viewport change. The first scope is in-app floating. Desktop companions with floating timers follow the web release on macOS, Windows and Linux; one-OS system website blocking is a separate later feature, not native-app blocking.

Steps: select task; confirm duration/objective; start; verify supported Chrome/profile website-rule status; optionally play audio; pause/resume; finish. Proposed pause behavior releases blocking while paused. Show unavailable controls honestly. Emergency unblock works even when the server cannot be reached; timed rules expire independently.

Audio controls: play/pause, volume, track/source and mute. No automatic sound before a user gesture. Audio failure leaves the timer usable. Licensing/source selection remains a delivery decision.

## 9. Screen S08 / Session completion

Purpose: record evidence and choose a useful next step.

Layout: short completion sheet with actual recorded duration; accomplishment prompt; explicit task status; optional outcome measure and optional self-rating. Do not infer task completion from timer expiry. Do not show a precise focus score without defined observation inputs and validation.

Steps: describe result; mark task complete or unfinished; record measurable progress if applicable; capture blocker; save. Offer a proposed continuation session or return to calendar. Saving session evidence does not approve a new calendar adjustment.

Components: duration summary, status control, note field, measure input, optional rating and next-step proposal.

## 10. Screen S09 / Follow-ups and loop settings

Purpose: let the user understand and control ongoing assistant work.

Follow-ups are coach-panel cards grouped by urgency and routine. Expand to inspect evidence, task owner, due date, draft and proposed action. Email sending and external changes require explicit authorization. Dismiss hides a finding; snooze changes reminder time; neither means the underlying commitment is complete.

Assistant exposes six template families configured through one short chat and a typed confirmation preview. Loop detail contains pinned template/profile version, purpose, goal/area scope, schedule, timezone, permitted sources, deterministic criteria, authority ceiling, stop/catch-up condition, quiet hours, notification destination, next run and last result. Chat cannot exceed the registered schema; style preferences affect writing only. Pause stops future runs; stop terminates the loop. Keep run history readable and errors actionable. Partial results name unavailable sources without exposing credentials or raw internal errors.

## 11. Screen S10 / Weekly review

Purpose: learn from the week and prepare a realistic next one.

Layout: outcome progress, completed work, scheduled versus recorded effort, repeatedly moved work, unresolved commitments and short reflection prompts. Focus time and goal outcomes remain separate. Place proposed next-week adjustments beside a calendar preview rather than burying them in prose.

Steps: inspect evidence; correct missing progress; decide carry-forward/drop/defer; discuss constraints; generate next-week proposal; approve exact changes. Defer changes a commitment deliberately; it is not silent rollover.

Components: outcome summary, effort comparison, carry-forward list, reflection form and next-week proposal review.

## 12. Component contract inventory

| Component | Main behavior | Required states |
| --- | --- | --- |
| Goal tree | Expand tasks; select scope; add goal | Empty, expanded, filtered, archived |
| Task row | Complete, inspect, schedule, drag | Candidate, todo, in-progress, done, cancelled |
| Calendar block | Inspect, move, resize, start focus | Local, external, proposed, stale, read-only |
| Proposal card | Explain, edit, accept, dismiss | Pending, superseded, conflicted, partial, applied, failed |
| Coach message | Clarify with source context | Streaming, cancelled, unavailable, retry |
| Floating timer | Move, minimize, pause, end | Running, paused, reconnecting, ended |
| Browser rule status | Report supported Chrome website rules | Active, paused, denied, offline, expired |
| Loop card | Configure, pause, inspect results | Active, paused, failed, partial, stopped |
| Event popover | Edit relevant details | Read-only, editable, recurrence choice, conflict |
| Source connector | Connect, scope, disconnect | Unconfigured, syncing, current, stale, revoked |

## 13. Responsive and accessibility behavior

Desktop keeps the calendar dominant. Tablet uses a coach drawer over the workspace. Phone defaults to day/agenda view with separate task and coach sheets; no squeezed seven-column grid. Preserve selected date/task when changing surfaces.

Support keyboard scheduling and resizing alternatives, visible focus, descriptive labels, meaningful dialog focus restoration, screen-reader announcements for approval and timer changes, reduced motion, text zoom and comfortable touch targets. Use text and icons for all statuses. Do not announce timer ticks continuously to assistive technology. Validate accessibility and measured contrast in the prototype and implementation.

## 14. Design validation walkthrough

Walk a user through: define a six-week goal; answer clarification; revise a proposed plan; activate a loop; run daily coach sync; schedule a task without dragging; approve a move; start focus; navigate with the timer; pause/unblock; finish without completing the task; handle stale Google data; review the week. Confirm comprehension of proposed versus accepted changes and which devices are actually protected.

This document specifies screen behavior, not a claim that the screens or all integrations are implemented. The web/desktop sequence and no-app/no-cross-device scope are fixed. Exact supported versions, first website-helper OS, audio licensing, session recovery and pilot targets remain open decisions.


## 15. Supporting views S11-S14

Today and Plan share S04: Today anchors the calendar and brief to the current day; Plan emphasizes week-ahead capacity and proposed changes. The shell remains calendar-first rather than introducing a competing home dashboard.

| View | Content and main steps | Components and critical states |
| --- | --- | --- |
| Commitments / S11 | Filter candidates, mine, waiting, reply debt and promises; inspect evidence; accept/merge; schedule fulfillment tasks; confirm resolution or defer with resume trigger | Ledger row, owner/due/source labels, evidence drawer, task links, merge review, partial-answer and reopened states |
| Goals / S12 | Define season/outcome; inspect plan, tasks and recorded progress; revise priorities; return to calendar for time decisions | Goal detail, outcome measure, capacity, milestone list, fixed-block links, insufficient-evidence trajectory |
| Review / S13 | Daily check-out, Friday wrap/week-ahead modes, scheduled-vs-logged time and inbox-noise coverage | Shared review record, carry-forward decisions, coverage labels, fresh deterministic fallback |
| Assistant / S14 | Pick template; short setup chat; confirm preview; manage sources/preferences/usage; inspect history; pause/stop | Template picker, typed configuration, authority diff, unsupported-request feedback, usage meter, degraded/paused states |

## 16. Background and budget UX

Feed items show produced-at/as-of, source coverage, notification tier and action status. Push permission denial offers an in-app path and opt-in email fallback; no duplicate fallback merely because an alert was not read. Missed runs coalesce into the latest useful finding. Respect quiet hours and daily caps while keeping pending decisions visible.

Usage meter shows scheduled loops, extraction, drafting and chat; identify reserved daily-brief capacity and one near-80-percent alert. Budget degradation is visible: full output, cached summaries with current deterministic checks, current deterministic digest, or paused low-priority AI. Never interpret unprocessed new mail as no reply debt.

## 17. Full assistant acceptance walkthrough

With the browser closed, a new permitted email and supplied meeting note are ingested. Candidate promises and waiting items are linked to evidence. The morning brief is generated before opening; permitted push/email follows delivery rules. Open Today, inspect the brief, accept an inferred task, reject a calendar move and verify it does not reappear unchanged tomorrow. Resolve a partial reply without prematurely closing the request; inspect a meeting dossier, approve a follow-up draft/send separately, run focus with Chrome website rules, check out and review the week. Repeat with revoked permissions, stale sources, expired cursor, low AI budget and a fixed block collision.
