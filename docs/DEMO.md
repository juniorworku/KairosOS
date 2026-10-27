# Local core demo

1. Copy `.env.example` to `.env` and run `make dev`. The API applies pending migrations before serving and seeds the configured owner idempotently.
2. Confirm `http://localhost:8000/healthz` and `/readyz` succeed. Open `http://localhost:5173` using `localhost`, not a different host name.
3. Request a sign-in link for `OWNER_EMAIL` (default `owner@localhost.test`). Open the newest message in `http://localhost:8025`. The first link visit only shows confirmation; choose the sign-in button to consume it.
4. Set your timezone, working days/hours and daily focus limit. Create a goal with an outcome measure, target date, one to five actions, and an if-then obstacle response. Add a manual busy interval to exercise availability without Google.
5. Draft a week. Check proposal reasons and any capacity warning. Discard or move a proposal, then accept the blocks you want. These are local plan changes; no Google write happens implicitly.
6. Start a focus session from a block or the focus page. Check reload recovery. Finish and add a focus rating. Record a separate outcome check-in; effort should not fabricate metric progress.
7. Save a weekly reflection and inspect the goal's computed trajectory. New goals with little evidence should show insufficient data rather than invented progress.
8. In Settings, inspect sessions, export account data, and review the AI/calendar configuration status. The coach should explain when it is not connected; manual planning should still work. The owner can inspect users/plans/invites/audit.
9. Optionally configure a real Google client, encryption key and AI provider. Run consent/publication/provider checks only with appropriate credentials. Keep every external calendar write behind approval. These checks are not implied by the local fake-provider test suite.
10. To try focus blocking, build/load the unpacked [extension](../extension/README.md), pair it from Settings, configure the bridge ID, and follow [manual QA](../extension/QA.md). No browser extension is installed automatically.
11. Run `make lint typecheck test build`, `make integration`, and browser tests as described in README. `make generate-api` should leave no generated contract drift. Record actual results in the verification report.
12. Run `make down` when finished. Nothing is deployed. Account deletion is destructive and should be tried only after export if the data matters.

PWA installation/offline behavior must be exercised from the production build as well as normal development. No Lighthouse score or Chrome lifecycle guarantee is claimed without its corresponding measurement/manual run.
