# Product description and scope

Version 2.0 / 30 October 2026. Target product specification; capabilities below are planned unless separately verified in the implementation record.

## Purpose

Kairos is a web-first AI executive assistant that turns goals and commitments into an agreed plan, then follows up until each item is completed, cancelled, or deliberately deferred. It serves founders, solopreneurs, freelancers, and team leads in a personal workspace; shared team administration is deferred.

Users already have calendars. Kairos earns its place by keeping a commitment ledger, detecting what needs attention, preparing briefs and drafts, and bringing concrete decisions back for approval. Its calendar-first interface connects this assistant work to available time, goals, and focus.

## Product promise

Define what matters. Agree on a realistic plan. Activate follow-up loops. Work with protected focus. Kairos tracks the evidence, prepares the next useful action, and asks before changing the schedule or sending anything.

## Five assistant engines

| Engine | Responsibility | Authoritative inputs and outputs |
| --- | --- | --- |
| Commitment ledger | Track promises, reply debt, waiting items, meeting follow-through and VIP attention | Commitments from permitted email, supplied meeting notes and manual entry; linked tasks, resolution evidence and reviewable follow-ups |
| Calendar guardian | Detect conflicts and overload, protect/recover focus time, propose freed-time use and travel buffers | Synchronized calendar events and focus reservations; findings and proposed calendar changes |
| Briefing composer | Prepare daily briefs, week-ahead preparation, meeting dossiers and Friday wraps | Reads shared engine facts and summaries; produces a coherent brief without creating competing facts |
| Goal engine | Support seasons, goal clarification, GPS-style planning, weekly plans, trajectory and velocity | Goals, tasks, measurable progress and recorded effort; reviewable plans and evidence-based adjustments |
| Insights | Explain where time went and what creates inbox noise | Calendar/session and email statistics, with coverage and freshness; descriptive reports and proposed fixes |

These are logical responsibilities, not a requirement for five autonomous agents or separate deployed services. They share a single context layer and durable records. Deterministic code owns checks, ranking rules, dates and capacity calculations; bounded AI steps extract or classify new text and write drafts, summaries and coaching.

## Product model

A season is an optional longer planning container. A goal defines an outcome and success measure. A plan connects milestones, tasks, time allocations and follow-up loops to that outcome. A support area holds ongoing responsibilities without an artificial goal.

A commitment records something owed, the responsible person, who expects it, its source, due date if known, and resolution evidence. Tasks are actions that fulfil commitments; they are not duplicate commitment records. Independent personal tasks remain supported. A calendar block reserves time; a focus session records effort. Task completion, commitment resolution and goal progress are separate decisions and evidence.

Planning horizons are one day, one week, two weeks, four weeks, six weeks and twelve weeks. Longer plans do not reserve every future hour by default. Daily coaching preserves accepted blocks and proposes changes only when constraints or user priorities change. Users can mark a block as fixed; conflicting work is surfaced for a decision rather than silently moving it.

## Loops and authority

A loop is an instance of a fixed, versioned, typed template with selected declarative parameters. Its specification defines trigger types, scope filters, deterministic checks, permitted action types, an authority ceiling, context recipe, model tiers, run/token caps and a stopping condition. Chat fills in that specification and presents what runs, when and why for confirmation. Parameters can lower authority but cannot exceed the template ceiling. Unsupported requests receive an explanation and the nearest supported option; the miss is recorded for product review.

The six starter template families are Daily brief, Daily check-out, Goal check-in, Overdue and slipping work, Focus rescue, and Weekly review. Friday wrap and week-ahead prep are modes of Weekly review. Daily coach sync is the interactive planning conversation that uses the brief; it is not a seventh ambiguous background template. Specialized assistant engine checks and output profiles must be mapped to the fixed catalog before release; see the feature catalog for the proposed mapping and unresolved boundary.

Free-text preferences may personalize output wording, length and order. They cannot alter checks, triggers, permissions or executable actions. Tasks, drafts and calendar actions inferred by the assistant are presented for approval; reading, deterministic analysis and briefing generation within granted access can run in the background. Correspondence and follow-up messages require exact per-message approval. Activating a notification loop authorizes its scheduled push/email delivery within configured limits. Every assistant-proposed schedule adjustment requires approval.

## First-release boundary and build order

The first public release must deliver a full executive-assistant experience across the five engines, including commitments from email, supplied meeting material and manual entry. Calendar/goal/focus-only milestones are internal increments, not the released product.

Build Google Calendar reading, synchronization and approved publication with goals and tasks first; add meeting ingestion and follow-through next; then email ingestion and assistant workflows. Complete and verify the integrated assistant before first-release acceptance. Gmail is the proposed initial mail provider; supplied notes/transcripts are the first meeting input. Confirm import channel details before implementation; additional providers remain later work.

The web app comes first. It includes the calendar workspace, coaching, assistant workflows, in-app floating timer, optional lo-fi audio and Chrome website blocking. Desktop companions for macOS, Windows and Linux follow, including a system-floating timer where supported. Later system-wide website blocking starts with one selected desktop operating system. Native application blocking and cross-device blocking are excluded promises. The device owns session expiry and unblock recovery.

## Background operation and cost

Server-side loops run even when the UI is closed. Each template defines a catch-up policy for missed runs. In-app results are the record of truth; web push and email fallback follow delivery preferences, permission and failure rules. Notification tiers are quiet, scheduled, nudge and urgent, with quiet hours and a daily limit.

Sources synchronize once into the shared store. Rolling summaries and content hashes support incremental processing; routines query the store instead of independently rereading providers. Context packs include bounded structured facts and source references. Usage is recorded per run and purpose, with reserved daily-brief capacity, per-run/per-loop caps and a global daily stop mechanism. When AI budget is constrained, fall back to clearly dated cached summaries or a deterministic digest and visibly pause lower-priority AI work.

## Success measures

Prioritize commitment resolution, useful follow-up acceptance, timely reply handling, accurate and ready-before-open briefs, and reduced missed obligations. Also track time to first approved plan, goal outcome check-ins, session completion, proposal edit/rejection, notification dismissals and AI cost per purpose. Separate calendar reservations, recorded effort, task completion and measured outcomes. Set pilot targets after baseline usage; collect only consented telemetry.

## Boundaries

Keep the interface minimal: calendar as the main workspace; contextual panels and drawers instead of a page for every routine. Use original Kairos copy and identity. Avoid invented progress, unexplained scores and automatic rescheduling. Broader connectors, native audio capture and AI handoff require separate capability and consent validation; they are not prerequisites for importing meeting notes into the first release.
