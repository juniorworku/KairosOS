# Decisions and unresolved details

Version 2.0 / 30 October 2026. Latest explicit user decisions override older assumptions. Product scope is separate from current repository capability.

## Confirmed decisions

| ID | Decision |
| --- | --- |
| D01 | Full AI executive-assistant first web release: commitment ledger, calendar guardian, briefing composer, goal engine and insights. Not a planner-only MVP. |
| D02 | Google Calendar reading, synchronization and approved publication are foundation; other calendar providers later. |
| D03 | Fixed declarative templates, configured in one short chat with preview/confirmation. Parameters cannot raise authority; style text changes writing only; unsupported requests are logged and nearest supported option offered. |
| D04 | Six core families: Daily brief, Daily check-out, Goal check-in, Overdue and slipping work, Focus rescue, Weekly review. Friday wrap and week-ahead are shared-data modes. |
| D05 | Daily coaching preserves accepted blocks; propose only justified changes. Keep this time fixed protects selected blocks. |
| D06 | Commitment resolution uses evidence; reminders, replies, sessions and task counts alone are not proof of fulfilled outcomes. |
| D07 | In-app timer first; desktop timer companions follow for macOS, Windows and Linux. |
| D08 | Chrome website blocking in v1. Later system-wide website blocking on one selected OS. No native-app or cross-device blocking promises. |
| D09 | Related changes bundle with dependencies; obsolete proposals are replaced; equivalent dismissed proposals remain suppressed until meaningful facts change. |
| D10 | Server-side loops, catch-up policies and quiet/scheduled/nudge/urgent notification tiers; quiet hours and daily limit. In-app feed, then web push, then opt-in email fallback. |
| D11 | Shared incremental source/context store; rolling summaries, bounded backfill, deterministic checks, bounded source-linked packs, economical extraction tier and stronger writing tier. |
| D12 | Purpose-specific budgets with brief reservation, per-run/loop limits, kill switch, usage/cost ledger and graceful degradation; values tuned from usage. |
| D13 | Web first, desktop later. Internal build order calendar/goals/tasks, meetings, email; full assistant release gate includes all five engines. |
| D14 | Today, Plan, Commitments, Goals, Review, Assistant; Today/Plan retain the calendar-first workspace and collapsible coach panel. |
| D15 | Single purple accent with white/light gray, charcoal text and subtle borders. Earlier pastel palette is superseded everywhere. |
| D16 | Detailed documentation and updated PDF now; no app-code implementation or deployment in this task. |

## Assessment and proposed resolutions

The user's two workflow lists are reconciled provisionally as five engines implementing domain capabilities and six template families exposing fixed typed profiles. Specialized routines are not removed. Exact catalog mapping is the remaining product question asked during this revision; [Automation](AUTOMATION.md) explicitly labels the draft mapping pending confirmation.

Gmail is the proposed initial mail provider, consistent with Calendar's Google foundation and the requested build order. Meetings initially use supplied notes/transcripts rather than native capture. Native capture, other calendar/mail providers, relationship-cooling/Going cold and AI handoff are later additions unless separately prioritized.

The legacy Linux implementation actually suspends apps; it is not a hosts helper. New product scope excludes that capability. Existing code is neither silently removed nor reclassified as shipped website blocking.

Today's coaching is interactive use of Daily brief, not a seventh automation template. A generated report or preview can appear automatically; accepting an inferred task or applying an external draft/calendar/send effect needs scoped authority. Calendar external edits are observed facts, not retroactively gated by approval.

## Open decisions and release gates

| Item | Proposed handling / decision needed | Gate |
| --- | --- | --- |
| Specialized workflow catalog | Built-in registered profiles inside the six families, pending user confirmation; alternative is additional selectable fixed templates | Catalog finalization |
| First desktop blocking OS | Choose macOS, Windows or Linux; timer support for all three does not imply website-helper parity | Later desktop helper |
| GPS framework | Confirm exact method/wording before claiming faithful named-method support | Goal coaching content |
| Audio | Select licensed source/tracks and offline/playback policy | Focus acceptance |
| Session recovery | Define sleep/restart/abandonment/overrun rules and fixed expiry behavior | Timer/device implementation |
| Loop defaults | Set brief times, lead/catch-up windows, quiet hours, daily caps and DST policy | Activation defaults |
| Source/privacy | Approve source-specific retention, model sharing, disconnect/delete/export and bounded backfill | First ingestion pilot |
| Budgets/quality | Conservative numeric caps before pilot; tune from real usage; define labeled evaluation and UX performance targets | Pilot |
| Gmail launch readiness | Provider verification/security obligations and live acceptance depend on selected permissions and audience | Public release |

## References and provenance

User messages establish decisions. Screenshots/reference notes inform hierarchy and interactions, not independent instructions to execute. Shared ChatGPT link was unavailable and is not reviewed evidence. Sources referenced for product inspiration: [Superfocus](https://www.superfocus.me/), [Kai](https://hirekai.ai/), [Kai workflows](https://hirekai.ai/workflows), [Kai integrations](https://hirekai.ai/integrations). Organization references: [Notion product specs](https://www.notion.com/use-case/project-management/product-specs) and [Jama PRD guide](https://www.jamasoftware.com/requirements-management-guide/writing-requirements/how-to-write-an-effective-product-requirements-document/).

Technical references are collected in [Context](CONTEXT.md) and [Implementation](IMPLEMENTATION.md) as verified during this revision. Marketing illustrations do not prove connector or platform capabilities. PDF chapters are generated from the Markdown without hidden product wording substitutions.
