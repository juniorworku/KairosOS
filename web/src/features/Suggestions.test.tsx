import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/client";
import type { Goal } from "../api/types";
import { copy as c } from "../copy/en";
import { Suggestions } from "./Suggestions";

const availability = vi.hoisted(() => ({
  configured: true,
  enabled: true,
  online: true,
}));
vi.mock("../lib/hooks", () => ({
  useData: () => ({
    data: {
      configured: availability.configured,
      enabled: availability.enabled,
    },
  }),
  useOnline: () => availability.online,
}));
vi.mock("../api/client", () => ({ api: vi.fn() }));

const goal: Goal = {
  id: "goal",
  title: "Write a book",
  outcome_statement: "Complete the manuscript",
  metric_name: "Chapters",
  metric_unit: "chapters",
  metric_start: 0,
  metric_target: 10,
  start_date: "2026-10-28",
  target_date: "2027-01-20",
  season_id: null,
  why_facts: "Private motivation",
  why_feelings: "Private feelings",
  why_function: "Private personal context",
  anti_goals: ["Private boundary"],
  confidence_pct: 80,
  follow_through_pct: 80,
  priority: 3,
  status: "active",
  actions: [
    {
      id: "action",
      title: "Write each morning",
      kind: "habit",
      weekly_minutes_target: 120,
      total_minutes_estimate: null,
      min_block_minutes: 30,
      preferred_block_minutes: 60,
      max_block_minutes: 120,
      preferred_time_of_day: "morning",
      requires_deep_focus: true,
    },
  ],
  obstacles: [],
  checkins: [],
};

beforeEach(() => {
  vi.mocked(api).mockReset();
  availability.configured = true;
  availability.enabled = true;
  availability.online = true;
});
afterEach(cleanup);

