import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { api } from "../api/client";
import type {
  Block,
  FocusSession,
  Goal,
  Season,
  Trajectory,
} from "../api/types";
import type { AgendaItem } from "../api/agenda";
import { Today } from "./Today";
import { GoalDetail, GoalEditor } from "./Goals";
import { SeasonOverview } from "./SeasonOverview";
import {
  calendarDays,
  nextAccepted,
  outcomeEvidence,
  planDay,
  selectedSeason,
} from "./workflow-data";
import { copy as c, agendaCopy as a } from "../copy/en";
import { workflowCopy as w } from "../copy/workflow";

const state = vi.hoisted(() => ({
  data: {} as Record<string, unknown>,
  online: true,
  refetch: vi.fn(),
}));
vi.mock("../api/client", () => ({
  api: vi.fn(),
  readDraft: vi.fn(async () => undefined),
  saveDraft: vi.fn(async () => {}),
  deleteDraft: vi.fn(async () => {}),
  queueWrite: vi.fn(async () => {}),
}));
vi.mock("../lib/auth", () => ({
  useAuth: () => ({
    user: {
      id: "owner",
      timezone: "UTC",
      work_start: "09:00",
      work_end: "17:00",
      work_days: [0, 1, 2, 3, 4],
    },
  }),
}));
vi.mock("../lib/hooks", () => ({
  useOnline: () => state.online,
  useData: (path: string, enabled = true) => ({
    data: !enabled
      ? undefined
      : path in state.data
        ? state.data[path]
        : path === "/focus/active" || path.startsWith("/reflection/")
          ? null
          : path.startsWith("/focus/stats")
            ? { total_minutes: 12, completed_sessions: 1, average_rating: 4 }
            : [],
    isPending: false,
    isError: false,
    error: null,
    dataUpdatedAt: 1,
    refetch: state.refetch,
  }),
}));

const season: Season = {
  id: "season",
  name: "Writing season",
  start_date: "2026-10-01",
  end_date: "2026-12-23",
  status: "active",
};
const goal: Goal = {
  id: "goal",
  title: "Finish the manuscript",
  outcome_statement: "Draft ten chapters",
  season_id: "season",
  metric_name: "Chapters",
  metric_unit: "chapters",
  metric_start: 0,
  metric_target: 10,
  start_date: "2026-10-01",
  target_date: "2026-12-23",
  why_facts: "",
  why_feelings: "",
  why_function: "",
  anti_goals: [],
  confidence_pct: 80,
  follow_through_pct: 80,
  priority: 3,
  status: "active",
  actions: [
    {
      id: "action",
      title: "Write the next section",
      kind: "habit",
      weekly_minutes_target: 120,
      total_minutes_estimate: null,
      preferred_block_minutes: 60,
      min_block_minutes: 30,
      max_block_minutes: 120,
      preferred_time_of_day: "morning",
      requires_deep_focus: true,
    },
  ],
  obstacles: [],
  checkins: [
    {
      id: "check",
      goal_id: "goal",
      metric_value: 2,
      note: "Two chapters",
      recorded_at: "2026-10-31T10:00:00Z",
      client_event_id: null,
    },
  ],
};
const block: Block = {
  id: "block",
  goal_id: "goal",
  action_id: "action",
  title: "Write the next section",
  start_at: "2026-11-02T09:00:00Z",
  end_at: "2026-11-02T10:00:00Z",
  planned_minutes: 60,
  status: "accepted",
  reason: "Morning availability",
  week_start: "2026-11-02",
  moved_count: 0,
  google_event_id: null,
  notes: "",
};
const trajectory: Trajectory = {
  goal_id: "goal",
  status: "off_track",
  expected_fraction: 0.4,
  actual_fraction: 0.2,
  effort_ratio: 0.5,
  projected_finish: "2027-01-01",
  reasons: ["Recorded progress compared with time elapsed."],
};
function agendaItem(
  source: "block" | "local" | "google",
  title: string,
  id: string,
): AgendaItem {
  return {
    id,
    source,
    source_id: source === "block" ? "block" : id,
    title,
    notes: "",
    start_at: "2026-11-02T09:00:00Z",
    end_at: "2026-11-02T10:00:00Z",
    all_day: false,
    timezone: "UTC",
    status: source === "block" ? "accepted" : "confirmed",
    editable: source !== "google",
    goal_id: source === "block" ? "goal" : null,
    action_id: null,
    task_id: null,
    occurrence_date: null,
    recurring: false,
    calendar_id: null,
    calendar_name: source === "google" ? "Work calendar" : null,
    etag: null,
  };
}
function Location() {
  return (
    <p data-testid="route">
      {useLocation().pathname}
      {useLocation().search}
      {useLocation().hash}
    </p>
  );
}
function mount(element: React.ReactNode, path = "/today") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        {element}
        <Location />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
