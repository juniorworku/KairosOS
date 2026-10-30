# User workflows and state rules

## 1. Connect and clarify

1. Choose plan a goal or organize existing work; select a day/1/2/4/6/12-week horizon.
2. Connect Google Calendar, then Gmail when ready, with separate source/AI/write consent. Enter availability manually if not connected.
3. Define success, path, capacity, constraints, follow-up and authority. Follow-up questions adapt to missing information; save/resume is available.
4. Show bounded import scope, progress, partial coverage and source freshness. Do not imply older history was checked.
5. Propose milestones, tasks, blocks and workflows; expose assumptions/capacity gaps. Review exact effects and destinations, accept/edit/reject.
6. Open the calendar-first workspace. Unapproved items remain suggestions; publication is approved explicitly, possibly within the same enumerated review.

## 2. Activate a fixed workflow

Choose one of six template families, answer a short chat, inspect the typed form preview and confirm. Chat selects only registered check/output profiles and allowed parameter values; it cannot invent new checks, code, tools or permissions. Style instructions go only to writing. Unsupported requests offer the nearest template and record a redacted catalog miss. Preview shows next run, source coverage, authority ceiling and stop condition. Changes to behavior are reviewed as a new version.

## 3. Morning brief and daily coach sync

The server creates a Daily brief before the app is opened. Today shows it in the coach panel beside the calendar. The interactive daily coach sync uses that report; it is not a separate automation template. Coach asks about changed capacity, energy and core priorities. Preserve the accepted weekly plan and fixed blocks. Propose only justified additions/differences, with reasons. Review and approve individual changes or an exact batch, then start focus. Skip sync without losing the existing plan.

## 4. Capture and resolve commitments

Email, meeting notes or manual input supplies evidence. Extract candidate commitments and match people/threads with provenance. User accepts, edits, dismisses or merges candidates before inferred work enters the accepted ledger. A commitment records what is owed; tasks describe actions that fulfill it. One task can contribute to an obligation without proving that obligation resolved.

Resolution rules:

- Task: explicit user completion or a separately approved, verifiable completion action.
- Waiting on them: a response creates evidence; mark resolved only when deterministic evidence is conclusive under the configured rule, otherwise request confirmation. Acknowledgments and partial answers do not close it.
- Promise/meeting action: completion evidence must satisfy the promised deliverable, with owner confirmation when uncertain.
- Goal: record the success measure; effort and task count are not substitutes.
- Deferred work: capture reason, resume date or review trigger; pause follow-ups until that trigger. Reopen when evidence invalidates an earlier resolution and show why.

## 5. Guardian and approval review

A source event or time-based check identifies conflict, freed capacity, missing link, travel need or threatened focus. Focus rescue merges preventive Focus guard and reactive Focus defense. Calendar sentinel remains a set of guardian checks, not a duplicate routine.

Produce a bundled proposal with before/after, dependency ordering, source versions and exact destinations. Fixed blocks remain protected; surface a decision rather than moving them. Preserve the currently observed external calendar: approval governs Kairos's corrective action, not whether a third-party edit already happened.

Revalidate on approval. Supersede old alternatives; changed facts require renewed review. Remember dismissal signatures (reason, affected items, meaningful constraints) until those facts change. Applying one change cannot silently apply a dependent unapproved change. Report partial results and reconcile unknown external writes before retrying.

## 6. Focus

Start a task/block, confirm objective/duration and configured Chrome website rules. Optional audio starts through user playback controls. Dedicated view and floating in-app timer show active time, pause/resume/end and actual browser protection status. Pause releases session blocking by default; resuming restores permitted rules. Emergency unblock and local expiry remain available without network.

On finish, record accomplishment, explicit task status, remaining work and optional outcome/self-rating. Timer expiry never completes a task. Sleep, restart and abandoned sessions need a declared recovery policy before implementation; do not claim idle/sleep time as focused work. A continuation block is a new proposal. Later desktop timer companions do not imply native-app or cross-device blocking.

## 7. Daily check-out and weekly review

Daily check-out reconciles completed, unfinished, waiting and blocked items; `/done` opens this session. Updates explicitly entered by the user apply as entered; inferred new tasks, mailbox drafts and calendar changes remain proposals. Missing the check-out does not mark all unfinished work failed or rolled forward.

Weekly review has Friday-wrap and week-ahead modes over one evidence snapshot/review record. Friday summarizes outcomes and open decisions; week-ahead proposes next week. Deduplicate overlapping reports; preserve differences when constraints change. Compare scheduled time, recorded active time and coverage, not invented actual activity. User decides carry-forward, defer, drop or revise.

## 8. Closed-app operation and catch-up

Ingestion, checks, briefing and approved notifications run server-side while the browser is closed. The device independently ends website rules. Feed stores report and decision history; push/email provide permitted delivery, not guaranteed proof the user read it. On reconnect, show latest useful outputs and partial-source warnings rather than replaying every old notification. Detailed catch-up and delivery rules are in [Automation](AUTOMATION.md).

## State contracts

Plan: draft → proposed → active → completed/archived; prior accepted revision remains authoritative until changed.

Commitment: candidate → accepted → active/waiting/deferred → fulfilled/cancelled. Candidate can be dismissed; deferred needs a resume trigger. Tasks have independent todo/in-progress/done/cancelled state and scheduling links. Goal outcome state is separate.

Proposal: pending → applying → applied/partially-applied/failed; pending can be dismissed/superseded/expired/conflicted. Retries retain operation identity. Changed effects create a new review version.

Loop: draft → active ↔ paused → stopped. Run: queued/running → success/partial/failed/skipped/cancelled. Check pause/version before delivery; cancelled work cannot emit newly generated actions.

Focus: idle → running ↔ paused → ended; local end/escape is authoritative for device rule release. Reconciled timestamps must not duplicate duration or extend expired protection.