describe("optional wizard suggestions", () => {
  it("requests only after a click and applies a goal suggestion only after explicit Use", async () => {
    const onUse = vi.fn();
    vi.mocked(api).mockResolvedValue({
      outcome_statement: "Draft twelve chapters",
      metric_name: "Drafted chapters",
      metric_unit: "chapters",
      suggested_target: 12,
      clarifying_questions: ["How much time can you protect?"],
    });
    render(<Suggestions kind="goal" goal={goal} onUse={onUse} />);
    expect(api).not.toHaveBeenCalled();
    expect(onUse).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: c.coach.suggestGoal }));
    expect(await screen.findByText("Draft twelve chapters")).toBeVisible();
    expect(onUse).not.toHaveBeenCalled();
    expect(api).toHaveBeenCalledTimes(1);
    const [path, method, rawBody] = vi.mocked(api).mock.calls[0];
    expect(path).toBe("/coach/goal-refine");
    expect(method).toBe("POST");
    const body = rawBody as { text: string; include_context: boolean };
    expect(body.include_context).toBe(false);
    const context = JSON.parse(body.text) as Record<string, unknown>;
    expect(context.title).toBe(goal.title);
    expect(context.actions).toEqual([
      { title: "Write each morning", kind: "habit", weekly_minutes: 120 },
    ]);
    expect(context).not.toHaveProperty("why_facts");
    expect(context).not.toHaveProperty("why_feelings");
    expect(context).not.toHaveProperty("checkins");
    expect(context).not.toHaveProperty("anti_goals");
    fireEvent.click(
      screen.getByRole("button", { name: c.coach.useSuggestions }),
    );
    expect(onUse).toHaveBeenCalledWith({
      outcome_statement: "Draft twelve chapters",
      metric_name: "Drafted chapters",
      metric_unit: "chapters",
      metric_target: 12,
    });
    expect(api).toHaveBeenCalledTimes(1);
    expect(
      screen.queryByRole("region", { name: c.coach.suggestions }),
    ).not.toBeInTheDocument();
  });

  it("cancels an action preview without changing wizard state", async () => {
    const onUse = vi.fn();
    vi.mocked(api).mockResolvedValue({
      actions: [
        {
          title: "Outline chapters",
          kind: "project",
          weekly_minutes: 90,
          rationale: "Make the next writing session concrete.",
        },
      ],
    });
    render(<Suggestions kind="actions" goal={goal} onUse={onUse} />);
    fireEvent.click(
      screen.getByRole("button", { name: c.coach.suggestActions }),
    );
    expect(await screen.findByText("Outline chapters")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: c.cancel }));
    expect(onUse).not.toHaveBeenCalled();
    expect(screen.queryByText("Outline chapters")).not.toBeInTheDocument();
    expect(api).toHaveBeenCalledTimes(1);
  });

  it("maps a reviewed action into editable local defaults without inventing a total estimate", async () => {
    const onUse = vi.fn();
    vi.mocked(api).mockResolvedValue({
      actions: [
        {
          title: "Outline chapters",
          kind: "project",
          weekly_minutes: 90,
          rationale: "Keep a recurring time for outlining.",
        },
      ],
    });
    render(<Suggestions kind="actions" goal={goal} onUse={onUse} />);
    fireEvent.click(
      screen.getByRole("button", { name: c.coach.suggestActions }),
    );
    fireEvent.click(
      await screen.findByRole("button", { name: c.coach.useSuggestions }),
    );
    expect(onUse).toHaveBeenCalledWith({
      actions: [
        {
          id: "",
          title: "Outline chapters",
          kind: "project",
          weekly_minutes_target: 90,
          total_minutes_estimate: null,
          min_block_minutes: 30,
          preferred_block_minutes: 60,
          max_block_minutes: 120,
          preferred_time_of_day: "any",
          requires_deep_focus: true,
        },
      ],
    });
    expect(api).toHaveBeenCalledWith(
      "/coach/suggest-actions",
      "POST",
      expect.objectContaining({ include_context: false }),
    );
  });

  it("maps reviewed obstacle risks into if-then plans only after Use", async () => {
    const onUse = vi.fn();
    vi.mocked(api).mockResolvedValue({
      obstacles: [
        {
          risk: "Messages interrupt writing",
          if_cue: "A new message arrives",
          then_response: "Reply after the focus session",
        },
      ],
    });
    render(<Suggestions kind="obstacles" goal={goal} onUse={onUse} />);
    fireEvent.click(
      screen.getByRole("button", { name: c.coach.suggestObstacles }),
    );
    expect(await screen.findByText("Messages interrupt writing")).toBeVisible();
    expect(onUse).not.toHaveBeenCalled();
    fireEvent.click(
      screen.getByRole("button", { name: c.coach.useSuggestions }),
    );
    expect(onUse).toHaveBeenCalledWith({
      obstacles: [
        {
          risk_text: "Messages interrupt writing",
          if_cue: "A new message arrives",
          then_response: "Reply after the focus session",
        },
      ],
    });
    expect(api).toHaveBeenCalledTimes(1);
  });

  it.each(["configured", "enabled"] as const)(
    "keeps manual fields usable when coaching is not %s",
    (flag) => {
      availability[flag] = false;
      render(
        <>
          <input aria-label="Manual goal" defaultValue="My goal" />
          <Suggestions kind="goal" goal={goal} onUse={vi.fn()} />
        </>,
      );
      expect(screen.getByLabelText("Manual goal")).toBeEnabled();
      expect(screen.queryByRole("button")).not.toBeInTheDocument();
      expect(api).not.toHaveBeenCalled();
    },
  );

  it("shows a provider error and permits retry without applying a proposal", async () => {
    const onUse = vi.fn();
    vi.mocked(api).mockRejectedValue(
      new Error("Coaching temporarily unavailable"),
    );
    render(<Suggestions kind="goal" goal={goal} onUse={onUse} />);
    fireEvent.click(screen.getByRole("button", { name: c.coach.suggestGoal }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Coaching temporarily unavailable",
    );
    expect(
      screen.getByRole("button", { name: c.coach.suggestGoal }),
    ).toBeEnabled();
    expect(onUse).not.toHaveBeenCalled();
  });
});
