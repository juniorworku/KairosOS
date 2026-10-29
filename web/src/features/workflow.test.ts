import { describe, expect, it } from "vitest";
import {
  planHref,
  requestedWeek,
  recommendationHref,
  plannedWeekMinutes,
} from "./workflow";
import type { Block } from "../api/types";
describe("workflow context", () => {
  it("keeps the exact calendar goal and block context", () => {
    expect(planHref("2026-10-28", "goal", "block")).toBe(
      "/plan?date=2026-10-28&goal=goal&block=block",
    );
  });
  it("validates review dates and normalizes Mondays", () => {
    expect(requestedWeek("2026-10-28", "2026-11-05")).toBe("2026-10-26");
    expect(requestedWeek("2026-02-31", "2026-11-05")).toBe("2026-11-02");
  });
  it("recommendations link to preview rather than mutate data", () => {
    expect(recommendationHref("planning", "2026-10-26")).toBe(
      "/plan?date=2026-10-26",
    );
    expect(recommendationHref("goal", "2026-10-26")).toBe("/goals");
  });
  it("counts saved plan commitments without cancelled or proposed time", () => {
    const blocks = [
      "accepted",
      "published",
      "completed",
      "skipped",
      "cancelled",
      "proposed",
    ].map((status) => ({ status, planned_minutes: 30 })) as Block[];
    expect(plannedWeekMinutes(blocks)).toBe(120);
  });
});
