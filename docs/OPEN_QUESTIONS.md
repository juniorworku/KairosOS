# Open questions

These decisions do not block M0. Defaults below keep the foundation narrow.

1. The user requested an MVP, while Section 19 specifies stopping after M0. This delivery establishes M0 first; subsequent milestones will build the usable product loop.
2. Choose owner email, Google OAuth credentials, and email provider for M1. Default signup remains closed; no fake sign-in is presented as real authentication.
3. Choose domain, Render region, and instance sizes only when deployment is authorized. No hosting resources are created now.
4. AI provider/model and plan quotas remain configurable; no sample model identifier is treated as a verified available model.
5. Calendar creation appears in the connect flow and again at M5. Prefer read-only availability consent in M3, then incremental app-calendar permission in M5.
6. Define action active/archived status, blackout storage, and metric direction before their domain migrations. These are referenced in behavior but missing from the initial core schema.
7. Define calibrated versus original planned duration before feeding session history back into quotas; avoid compounding the buffer.
8. Focus sessions update effort evidence, not goal metric values. Trajectory must not invent outcome progress from time spent.
9. Define zero-range metric and zero-length goal handling before trajectory implementation.
10. Specify extension-only end-session and pause endpoints before M9; extension tokens cannot use unrestricted web endpoints.
11. Dev email delivery may expose a magic link in an isolated local inbox; never put links in application logs outside explicit local delivery.
12. Primary desktop OS, Home Assistant, Slack/Teams, and intervention preferences are deferred until Personal Mode.