function overview(props: Partial<Parameters<typeof SeasonOverview>[0]> = {}) {
  return (
    <SeasonOverview
      seasons={[season]}
      goals={[goal]}
      trajectories={[trajectory]}
      blocks={[block]}
      today="2026-11-02"
      timezone="UTC"
      online
      through="2026-11-15"
      {...props}
    />
  );
}
beforeEach(() => {
  vi.spyOn(Date, "now").mockReturnValue(Date.parse("2026-11-02T08:00:00Z"));
  vi.mocked(api).mockReset();
  vi.mocked(api).mockResolvedValue({});
  state.data = {
    "/seasons": [season],
    "/goals": [goal],
    "/trajectory": [trajectory],
    "/plan/week?start=2026-11-02": [block],
    "/plan/week?start=2026-11-09": [],
    "/calendar/status": { connected: false },
    "/agenda?start=2026-11-02&end=2026-11-03": [
      agendaItem("block", block.title, "block:item"),
    ],
  };
  state.online = true;
  state.refetch.mockReset();
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("persisted season workflow", () => {
  it("shows recorded outcome, expected pace and a contextual accepted action without a score", () => {
    mount(overview());
    expect(screen.getByRole("heading", { name: season.name })).toBeVisible();
    expect(screen.getByText("2 / 10 chapters")).toBeVisible();
    expect(
      screen.getByText(/Recorded outcome 20%.*Expected by today 40%/),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: /Write the next section/ }),
    ).toHaveAttribute("href", "/plan?date=2026-11-02&goal=goal&block=block");
    expect(
      screen.queryByText(/strength|quality score|productivity score/i),
    ).not.toBeInTheDocument();
  });
  it("creates a real season and links the next goal to its persisted id", async () => {
    vi.mocked(api).mockResolvedValue(season);
    mount(overview({ seasons: [], goals: [] }));
    fireEvent.click(screen.getByRole("button", { name: w.createSeason }));
    const dialog = screen.getByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText(w.seasonName), {
      target: { value: season.name },
    });
    fireEvent.click(
      within(dialog).getByRole("button", { name: w.createSeason }),
    );
    await waitFor(() =>
      expect(api).toHaveBeenCalledWith(
        "/seasons",
        "POST",
        expect.objectContaining({ name: season.name, status: "active" }),
      ),
    );
    expect(
      await screen.findByRole("link", { name: w.addSeasonGoal }),
    ).toHaveAttribute("href", "/goals/new?season=season");
  });
  it("assigns an existing goal while preserving its action ids and measured data", async () => {
    mount(overview({ goals: [{ ...goal, season_id: null }] }));
    fireEvent.click(screen.getByRole("button", { name: w.addExisting }));
    const dialog = screen.getByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: w.assignGoal }));
    await waitFor(() =>
      expect(api).toHaveBeenCalledWith(
        "/goals/goal",
        "PATCH",
        expect.objectContaining({
          season_id: "season",
          actions: goal.actions,
          checkins: goal.checkins,
        }),
      ),
    );
  });
  it("preselects the owned season and its dates in the existing goal editor", async () => {
    mount(<GoalEditor />, "/goals/new?season=season");
    expect(await screen.findByLabelText("Season")).toHaveValue("season");
    expect(screen.getByLabelText(c.goals.form.startDate)).toHaveValue(
      season.start_date,
    );
    expect(screen.getByLabelText(c.goals.form.due)).toHaveValue(
      season.end_date,
    );
  });
  it("lands a progress link on the actual loaded goal check-in heading", async () => {
    state.data["/goals/goal"] = goal;
    mount(
      <Routes>
        <Route path="/goals/:id" element={<GoalDetail />} />
      </Routes>,
      "/goals/goal#check-in",
    );
    const heading = await screen.findByRole("heading", {
      name: "Record progress",
    });
    expect(heading).toHaveAttribute("id", "check-in");
    expect(heading).toHaveFocus();
  });
});

