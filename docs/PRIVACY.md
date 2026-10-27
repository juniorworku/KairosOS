# Privacy and data handling

M0 is a local foundation and design preview. It does not connect to Google, send goal text to AI providers, send authentication emails, track browsing, or log focus sessions. No analytics integration is configured.

Keep `.env` private. The example contains development values only. Uploaded reference screenshots and the implementation plan are source materials, not application user records.

Before M1 ships, document actual account/session storage, retention, export, deletion, and administrator access. Before calendar integration, document the exact verified scopes and token encryption/key rotation. Standard calendar synchronization stores availability intervals, never event titles, attendees, or locations.

Before AI integration, disclose exactly which goal text and aggregate statistics leave the app and offer AI-off mode. AI must never write calendar events without user approval. Before extension distribution, add a privacy policy URL, a single-purpose description, permission justifications, pairing/token lifecycle, and a manual blocking QA checklist.

Personal Mode requires separate consent and controls. Raw window titles stay on the local companion; title-less classified data is the only permitted server upload. These features are not implemented in M0.

This document describes engineering intent and current behavior; it is not a public-launch privacy policy.
