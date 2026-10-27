# Configuration and open questions

The local core can be used before these production/integration decisions are made. No credentials or service purchases are invented.

1. **Owner account.** Local Compose seeds `OWNER_EMAIL`, default `owner@localhost.test`, with closed signup. Use Mailpit to sign in. Choose the actual owner email before configuring real mail. A deleted owner is not automatically recreated; the hash-only seed marker deliberately preserves that choice.
2. **Google credentials.** Supply an OAuth client/secret and the exact identity/calendar callback URIs. Identity consent is separate from calendar consent. Availability and app-calendar write scopes require live verification and the applicable Google verification process before public launch.
3. **Email delivery.** Local SMTP targets Mailpit. For real mail choose configured Resend or authenticated STARTTLS SMTP, a sending domain, and delivery/authentication checks. No console transport logs sign-in links.
4. **Calendar encryption.** Generate and privately retain a valid Fernet key in `TOKEN_ENCRYPTION_KEY` before connecting a calendar. A future key rotation procedure must decrypt with the old key, re-encrypt with the replacement, and keep a secure recovery copy until verification succeeds. Do not rotate by discarding the old key.
5. **AI provider/model.** Set the chosen Anthropic or Gemini key and an available model name. No default model identifier is assumed to exist. Plan names/numeric limits are placeholders in the auth seeding configuration; existing plans are not overwritten on restart. AI-off mode remains available.
6. **Planning schema.** The initial local implementation uses typed planning aggregates in a user-owned JSON table rather than every separate table in the guide. Decide when normalized actions/blocks/check-ins and richer database-level relations are needed before scaling.
7. **Quota architecture.** Current AI reservations are serialized in PostgreSQL with audit rows. The guide's Redis hot counters and nightly reconciliation are not implemented; adopt them only with appropriate concurrency/reconciliation tests when volume warrants it.
8. **Extension release.** Configure the unpacked extension ID for immediate web sync. Run the manual Chrome QA matrix. Exact hosted origins, privacy disclosures, permission justifications and a Web Store owner are required before distribution.
9. **Public hosting.** Domain, region, instance sizes, DNS/email authentication, backup/restore and monitoring decisions remain deferred. No deployment is authorized.
10. **Personal Mode.** Primary OS, native capture, Slack/Teams, smart-home integrations, activity retention, and intervention preferences remain deferred with M10–M17. The current app does not collect native activity or change OS settings.

The user authorized continuation beyond the original M0 stop instruction. Acceptance status remains evidence-based; provider credentials, remaining manual Chrome testing, device/installation coverage, and public deployment are not silently treated as completed.

Anti-goal text is a planning note, not a natural-language scheduling rule. Working hours and explicitly entered unavailable intervals are the enforced exclusions. Recurring blackout controls can be added separately. Duration calibration currently uses recorded session history; richer task-completion estimates remain a future refinement.
