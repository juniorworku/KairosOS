import { addDays, dateKey, weekStart } from "../lib/time";
import type { Block, FocusSession, Goal } from "../api/types";
export function planHref(
  date: string,
  goalId?: string | null,
  blockId?: string | null,
) {
  const params = new URLSearchParams({ date });
  if (goalId) params.set("goal", goalId);
  if (blockId) params.set("block", blockId);
  return "/plan?" + params.toString();
}
export function reviewHref(session: FocusSession, timezone: string) {
  const params = new URLSearchParams({
    week: weekStart(dateKey(new Date(session.started_at), timezone)),
  });
  if (session.goal_id) params.set("goal", session.goal_id);
  return "/review?" + params.toString();
}
export function requestedWeek(value: string | null, today: string) {
  if (value && /^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const candidate = new Date(value + "T12:00:00Z");
    if (
      Number.isFinite(candidate.getTime()) &&
      candidate.toISOString().slice(0, 10) === value
    )
      return weekStart(value);
  }
  return weekStart(today);
}
export function sessionGoal(
  session: FocusSession | null | undefined,
  goals: Goal[],
): Goal | undefined {
  return session
    ? goals.find(
        (goal) =>
          goal.id === session.goal_id ||
          goal.actions.some((action) => action.id === session.action_id),
      )
    : undefined;
}
export function plannedWeekMinutes(blocks: Block[]) {
  return blocks
    .filter((block) =>
      ["accepted", "published", "completed", "skipped"].includes(block.status),
    )
    .reduce((total, block) => total + block.planned_minutes, 0);
}
export function recommendationHref(
  type: "planning" | "focus" | "goal" | "reflection",
  week: string,
  goal?: Goal,
) {
  if (type === "planning") return planHref(week, goal?.id);
  if (type === "goal") return goal ? "/goals/" + goal.id : "/goals";
  if (type === "focus")
    return goal ? "/focus?goal=" + encodeURIComponent(goal.id) : "/focus";
  const params = new URLSearchParams({ week });
  if (goal) params.set("goal", goal.id);
  return "/review?" + params.toString();
}
export function nextWeekHref(week: string, goalId?: string) {
  return planHref(addDays(week, 7), goalId);
}
