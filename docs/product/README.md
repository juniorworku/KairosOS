# Kairos product documentation suite

Version 2.0 / 30 October 2026 / Product specification; implementation and deployment are separate work.

Kairos is a full AI executive assistant with a calendar-first workspace. It turns goals and commitments into an approved plan, runs follow-up routines on the server, and keeps evidence and decisions connected until work is done, cancelled, or deliberately deferred.

## Read the suite

1. [Product description and release scope](VISION.md)
2. [Requirements and acceptance criteria](REQUIREMENTS.md)
3. [User workflows and state rules](WORKFLOWS.md)
4. [Interface architecture](DESIGN.md)
5. [Screen specifications and components](SCREEN_SPECIFICATIONS.md)
6. [Five engines, workflows, and integrations](FEATURES.md)
7. [Templates, approvals, background runs, and notifications](AUTOMATION.md)
8. [Shared context, AI use, and budgets](CONTEXT.md)
9. [Implementation sequence and release gates](IMPLEMENTATION.md)
10. [Decisions, unresolved details, and references](DECISIONS.md)

## Agreed direction

- First public product release includes commitment, calendar, briefing, goal, and insight capabilities. Calendar/goals/tasks, meetings, then email is the internal build order, not permission to release a planner-only MVP.
- Google Calendar reading, sync, and approved publication are foundational. Additional calendar providers come later.
- Six fixed template families are configured through one short chat and a typed preview. Chat cannot create arbitrary automation or expand authority.
- Every assistant-created task, message draft, or calendar mutation is a reviewable proposal. Reports and authorized notifications can run automatically; sending and schedule changes require explicit approval.
- Web app first: Chrome website blocking and an in-app timer. Desktop companions for macOS, Windows, and Linux follow. System-wide website blocking starts later on one chosen desktop OS. Native app blocking and cross-device blocking are excluded.
- Today and Plan share the calendar-first workspace. Commitments, Goals, Review, and Assistant are supporting views; no separate metric-heavy home dashboard.
- Clean Tech: white/light gray, charcoal text, and one deep-purple accent. No conflicting pastel category palette.

## Authority and status

This suite is the current product specification and supersedes older product/layout assumptions. Statements about existing implementation are limited to documented repository evidence, not new certification. [Existing architecture](../ARCHITECTURE.md), [roadmap](../ROADMAP.md), [agenda behavior](../AGENDA.md), and [verification](../VERIFICATION.md) remain historical/current implementation references. The [original guide](../../IMPLEMENTATION.md) is not the new release definition. Existing native app-suspension code is outside the new launch scope; this documentation pass does not remove or modify it.

Proposed catalog mapping and unresolved platform/operational choices are recorded in [Decisions](DECISIONS.md). Nothing here authorizes provider connections or deployment.

## PDF edition and source of truth

[Download the updated product blueprint](../../output/pdf/Kairos-Product-Blueprint.pdf). The PDF is generated from these Markdown chapters without separate product wording or palette substitutions. Diagrams illustrate the same contracts. Future edits update the source suite first and regenerate the PDF.


## Regenerate the PDF

Run `python3 docs/product/tools/build_pdf.py` from the repository root to generate the print HTML in `tmp/pdfs/`. Print that local HTML to `output/pdf/Kairos-Product-Blueprint.pdf` with a paged-media-capable browser, retaining CSS page numbering and suppressing browser URL/date headers. Render every page for visual verification after edits. The renderer contains layout illustrations but no alternate chapter text or source wording substitutions.

## Interactive design review

The [standalone clickable prototype](../../output/prototype/Kairos-Interactive-Prototype.html) demonstrates the calendar-first workspace, commitments, goal setup, coaching/proposals, workflow configuration and focus timer with fictional sample data. See the [review guide](../../prototypes/kairos/README.md) for scenarios, scope and verification limits. This artifact is separate from app implementation and has no live integrations.
