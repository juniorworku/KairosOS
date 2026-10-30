# Requirements and acceptance criteria

All F requirements below belong to the first full executive-assistant web release. Build increments are internal validation stages, not progressively weakened release promises. Later-platform requirements are labeled L. Proposed numerical caps are intentionally not invented; they must be configured before any AI pilot and tuned from measured usage.

## Product requirements

| ID | Capability | Acceptance criteria |
| --- | --- | --- |
| F01 | Goal and season planning | User selects day/1/2/4/6/12-week horizon; defines success, path, capacity, constraints, follow-up and authority. Adaptive questions and manual fallback work; draft can resume. |
| F02 | Plans and trajectory | Proposed milestones, tasks and time allocations show assumptions and capacity gaps. Measured outcomes, completed actions and effort remain distinct; insufficient data never produces invented progress or velocity. |
| F03 | Google Calendar foundation | Selected permitted calendars supply freshness-aware availability/details. Approved publication and changes reconcile using source versions and stable operation IDs. Expired sync cursors trigger controlled recovery. |
| F04 | Calendar-first interaction | Today/Plan share goals/tasks left, weekly/day calendar center and collapsible coach right. Drag/drop, resizing and equivalent keyboard/forms work; source, recurrence and external effects are visible. |
| F05 | Daily briefing and coaching | Server prepares morning brief before app opening. Interactive coach preserves accepted blocks, asks about changed priorities/capacity and proposes only justified differences. User may skip sync. |
| F06 | Exact approvals | Inferred task creation, saving a draft to an external mailbox, message sending and assistant calendar changes have versioned reviewable effects. Reports can render automatically. Direct user commands are authorization only for their explicit scoped effects. |
| F07 | Stable schedule | Keep this time fixed prevents automatic placement/move/removal suggestions for that block. Conflicts are still surfaced; user can explicitly unlock or request a scoped change. No approval silently clears the lock. |
| F08 | Commitment ledger | Email, supplied meeting notes and manual entry create sourced candidate commitments. Accepted commitments link fulfillment tasks; duplicate/ambiguous evidence is reviewed. Promise tracker, reply debt, waiting, meeting follow-through and VIP watch are available. |
| F09 | Resolution evidence | Task completion is explicit; an incoming reply is not automatically resolution. Waiting items resolve only on clear evidence or confirmation. Goal completion uses its success criterion; evidence and reopening history remain inspectable. |
| F10 | Calendar guardian | Checks cover conflicts, missing links, overload, merged Focus rescue, freed time and travel buffers. Outputs are findings/proposals. No physical travel estimate is invented without sufficient location/transport data. |
| F11 | Meeting assistance | User-supplied notes/transcripts support decisions, candidate commitments and follow-up proposals; dossiers use available history with provenance. Native recording is not required for this release. Unknown owners/dates remain unknown. |
| F12 | Email assistance | Gmail, the proposed launch mail baseline, supports bounded initial history, incremental ingestion, triage, reply debt, waiting evidence and draft proposals. Sending requires exact approval; permissions and provider acceptance are release gates. Outlook mail is later. |
| F13 | Fixed workflow setup | One short chat fills a supported template's typed parameters. Preview states what/when/why/sources/authority/stop condition; confirmation activates. Unknown requests offer nearest supported configuration and record a minimal redacted miss. |
| F14 | Predictable workflow logic | Six template families expose registered typed check/output profiles. Parameters cannot exceed template authority; free-text style preferences affect prose only. Template version changes never silently expand actions or sources. |
| F15 | Server operation | Runs occur with the browser closed. Every template defines catch-up, expiry and deduplication. Late reports remain useful; obsolete urgent notices are suppressed. Paused/stopped loops cannot emit new deliveries. |
| F16 | Managed delivery | In-app feed is durable. Web push is permission-aware; email fallback is opt-in and avoids duplicate sensitive content. Quiet/scheduled/nudge/urgent tiers obey quiet hours and configured daily limits. |
| F17 | Focus and audio | In-app movable/minimizable timer and focus workstation support pause/resume/end, reload recovery, optional licensed lo-fi/ambient audio and Chrome website blocking. No native-app or cross-device protection is claimed. |
| F18 | Focus evidence | Recorded active time excludes pauses; sleep/restart handling follows a documented policy. Completion records accomplishment, task status and optional outcome/self-rating separately. Device-local expiry and escape work without server access. |
| F19 | Weekly review and insights | Friday wrap/week-ahead share review evidence and differ by mode. Time-use and inbox-noise statistics label coverage and distinguish scheduled, logged and inferred time. Carry-forward is a decision, not silent rollover. |
| F20 | Shared context and costs | Sources ingest centrally; recipes build bounded source-linked packs. Deterministic checks precede AI. All runs record actual/estimated/unknown usage distinctly; purpose budgets protect briefing capacity. |
| F21 | Proposal hygiene | Related changes bundle with dependencies; obsolete alternatives are superseded. Dismissals suppress equivalent proposals until relevant facts change. Partial batch results and conflicts are explicit. |

## Nonfunctional requirements

| ID | Requirement | Acceptance criteria |
| --- | --- | --- |
| N01 | Access and consent | Ownership checks cover every entity. Source-reading, AI-sharing, notifications, publication and device-control permissions are explicit and revocable. Imported text never grants authority. |
| N02 | Reliable state | Retry-safe ingestion, jobs, approvals, notifications and provider effects have stable keys. Unknown remote outcomes reconcile before retry. Record partial success; do not promise atomic writes across providers. |
| N03 | Time correctness | IANA timezone, all-day bounds, DST, travel timezone changes, quiet hours and catch-up are defined/tested. Time passing invalidates time-sensitive cached results. |
| N04 | Accessibility and layout | Keyboard alternatives, visible focus, labels, reduced motion and text zoom work. Narrow screens use day/agenda plus drawers. Status is not conveyed by color alone. |
| N05 | Honest degradation | Manual planning works without AI; cached content has as-of/coverage labels. Low budgets fall back to fresh deterministic facts; new unsupported claims are not generated from stale summaries. |
| N06 | Privacy lifecycle | Each source defines retention, encryption, model-sharing boundary, export, disconnect and deletion for raw data, derived summaries and audit records before release. |
| N07 | Performance and evaluation | Agree representative data/device budgets before UI acceptance. Evaluate extraction, duplicate detection, commitment resolution and briefing grounding with labeled scenarios. |
| N08 | Budget enforcement | Configure conservative caps before a pilot; tune after measured use. Atomic reservations prevent concurrent overspend. Global kill switch blocks AI, not local unblock or manual access. |

## Later platform scope

| ID | Scope | Gate |
| --- | --- | --- |
| L01 | Desktop timer companions for macOS, Windows and Linux | After web release; platform-specific signed packaging, permissions, recovery, updates and acceptance. No app-blocking implication. |
| L02 | System-wide website blocking on one selected desktop OS | Later opt-in hosts helper or reviewed equivalent; reversible, privilege-bounded, locally expiring; disclose coverage limitations. No native-app/cross-device blocking. |
| L03 | Additional providers, native capture and AI handoff | Separate validated connector/capture contracts and user authority; not required for first web release. |

## Approval interpretation

A report/brief, deterministic finding or in-app preview is not an external mutation. Candidate extraction can persist suggestions in the ledger without accepting them as obligations. A generated reply can be displayed automatically as preview; approving creation of an external mailbox draft does not approve sending it. Direct explicit task creation needs no redundant generic approval. Every assistant schedule adjustment still needs review, with a single batch approval permitted only when all effects and destinations are listed.
