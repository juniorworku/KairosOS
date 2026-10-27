# Manual planning API

`POST /api/v1/blocks` creates a goal-linked local time block. It requires an authenticated session and the usual `X-CSRF-Token` header. It never writes to Google Calendar.

| Request field | Meaning |
| --- | --- |
| `goal_id` | An active goal owned by the signed-in user |
| `action_id` | An action currently belonging to that goal |
| `start_at`, `end_at` | Future ISO-8601 timestamps with explicit timezone offsets |
| `status` | `accepted` (default) or `proposed` |

The server derives the action title, whole-minute duration, user's local Monday `week_start`, and an explanatory reason. It validates goal dates, action duration bounds, working days/hours, busy buffers, existing accepted/calendar reservations, and daily focus capacity. Invalid placements return a structured conflict; no partial record is saved. The response is a typed `BlockResponse` with HTTP 201. See `/docs` for its generated schema.

A proposed manual block can be reviewed and accepted through `POST /api/v1/plan/accept`. Reaccepting an already accepted or published block is a no-op. Publishing to Google remains a separate explicit action.

`PATCH /api/v1/blocks/{id}` moves/resizes local blocks with the same placement checks. An active linked focus session prevents changing times or deleting its block/goal. Published blocks must be changed in Google and synced before removing their local records.

Current limits: the web UI does not yet expose direct manual block creation. Blocks require goals/actions; independent tasks, support areas, recurrence and event notes are not supported by this endpoint. Draft generation replaces only existing proposed blocks and returns a placement preview; it does not produce an added/moved/removed diff for accepted plans.
