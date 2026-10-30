# Kairos interactive design prototype

A standalone, local UI/UX prototype based on the v2.0 product blueprint. This is separate from the production app. It uses fictional sample data and a fixed demo week (November 2-8, 2026).

## Open for review

Open `output/prototype/Kairos-Interactive-Prototype.html` in a browser. CSS and JavaScript are embedded; no server, package installation, network request or account connection is needed. The ZIP edition contains the same HTML and this guide.

## Suggested review path

1. Today: expand a goal and inspect the calendar. Open the coach or collapse it. Switch Day/Week. On narrow screens the entry uses Day view.
2. Review changes: inspect both proposed adjustments, approve either/both, or dismiss. These affect only the sample calendar. Fixed blocks can be inspected and unlocked explicitly.
3. Calendar: click an event, edit its time using the form, or drag an event/task into a free slot. Drops open a concrete approval. Double-click empty time or press Enter on a day column to propose a block. Conflicting sample reservations are rejected.
4. Commitments: filter promises/replies/waiting/candidates, inspect evidence, edit a draft, review the simulated send, accept a candidate, or resolve with a completion note. Sending does not close an obligation.
5. Meeting prep: open Acme's dossier, add supplied notes, review extracted candidates and accept/link evidence.
6. Goals: create a goal through the three-step clarification/plan review. Save a draft locally or approve a prepared plan/check-in. No calendar publication is included.
7. Assistant: configure one of six workflow templates, inspect cadence, source, authority and stop-condition preview, then confirm. Unsupported example requests are rejected rather than expanding authority. Specialized profile grouping remains undecided in the blueprint.
8. Focus: start from a task/block, pause/resume, navigate to Today to use the floating timer, drag/minimize it or move its handle with arrow keys. Finish and record an outcome without assuming task completion.
9. Review: inspect example outcome/time-use evidence and save a daily reflection. The sample chart is illustrative, not inferred activity.
10. Click the profile initials or lower-left prototype guide to reset sample data.

## What is real in this prototype

Navigation, modal dialogs, filters, local sample edits, task/commitment actions, proposal approval/dismissal, drag/drop previews, goal setup, template-preview steps, local reflection persistence, a working pauseable timer, floating timer controls and an optional browser-synthesized ambient chord.

## What is simulated

AI replies/plan generation/extraction, provider sync, server jobs, push/email delivery, source accounts, focus protection, metrics and progress. No emails are sent. No calendar writes occur. No blocking rules are installed or applied. No native-app or cross-device blocking is promised. The audio is a synthesized ambient tone rather than a licensed lo-fi music library.

Changes persist only in this browser's local storage. The active timer can restore after reload; this does not implement the production session recovery policy. Reset clears the prototype's saved data only. Browser storage behavior for local HTML may vary.

## Design system

White/light gray surfaces, charcoal text, one deep-purple accent, subtle borders, compact event details and a calendar-first workspace. Today and Plan share the shell. Commitments, Goals, Review and Assistant are supporting views. Medium/narrow screens use a coach drawer; phone entry uses Day view.

## Validation

`node prototypes/kairos/check.cjs` runs meaningful DOM interaction scenarios using the repository's existing jsdom dependency. JavaScript syntax and CSS parsing are checked separately. Local interaction checks passed for the review path above. Automated browser visual/drag-geometry checks were not completed: the browser tool rejected the local file URL. Actual desktop/mobile visual review is therefore still required; this is not a pixel-perfect or accessibility certification.

## Source and rebuild

Sources: `prototypes/kairos/index.html`, `styles.css` and `app.js`. To rebuild the standalone HTML, inline the stylesheet and script into the HTML template. The existing application source is untouched.