describe("connected Today", () => {
  it("starts the next accepted goal action and opens a specific calendar day", async () => {
    mount(<Today />);
    const hero = screen.getByRole("region", { name: block.title });
    fireEvent.click(within(hero).getByRole("button", { name: "Start focus" }));
    await waitFor(() =>
      expect(api).toHaveBeenCalledWith("/focus/start", "POST", {
        time_block_id: "block",
        planned_minutes: 60,
      }),
    );
    await waitFor(() =>
      expect(screen.getByTestId("route")).toHaveTextContent("/focus"),
    );
    expect(
      screen.getByRole("link", { name: /Tuesday 2026-11-03/ }),
    ).toHaveAttribute("href", "/plan?date=2026-11-03");
  });
  it("prioritizes a running session and prevents another start", () => {
    const active: FocusSession = {
      id: "focus",
      time_block_id: "block",
      action_id: "action",
      goal_id: "goal",
      title: "Current writing",
      started_at: "2026-11-02T07:50:00Z",
      ends_at: "2026-11-02T08:15:00Z",
      ended_at: null,
      planned_minutes: 25,
      actual_minutes: 0,
      self_rating: null,
      blocklist_id: null,
      blocklist_snapshot: [],
    };
    state.data["/focus/active"] = active;
    mount(<Today />);
    expect(screen.getByRole("heading", { name: active.title })).toBeVisible();
    expect(screen.getByRole("link", { name: /Resume/ })).toHaveAttribute(
      "href",
      "/focus",
    );
    expect(screen.getByRole("button", { name: "Start focus" })).toBeDisabled();
    expect(api).not.toHaveBeenCalled();
  });
  it("shows unified local and Google appointments once, without starting them or treating drafts as accepted", () => {
    state.data["/agenda?start=2026-11-02&end=2026-11-03"] = [
      agendaItem("block", block.title, "block:item"),
      agendaItem("local", "Dentist", "local:appointment"),
      agendaItem("google", "Team call", "google:meeting"),
      { ...agendaItem("block", "Draft only", "draft"), status: "proposed" },
      { ...agendaItem("block", "Skipped", "skipped"), status: "skipped" },
    ];
    state.data["/calendar/status"] = {
      connected: true,
      details_error: "provider unavailable",
    };
    mount(<Today />);
    const schedule = screen.getByRole("region", { name: "Schedule" });
    expect(
      within(schedule).getByRole("link", { name: "Dentist" }),
    ).toBeVisible();
    expect(
      within(schedule).getAllByRole("link", { name: "Team call" }),
    ).toHaveLength(1);
    expect(
      within(schedule).getAllByRole("button", { name: "Start focus" }),
    ).toHaveLength(1);
    expect(within(schedule).queryByText("Draft only")).not.toBeInTheDocument();
    expect(within(schedule).queryByText("Skipped")).not.toBeInTheDocument();
    expect(within(schedule).getByRole("status")).toHaveTextContent(
      a.detailsUnavailable,
    );
    expect(state.refetch).toHaveBeenCalled();
  });
  it("routes overdue task rows to the task context in today's calendar", () => {
    state.data["/tasks"] = [
      {
        id: "task",
        title: "Send draft",
        notes: "",
        due_date: "2026-11-01",
        status: "todo",
        estimated_minutes: 30,
        goal_id: null,
      },
    ];
    mount(<Today />);
    expect(
      screen.getByRole("link", { name: /Send draft.*Overdue/ }),
    ).toHaveAttribute("href", "/plan?date=2026-11-02&task=task#agenda-tasks");
  });
});

describe("workflow calculations", () => {
  it("uses calendar days across daylight-saving changes and chooses actual dated seasons", () => {
    expect(calendarDays("2026-03-07", "2026-03-09")).toBe(2);
    expect(
      selectedSeason(
        [{ ...season, id: "old", status: "done" }, season],
        "2026-11-02",
      )?.id,
    ).toBe("season");
    expect(planDay("2026-11-02", "a b", "block")).toBe(
      "/plan?date=2026-11-02&goal=a+b&block=block",
    );
  });
  it("never starts proposed/completed work and supports decreasing outcome measures", () => {
    expect(
      nextAccepted(
        [
          { ...block, status: "proposed" },
          { ...block, id: "done", status: "completed" },
        ],
        Date.now(),
        "2026-11-02",
        "UTC",
      ),
    ).toBeUndefined();
    expect(
      outcomeEvidence({
        ...goal,
        metric_start: 100,
        metric_target: 0,
        checkins: [{ ...goal.checkins[0], metric_value: 50 }],
      }).fraction,
    ).toBe(0.5);
  });
});
