# Interface architecture

## Clean Tech visual system

White and light-gray surfaces, deep charcoal typography, ample white space and subtle borders. One vibrant deep-purple accent (#6438E8) supports primary buttons, links, selection and focus. A pale tint of the same accent is permitted. Neutral labels/icons/outline patterns distinguish categories, sources and statuses; no multi-color pastel category palette. Original Kairos text and assets follow the supplied reference's hierarchy and simplicity.

## Six views, one calendar-first entry

| View | Role |
| --- | --- |
| Today | Default entry: calendar-first shell anchored to today, with morning brief/daily coaching and urgent decisions. No metric-heavy replacement dashboard. |
| Plan | Same shell for week-ahead work, full calendar, tasks, proposals and capacity. Preserve date/selection when switching context. |
| Commitments | Accepted/candidate obligations, replies owed, waiting, promises and linked tasks; inspect evidence and resolution. |
| Goals | Seasons, goal setup, milestones, plans and trajectory; task scheduling returns to the same calendar. |
| Review | Daily check-out, Friday wrap/week-ahead modes, outcome and coverage-aware effort insights. |
| Assistant | Template setup through short chat, workflow settings/history, preferences, usage and connected sources. |

## Workspace composition

Coach closed: left goals/tasks/support panel approximately 26%, calendar approximately 74%, with practical min/max widths. Coach open: protect a minimum usable calendar and collapse the left panel or show the coach as an overlay at laptop widths. At an illustrative 1440 px viewport: 24 px outside margins each, 272 px sidebar, 760 px calendar, 312 px coach and two 24 px gutters sum to 1440 px. This is a prototype example, not a universal breakpoint rule. An overlay is preferable when a seven-day grid becomes unreadable.

Left panel has quick capture, expandable goals/tasks, support areas, filters and sources. Center has date navigation, day/week switch, all-day row, hourly grid, now marker, source freshness and proposal review strip. Right panel holds the brief, interactive daily coaching, follow-ups, approvals and chat. A compact primary navigation avoids adding another oversized sidebar.

## Interaction rules

Drag tasks to schedule; offer equivalent keyboard/form controls. Inspect event details in a popover/drawer. Direct edits expose local/external effects. Assistant additions use dashed outlines, moves show before/after, and proposed removals remain marked until approved. Keep this time fixed is visible on blocks and respected by planning. Third-party changes display as observed facts; corrective changes require approval.

Proposals bundle related changes, show dependencies and destinations, suppress equivalent dismissed suggestions and replace obsolete versions. A concise card expands for evidence and detailed effects. Approval is specific to a version; chat is not a general grant of authority.

## Focus

Dedicated task-centered view with optional audio, in-app timer and Chrome website-rule status. No native-app or cross-device protection indicators. Device owns expiry and escape. Later desktop companions supply timer access on macOS/Windows/Linux; later system website blocking starts with one supported OS. All device capabilities are labeled accurately.

## Responsive and accessible

Desktop prioritizes the calendar; medium screens use drawers; phone uses day/agenda and task/coach sheets. Preserve selected date and task. Provide keyboard alternatives, focus restoration, text zoom and reduced motion. Status uses words/icons as well as styling. Loading, empty, partial, stale, denied, offline, failed and budget-limited states are explicit. See [screen specifications](SCREEN_SPECIFICATIONS.md) for components and step-by-step flows.
