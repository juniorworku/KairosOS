# Privacy and data handling

This document describes the local implementation. It is engineering documentation, not a final public-launch privacy policy. No analytics or deployment is configured.

## Saved data

The server saves account email/profile/work preferences, hashed sign-in credentials, session device metadata and hashed source addresses, goals/actions/obstacles, busy intervals, time blocks, focus logs/self-ratings, metric check-ins, and reflections. Owner/admin roles can manage accounts, plans, invites, session access, and inspect administration audit records. No administrator feature is intended to expose another user's planning content.

Development sign-in messages go to the local Mailpit inbox. Configuring a real email provider sends sign-in email to that provider. Tokens expire after 15 minutes by default and can be used once; opening a link alone does not consume it. Application/task logs omit emails, tokens, sign-in URLs, and provider error bodies. Server access logging must remain disabled or sanitize query strings.

Sessions expire after 30 inactive days, with a 90-day absolute limit. The scheduled auth cleanup removes expired/revoked credentials. A hash-only owner seed marker is retained after deletion to prevent the configured owner being recreated automatically. This marker is pseudonymous, not a claim of irreversible anonymization.

## Calendar and coaching

Google sign-in and calendar access are separate consents. Calendar refresh credentials are encrypted with the configured server key. Standard calendar reads save availability intervals, not event titles, attendees, locations, or descriptions. Accepted time blocks can be published to the dedicated Kairos calendar only after explicit approval. Disconnect revokes credentials, clears local availability, and detaches local event references. Existing Google events remain in the user’s calendar, unmanaged by Kairos. Account deletion also attempts provider revocation before removing records.

Coaching is optional. When enabled/configured, the chosen Anthropic or Gemini service receives the text submitted to the coach and, if requested, redacted goal titles/outcomes plus computed trajectory fields. Free-form goal text can still be personal after identifier redaction. Provider credentials, account email, and raw calendar event details are not sent as coaching context. AI audit rows store task/provider/model, token counts, timing and status, rather than raw prompts or chat transcripts. If a request stops before usage is confirmed, its maximum output allowance remains reserved; this can exceed actual billed usage. Turning AI off leaves manual planning and focus features available.

## Browser and extension

The browser may cache private planning reads and queue supported offline check-ins/session endings in IndexedDB. Reads and queued writes are scoped to the signed-in account. Switching accounts hides the previous account’s data; signing out clears all local private reads and queued writes. Failed queued writes are retained for an explicit retry or discard. Anyone with access to an unlocked browser profile may be able to view locally cached data; no claim of encrypted browser storage is made.

The Chrome extension reads no page content or browsing history. It stores its paired bearer token, active session timing and the selected domain list locally, and uses navigation rules only while focusing. Optional redirects require separately granted host access. Optional reminder-page mode counts its own blocked page loads. Basic native blocking does not collect navigation counts. Session-bound pending pause/end events are stored locally during outages and replayed after reconnect. Pairing and bearer access are revocable; disabling an account also invalidates extension access.

## Export, deletion and limits

Account export returns profile and user-owned planning/integration metadata, excluding private auth/OAuth/pairing/bearer records and credential columns. Account deletion removes user-owned records through cascading foreign keys and clears browser/session access. Provider revocation errors are surfaced so deletion can be retried. Local Docker database volumes and Mailpit messages are operator-managed; backups or exported files require separate removal.

Reference screenshots and the implementation plan are repository source material, not user account records. Keep `.env`, credential encryption keys, exports, and backups private. Losing the encryption key prevents recovery of saved calendar credentials.

Personal Mode is deferred. No native activity logger, window-title upload, privileged helper, OS-wide blocker, Slack/Teams integration, smart-home control, or intervention overlay is implemented.

A public launch still requires a final policy matching the deployed configuration, provider/domain verification, retention/backup decisions, and the Chrome Web Store permission/privacy disclosures. Nothing is published by this repository's CI.
