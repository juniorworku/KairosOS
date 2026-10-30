# Shared context, AI use and budgets

## One ingestion layer

Source adapters sync Calendar changes, Gmail history and supplied meeting notes into an owner-scoped store of people, threads, meetings, commitments, goals, summaries and evidence references. Routines query this store, not providers directly. Calendar cursors and Gmail history IDs are opaque provider state with explicit recovery on expiry. A connector may require fetching changed records; incremental does not mean zero network traffic.

First connections use declared bounded backfill (proposed mail starting point: ten days, configurable before consent). Show coverage dates and unknown older promises; do not present bounded history as a complete account. Resync after cursor expiry has its own bounded recovery policy and must preserve accepted local commitments and provenance.

## Incremental summaries and freshness

Hash content with owner/source identity and normalization; re-extract only changed material. Version rolling thread/person/goal summaries with source IDs, source versions, model/prompt version and as-of time. Source edits, deletion, permission changes and retention invalidate relevant summaries/context packs. A language-model summary is derived evidence, not ground truth; retrieve specific source evidence for uncertain or consequential claims.

Time passing is an input. Due dates, waiting ages, current local day, meeting lead time, resolved status and capacity are re-evaluated deterministically even when source content hashes are unchanged. Never reuse yesterday's brief as today's factual analysis. If nothing relevant changed, create a short fresh digest with refreshed time-sensitive fields; reuse only still-valid prose fragments, clearly dated.

## Deterministic first, language second

| Work | Implementation | Guardrail |
| --- | --- | --- |
| Overdue, days waiting, double bookings, ranking, capacity, velocity math | Plain code over typed facts and declared preferences | No LLM-computed authority or ungrounded social importance |
| Commitment extraction and text classification | Configured economical model tier | Schema validation, evidence spans, uncertainty, candidate-only output |
| Drafts, briefing prose and coaching | Configured stronger model tier on allowed template paths | Grounded context pack; cannot invent facts or choose tools outside schema |

No model brand, model identifier or guaranteed price is assumed. Model selection and quality evaluation are deployment configuration. Classification/extraction may be probabilistic even though subsequent checks are deterministic; evaluate errors and keep corrections/audit history.

## Context packs and bounded orchestration

Each template profile defines a context recipe, permitted fields, evidence IDs, freshness/coverage requirements, model tier, maximum tokens and maximum steps/tool calls. The orchestrator builds one compact structured pack per logical step/snapshot; sub-steps share its facts and pass typed results, not repeated transcript dumps. Do not reuse packs across users or beyond consent boundaries. Multi-agent orchestration is optional implementation machinery, not a requirement to run several agents for every routine.

Separate trusted template instructions from untrusted source text and free-text preferences. Output style preferences cannot change criteria or authority. Stable profile/preferences prefixes may use provider caching where supported; measure actual cache use rather than assuming savings. Raw credentials, unnecessary source content and secret-bearing fields are excluded.

## Budgets and run ledger

Per-user monthly allocation splits scheduled loops, extraction, drafting and chat, with a reserved daily-brief share inaccessible to chat. Add per-loop/run token/step/tool caps, concurrency limits, and a global daily AI kill switch. Conservative numeric limits must be configured before the first pilot; tune after one week of measured use rather than leaving execution uncapped while collecting data.

Reserve maximum allowed usage transactionally before work; reconcile actual known usage after completion. Unknown/cancelled provider usage retains a bounded reservation until reconciliation/expiry policy resolves it. Track model ID, tier, prompt version, input/output/cached tokens, measured/estimated/unknown usage, currency/pricing version, cost estimate, purpose, loop/run IDs and time. Distinguish application allowance from provider invoice cost. Price snapshots and unavailable pricing are explicit.

Usage meter shows purpose breakdown and one proposed 80% threshold alert per budget period (exact threshold configurable). Reserved briefing capacity is finite: if exhausted, deliver a current deterministic digest rather than claiming AI briefing remains guaranteed.

## Degradation ladder

1. Full permitted output within reservation.
2. Use still-valid cached summaries; no new AI analysis; refresh deterministic facts and show coverage/as-of limitations.
3. Fresh deterministic digest, without generated prose, retaining pending decisions and source status.
4. Pause lower-priority AI steps/loops and disclose what is paused. Continue essential deterministic checks where possible.

No budget mode bypasses approvals, stale-source protections or device-local release. New items that lack extraction remain visibly unprocessed; existing accepted commitments are still tracked. Failures never get silently summarized as no urgent work.

## Privacy lifecycle

Before first release define source-specific retention, user deletion/export, disconnect behavior, encryption, model-sharing consent and audit minimization. Removal/permission revocation propagates to raw content, summaries, pack caches and embeddings if used. Retain only minimal non-content audit data permitted by the agreed retention policy. Existing coach restrictions on raw calendar content are not silently lifted: new context access requires explicitly designed and consented sharing.


## Verified technical references

- [Google Calendar incremental synchronization](https://developers.google.com/workspace/calendar/api/guides/sync): complete pagination before committing the next sync token; invalidated tokens require provider-cache rebuild.
- [Gmail synchronization](https://developers.google.com/workspace/gmail/api/guides/sync): expired/out-of-range history requires resync; preserve bounded coverage and accepted local work.
- [Gmail push](https://developers.google.com/workspace/gmail/api/guides/push): Pub/Sub notifications and watch renewal are connector responsibilities, not execution of user loops.
