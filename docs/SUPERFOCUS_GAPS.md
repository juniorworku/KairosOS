# Superfocus reference and Kairos gaps

Reviewed 28 October 2026: [Superfocus](https://www.superfocus.me/). This assessment uses the public planning, focus and trajectory illustrations, compared with Kairos source and local checks. The signed-in Superfocus application was not tested; marketing illustrations and integration logos are not proof of shipped behavior.

## Direction

Superfocus is the primary workflow and composition reference. Kairos retains its own branding and shadcn/ui components. The owner authorized color after the initial monochrome pass: warm neutral surfaces, lavender planning and green recorded progress now reinforce labels and border treatment in light and dark themes. The central workflow is goal → dated plan → focus → outcome check-in → review → next week. Promotional claims, testimonials and subscription UI are outside the personal app scope.

## Implemented connections

| Area | Implemented in this pass | Remaining limits |
| --- | --- | --- |
| Calendar workspace | Date/goal/block/task context, working-hour framing, selected-source availability and encrypted details, calendar picker, version-checked owned Google event creation/edit/delete | Live Google consent/write acceptance; shared calendars remain availability-only; whole-series remote edits open in Google |
| Draft review | One added/moved/removed review, before/after times, explicit Keep/Discard and Accept remaining; publication stays separate | Structured model recommendations do not contain mutation IDs; opening a recommendation does not apply a change |
| Seasons and goals | Persisted season creation and assignment, preselected goal dates, countdown, recorded versus expected outcome pace and next accepted action | Next actions cover the displayed current/following-week window; no invented composite score |
| Today | Running-session priority, next accepted action, unified local/Google agenda, cached-data warning, due tasks and check-in/review links | Named Google data still requires explicit consent and live provider acceptance |
| Focus | Compact timer, linked check-ins and review, plus opt-in Linux executable suspension with independent recovery, private local configuration and authenticated reports | Native desktop-app/device acceptance and Windows/macOS support; no attention measurement. Both recovery processes being forcibly stopped requires manual recovery |
| Review and coaching | URL-driven review week, planned commitments versus logged effort, next-week links, visible evidence and explicit sharing consent, structured suggestion navigation and before/after goal-edit previews | Live provider quality needs credentialed evaluation; timing/distraction patterns are not inferred from totals |
| Recurrence | Daily/weekly/monthly/yearly local repeats, original date anchoring, skipped missing dates, wall-time/DST handling and occurrence overrides | Ordinal weekday rules, arbitrary RFC rules and external recurrence editing |
| First use and feedback | Create a season, add/assign a goal, review work hours, draft time, start a session and record outcome progress through contextual controls | Broader installed-device and long-running usage acceptance |

## Data continuity

Cancellation-aware reads prevent canceled pre-write snapshots from overwriting refreshed offline data. The initial empty-week query race is covered by a deterministic regression. Account-scoped offline reads, narrow queued writes, explicit calendar acceptance, ownership checks and provider-consent boundaries remain intact.

## Still separate milestones

- Credentialed Google write/consent acceptance; broader shared-calendar detail/write scopes and whole-series remote editing. AI coaching was unchanged in this pass.
- Apple/Outlook/meeting-note integrations and optional licensed audio.
- Measured cross-device attention, Windows/macOS app blocking and broader OS controls. Linux selected-app blocking is implemented and tested.
- Useful, explainable definitions and validation for any Plan strength/Compass score.
- Installed phone/browser matrix, production operations and deployment. Deployment remains paused.

The three implementation agents handled calendar/review, Today/seasons/goals, and Focus/coaching. The primary agent integrated shared state, task context, recurrence, visual verification and complete workflow tests. Exact final results are in [Verification](VERIFICATION.md).

## Calendar/native/appearance verification pass

The calendar backend/UI, native Linux companion and appearance controls were implemented with three agents and independently integrated/reviewed. Warm light is now the default; sidebar/mobile light/dark controls persist through reload and keep the existing system option. A self-hosted pre-paint script honors saved preferences without relaxing CSP. Selection changes clear both current-account memory and offline agenda snapshots, and old reads cannot restore deselected sources.

Native blocking was tested with real signals on disposable copied processes, including crash, offline, expiry, dead watchdog, root refusal and transient resume/identity failures. A live local Kairos pairing → focus → suspension → authenticated report → end → resume check also passed; its test resources were removed. Device reports are explicitly last-reported app-process counts, not proof of current blocking or attention. Setup remains opt-in on the Linux host: choose executable paths and run the companion. No system installation/autostart or real application suspension was performed.

Detailed final results are recorded in VERIFICATION.md. Deployment remains paused.
