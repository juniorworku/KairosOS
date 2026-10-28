import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { MemoryRouter, useLocation } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { api } from "../api/client";
import { Plan } from "./Plan";
import { AgendaChanges } from "./AgendaChanges";
import type { NotedBlock } from "../api/agenda";
vi.mock("../api/client", () => ({ api: vi.fn(async () => ({})) }));
vi.mock("../lib/auth", () => ({
  useAuth: () => ({
    user: {
      id: "test",
      timezone: "UTC",
      work_days: [0, 1, 2, 3, 4],
      work_start: "09:00",
      work_end: "17:00",
    },
  }),
}));
vi.mock("../lib/hooks", () => ({
  useData: () => ({ data: [], isPending: false, dataUpdatedAt: 0 }),
  useOnline: () => true,
}));
vi.mock("@fullcalendar/react", async () => {
  const React = await import("react");
  return {
    default: React.forwardRef(function Calendar(_props, ref) {
      React.useImperativeHandle(ref, () => ({
        getApi: () => ({ gotoDate: vi.fn() }),
      }));
      return <div />;
    }),
  };
});
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});
function Location() {
  return <output aria-label="Location">{useLocation().search}</output>;
}
function mount(node: React.ReactNode, path = "/plan") {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[path]}>
        {node}
        <Location />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
it("uses linked dates and preserves context while navigating", () => {
  mount(<Plan />, "/plan?date=2026-11-04&goal=goal-1&block=block-1");
  expect(screen.getByLabelText("Selected date")).toHaveValue("2026-11-04");
  fireEvent.change(screen.getByLabelText("Selected date"), {
    target: { value: "2026-11-12" },
  });
  expect(screen.getByLabelText("Location")).toHaveTextContent(
    "date=2026-11-12&goal=goal-1&block=block-1",
  );
  expect(screen.getByText("Work hours")).toBeVisible();
});
it("summarizes additions without writing and keeps only after explicit consent", async () => {
  const block: NotedBlock = {
    id: "added",
    title: "Write chapter",
    notes: "",
    goal_id: "goal",
    action_id: "action",
    status: "proposed",
    start_at: "2026-11-04T09:00:00Z",
    end_at: "2026-11-04T10:00:00Z",
    planned_minutes: 60,
    reason: "Available work hours",
    week_start: "2026-11-02",
    moved_count: 0,
    google_event_id: null,
  };
  const onChange = vi.fn(async () => {});
  mount(
    <AgendaChanges
      additions={[block]}
      changes={[]}
      timezone="UTC"
      online
      onChange={onChange}
    />,
  );
  expect(screen.getByText("1 added · 0 moved · 0 removed")).toBeVisible();
  expect(api).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Keep Write chapter" }));
  await waitFor(() =>
    expect(api).toHaveBeenCalledWith("/plan/accept", "POST", {
      block_ids: ["added"],
    }),
  );
  expect(api).not.toHaveBeenCalledWith(
    "/calendar/publish",
    expect.anything(),
    expect.anything(),
  );
});
it("discards a proposed addition without removing an accepted block", async () => {
  const block = {
    id: "draft-only",
    title: "Draft action",
    status: "proposed",
    start_at: "2026-11-04T09:00:00Z",
    end_at: "2026-11-04T10:00:00Z",
    reason: "",
  } as NotedBlock;
  mount(
    <AgendaChanges
      additions={[block]}
      changes={[]}
      timezone="UTC"
      online
      onChange={async () => {}}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Discard Draft action" }));
  await waitFor(() =>
    expect(api).toHaveBeenCalledWith("/blocks/draft-only", "DELETE"),
  );
});
