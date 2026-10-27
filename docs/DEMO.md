# M0 local demo

1. Copy `.env.example` to `.env` and run `make dev`.
2. Open http://localhost:8000/healthz and confirm a successful liveness response.
3. Open http://localhost:8000/readyz and confirm database/Redis readiness.
4. Run `make migrate` and confirm the baseline revision applies.
5. Open http://localhost:5173 and inspect the Kairos shell on desktop and mobile widths. Preview content must remain distinguishable from saved user data.
6. Open http://localhost:8000/docs and inspect the foundation API contract.
7. Run the checks listed in README and record actual results in the delivery report. A CI workflow file alone does not establish that remote CI passed.
8. Run `make down` after the demo. Nothing is deployed.

Authentication, goal creation, scheduling, focus logging, coaching, calendar connections, PWA installation, and extension blocking are future demos, not M0 acceptance claims.
