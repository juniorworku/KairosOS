# Events, tasks and week drafts

Deployment remains paused. The local Plan screen now uses one agenda feed for goal blocks, local events and explicitly consented Google events from owned selected calendars (legacy primary-calendar access before selection). It offers Calendar/List views, a task sidebar, Add event, Schedule action, time-range selection, drag/resize, notes and proposal review. Independent tasks do not require a goal.

## Local data and operations

| Endpoint | Behavior |
| --- | --- |
| `GET /api/v1/agenda?start=YYYY-MM-DD&end=YYYY-MM-DD` | Combined owner-scoped feed; start inclusive, end exclusive, one through 366 days |
| `GET/POST /api/v1/tasks` | List/create independent tasks: title, notes, optional due date/goal, estimated minutes, todo/done |
| `GET/PATCH/DELETE /api/v1/tasks/{id}` | Read/edit/remove a task; deleting unlinks its appointments rather than deleting them |
| `GET/POST /api/v1/events` | List/create local event series with title, notes, timed/all-day bounds, timezone and optional task link |
| `GET/PATCH/DELETE /api/v1/events/{id}` | Read/edit/remove a whole local series |
| `PATCH/DELETE /api/v1/events/{id}/occurrences/{date}` | Override/cancel one occurrence, identified by its original local date |
| `POST /api/v1/blocks` | Schedule a goal action manually; notes persist with the block |
| `POST /api/v1/plan/draft` | Draft goal-action time around availability, local recurring events and pending destinations; explain empty results |
| `GET/POST /api/v1/plan/changes` | List pending move/removal previews or propose one for an accepted local goal block |
| `POST /api/v1/plan/changes/{id}/accept` | Revalidate current state/availability, then apply explicitly; repeated acceptance is idempotent |
| `POST /api/v1/plan/changes/{id}/dismiss` | Dismiss without changing the calendar block |

Mutations require the existing authenticated session and CSRF header. All records and links are ownership-checked. Owner locks serialize writes; no endpoint publishes a local event or task to Google automatically. Tasks/events/exceptions/proposals use typed `planning_records` aggregates, consistent with the current persistence design. Deleting a goal unlinks independent tasks and clears its block proposals.

## Recurrence and dates

Local repeats support daily, weekly, monthly or yearly frequency, interval 1–52, selected weekdays for weekly repeats, and an occurrence count (maximum 500) and/or an end date (within five years). Unbounded repeats are rejected. Monthly repeats keep the original day of the month; yearly repeats keep the original month and day. Missing dates (such as February 31 or February 29 in a non-leap year) are skipped, without shifting future occurrences. The occurrence count counts actual valid instances. Arbitrary RFC recurrence strings and ordinal weekday rules are not implemented.

A series keeps its local wall-clock times in its IANA timezone across daylight-saving changes. Nonexistent spring-forward occurrences are skipped; ambiguous times preserve the original fold. Timed API inputs require offsets. All-day API bounds are local midnights with an exclusive end date; feed values use calendar dates. The UI distinguishes editing this occurrence from the entire series. Explicit occurrence field overrides survive later series edits; cancelled occurrences can be restored through an occurrence edit. Moved occurrences are included in the range they move into.

Local appointments may overlap each other, as normal calendar events do. Goal blocks and generated drafts avoid local appointments and recurring commitments, manual busy intervals and saved Google availability, with the planning buffer and daily capacity checks. Scheduling a task creates a linked local appointment; completing its task changes the feed status. Tasks are not silently auto-scheduled by Draft week.

## Drafts and proposed changes

Draft week uses active goals/actions covering the selected week. It returns a message for an empty account, zero/too-small action time, dates outside the week, already-planned targets, insufficient capacity or a past week. It does not create invented goals or tasks. Existing proposed additions can be reviewed before local acceptance.

When a future accepted local goal block no longer fits its goal or availability, a draft can propose a move to an available slot, or removal if no slot fits. The accepted block stays unchanged until Apply change. Dragging an accepted block or selecting Propose move/removal also creates a preview. Before/after snapshots, reasons, ghost destinations and removal marks are displayed. Applying rechecks the snapshot, active focus, current events/busy intervals and capacity. Changed state returns a conflict; it never silently overwrites newer edits. Pending destinations are reserved during subsequent drafts. Removal cancels the local reservation and preserves its history. Published Google-linked blocks are changed in Google and reconciled rather than locally moved/removed.

## Google details and privacy

Availability-only consent continues to use free/busy. Showing primary-calendar names and notes requires a separate explicit `calendar/connect?details=true` flow with the owned-calendar events read-only scope. A prior provider grant alone does not enable details locally. Named timed/all-day events and recurring instances are cached with encrypted titles/notes and owner/date indexes through migration `0005_google_event_details`.

Google source items require separate explicit edit consent and owned-calendar capability for editing in Kairos; otherwise Open Google Calendar is the editing path. Owned published goal blocks are deduplicated from the external feed. Provider outages retain local and cached items with a refresh warning. Optional detail-refresh failures do not roll back successful availability/app-calendar synchronization.

Hide Google event names and notes calls `DELETE /api/v1/calendar/details`, purges the server detail cache and the current account's cached browser agenda reads, and stops detail reads without disconnecting availability. It does not claim to revoke an existing Google OAuth grant. Disconnect/account deletion clear detail caches. Encrypted cache payloads are omitted from account export; local tasks/events/notes remain exportable. Google names/notes and local event notes are not added to coaching context.

GET agenda/task/event responses can be cached in account-scoped IndexedDB for offline reading. Logout clears private reads; changing accounts hides other owners' caches. New calendar/task mutations require connectivity; the existing narrow offline check-in/session-end queue is unchanged.

## Remaining limits

- Selected owned Google calendars now support details and event CRUD; shared sources remain availability-only. Whole-series Google edits are external.
- Local recurrence supports daily/weekly/monthly/yearly; ordinal weekday rules and external recurrence editing remain future work.
- Plan move/removal proposals target accepted local goal blocks. Local appointment edits are explicit direct edits, not AI-generated proposals.
- No live Google/model-provider acceptance, new phone installation matrix or public deployment is implied by controlled provider/browser tests.

## Multi-calendar selection and Google event editing

Migration `0006_multi_calendar` adds encrypted calendar-list metadata, persisted selection and explicit selection/editing consent flags. Settings offers separate OAuth upgrades for choosing calendars and editing owned-calendar events. Previously granted OAuth scopes alone do not turn on editing. Selected sources contribute availability; owned selected calendars can contribute names/notes with details consent. Shared calendars remain availability-only under the deliberately narrow scopes. Deselecting sources clears server detail/availability snapshots and current-account browser agenda snapshots; late pre-selection reads cannot repopulate the old offline agenda.

`GET/PUT /api/v1/calendar/calendars` lists capabilities and saves selection. `GET /api/v1/calendar/events/{calendar_id}/{event_id}`, `POST /api/v1/calendar/events`, and conditional `PATCH/DELETE` on the event path expose owned-calendar CRUD. UI IDs are encoded in routes; raw provider event IDs and ETags are retained. Save/Delete explicitly changes Google; it is distinct from draft acceptance and goal-block publication. Stable create IDs avoid retry duplication. ETag conflicts require reloading and reviewing the newer event. Recurring instances can be edited/deleted individually; whole-series/rule/all-following changes open in Google. Selected calendar names/notes remain encrypted at rest; no remote event title or note is added to coaching context.

Provider behavior is covered with controlled HTTP and PostgreSQL tests. Live Google consent/writes remain a credentialed acceptance step; no live remote calendars were changed in this pass.
