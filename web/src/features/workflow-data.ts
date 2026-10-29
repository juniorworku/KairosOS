import type { Block, Goal, Season, Trajectory } from "../api/types";
import { dateKey } from "../lib/time";

export function calendarDays(start: string, end: string): number {
  return Math.round(
    (Date.parse(`${end}T00:00:00Z`) - Date.parse(`${start}T00:00:00Z`)) /
      86400000,
  );
}

export function selectedSeason(
  seasons: Season[],
  today: string,
): Season | undefined {
  const current = seasons
    .filter(
      (season) =>
        season.status !== "done" &&
        season.start_date <= today &&
        season.end_date >= today,
    )
    .sort((a, b) => a.end_date.localeCompare(b.end_date));
  const future = seasons
    .filter((season) => season.status !== "done" && season.start_date > today)
    .sort((a, b) => a.start_date.localeCompare(b.start_date));
  return (
    current[0] ||
    future[0] ||
    [...seasons].sort((a, b) => b.end_date.localeCompare(a.end_date))[0]
  );
}

export function acceptedActions(blocks: Block[]): Block[] {
  return blocks
    .filter((block) => ["accepted", "published"].includes(block.status))
    .sort(
      (a, b) =>
        Date.parse(a.start_at) - Date.parse(b.start_at) ||
        a.id.localeCompare(b.id),
    );
}

export function nextAccepted(
  blocks: Block[],
  now: number,
  today: string,
  timezone: string,
): Block | undefined {
  const accepted = acceptedActions(blocks);
  return (
    accepted.find((block) => Date.parse(block.end_at) > now) ||
    accepted.find(
      (block) => dateKey(new Date(block.start_at), timezone) === today,
    )
  );
}

export function outcomeEvidence(goal: Goal, trajectory?: Trajectory) {
  const checkin = [...(goal.checkins || [])]
    .sort((a, b) => Date.parse(a.recorded_at) - Date.parse(b.recorded_at))
    .at(-1);
  const current = checkin?.metric_value ?? goal.metric_start;
  const range = goal.metric_target - goal.metric_start;
  const fraction =
    trajectory?.actual_fraction ??
    (range && Number.isFinite(range)
      ? (current - goal.metric_start) / range
      : 0);
  return {
    current,
    checkin,
    fraction: Number.isFinite(fraction)
      ? Math.max(0, Math.min(1, fraction))
      : 0,
  };
}

export function planDay(
  day: string,
  goal?: string | null,
  block?: string | null,
): string {
  const query = new URLSearchParams({ date: day });
  if (goal) query.set("goal", goal);
  if (block) query.set("block", block);
  return `/plan?${query}`;
}

export function shortDate(day: string): string {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${day}T12:00:00Z`));
}
