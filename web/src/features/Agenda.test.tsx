import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { api } from "../api/client";
import type { AgendaItem, LocalEvent, PlanChange, Task } from "../api/agenda";
import { agendaCopy as a, copy as c } from "../copy/en";
import { AgendaEditor } from "./AgendaEditor";
import { AgendaChanges } from "./AgendaChanges";
import { AgendaTasks } from "./AgendaTasks";
import { Plan } from "./Plan";

const state = vi.hoisted(() => ({
  data: {} as Record<string, unknown>,
  refetch: vi.fn(),
}));
vi.mock("../api/client", () => ({ api: vi.fn() }));
vi.mock("../lib/auth", () => ({
  useAuth: () => ({ user: { id: "owner", timezone: "UTC" } }),
}));
vi.mock("../lib/hooks", () => ({
  useData: (path: string) => ({
    data: state.data[path],
    isPending: false,
    error: null,
    dataUpdatedAt: 0,
    refetch: state.refetch,
  }),
  useOnline: () => true,
}));
vi.mock("@fullcalendar/react", async () => {
  const React = await import("react");
  return {
    default: React.forwardRef(function Calendar(_props, ref) {
      React.useImperativeHandle(ref, () => ({
        getApi: () => ({ gotoDate: vi.fn() }),
      }));
      return <div data-testid="calendar" />;
    }),
  };
});
const onChange = vi.fn(async () => {});
const close = vi.fn();
const event: LocalEvent = {
  id: "series",
  title: "Weekly planning",
  notes: "Original notes",
  start_at: "2026-11-02T09:00:00Z",
  end_at: "2026-11-02T10:00:00Z",
  timezone: "UTC",
  all_day: false,
  task_id: null,
  recurrence: {
    frequency: "weekly",
    interval: 1,
    weekdays: [0],
    until: null,
    count: 12,
  },
};
const occurrence: AgendaItem = {
  id: "local:series:2026-11-09",
  source: "local",
  source_id: "series",
  title: event.title,
  notes: event.notes,
  start_at: "2026-11-09T09:00:00Z",
  end_at: "2026-11-09T10:00:00Z",
  timezone: "UTC",
  all_day: false,
  status: "active",
  editable: true,
  recurring: true,
  occurrence_date: "2026-11-09",
  task_id: null,
  goal_id: null,
  action_id: null,
  calendar_id: null,
  calendar_name: null,
  etag: null,
};
function mount(
  element: React.ReactNode,
  queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  }),
) {
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{element}</MemoryRouter>
    </QueryClientProvider>,
  );
}
function editor(
  selection: Parameters<typeof AgendaEditor>[0]["selection"],
  timezone = "UTC",
) {
  return mount(
    <AgendaEditor
      selection={selection}
      timezone={timezone}
      goals={[]}
      tasks={[]}
      online
      close={close}
      onChange={onChange}
      onFocus={vi.fn()}
    />,
  );
}
beforeEach(() => {
  vi.mocked(api).mockReset();
  vi.mocked(api).mockResolvedValue({});
  onChange.mockClear();
  close.mockClear();
  state.data = { "/events/series": event };
  Object.defineProperty(HTMLDialogElement.prototype, "showModal", {
    configurable: true,
    value: function (this: HTMLDialogElement) {
      this.setAttribute("open", "");
    },
  });
  Object.defineProperty(HTMLDialogElement.prototype, "close", {
    configurable: true,
    value: function (this: HTMLDialogElement) {
      this.removeAttribute("open");
    },
  });
  vi.spyOn(window, "confirm").mockReturnValue(true);
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("local agenda editing", () => {
  it.each(["monthly", "yearly"])(
    "wires %s repeats to the event API",
    async (frequency) => {
      editor({
        kind: "event",
        start: "2026-01-31T09:00:00Z",
        end: "2026-01-31T10:00:00Z",
      });
      fireEvent.change(screen.getByLabelText(a.title), {
        target: { value: "Planning review" },
      });
      fireEvent.click(screen.getByLabelText(a.repeats));
      fireEvent.change(screen.getByLabelText(a.frequency), {
        target: { value: frequency },
      });
      expect(
        screen.getByText(/Months or years without that date are skipped/),
      ).toBeVisible();
      fireEvent.click(screen.getByRole("button", { name: a.saveEvent }));
      await waitFor(() =>
        expect(api).toHaveBeenCalledWith(
          "/events",
          "POST",
          expect.objectContaining({
            recurrence: expect.objectContaining({
              frequency,
              weekdays: [],
              count: expect.any(Number),
            }),
          }),
        ),
      );
    },
  );

  it("saves a one-day event using local midnight and an exclusive end", async () => {
    editor(
      { kind: "event", start: "2026-11-02", end: "2026-11-03", allDay: true },
      "Africa/Addis_Ababa",
    );
    fireEvent.change(screen.getByLabelText(a.title), {
      target: { value: "Protected day" },
    });
    fireEvent.click(screen.getByRole("button", { name: a.saveEvent }));
    await waitFor(() =>
      expect(api).toHaveBeenCalledWith(
        "/events",
        "POST",
        expect.objectContaining({
          title: "Protected day",
          start_at: "2026-11-01T21:00:00.000Z",
          end_at: "2026-11-02T21:00:00.000Z",
          all_day: true,
          timezone: "Africa/Addis_Ababa",
          recurrence: null,
        }),
      ),
    );
    expect(onChange).toHaveBeenCalled();
  });
  it("edits a recurring occurrence without modifying the series rule", async () => {
    editor({ kind: "event", item: occurrence });
    fireEvent.change(screen.getByLabelText(a.notes), {
      target: { value: "Only this Monday" },
    });
    fireEvent.click(screen.getByRole("button", { name: a.saveEvent }));
    await waitFor(() => expect(api).toHaveBeenCalled());
    const [path, method, body] = vi.mocked(api).mock.calls[0];
    expect(path).toBe("/events/series/occurrences/2026-11-09");
    expect(method).toBe("PATCH");
    expect(body).toEqual(
      expect.objectContaining({ notes: "Only this Monday" }),
    );
    expect(body).not.toHaveProperty("recurrence");
  });
  it("edits the complete series only when that scope is explicitly chosen", async () => {
    editor({ kind: "event", item: occurrence });
    fireEvent.click(screen.getByRole("button", { name: a.wholeSeries }));
    fireEvent.change(screen.getByLabelText(a.title), {
      target: { value: "New series title" },
    });
    fireEvent.click(screen.getByRole("button", { name: a.saveEvent }));
    await waitFor(() =>
      expect(api).toHaveBeenCalledWith(
        "/events/series",
        "PATCH",
        expect.objectContaining({
          title: "New series title",
          start_at: "2026-11-02T09:00:00.000Z",
          recurrence: event.recurrence,
        }),
      ),
    );
  });
  it("deletes only the chosen occurrence", async () => {
    editor({ kind: "event", item: occurrence });
    fireEvent.click(screen.getByRole("button", { name: a.deleteOccurrence }));
    await waitFor(() =>
      expect(api).toHaveBeenCalledWith(
        "/events/series/occurrences/2026-11-09",
        "DELETE",
      ),
    );
    expect(window.confirm).toHaveBeenCalledWith(a.confirmOccurrenceDelete);
  });
  it("keeps Google details read-only and renders notes as text", () => {
    editor({
      kind: "event",
      item: {
        ...occurrence,
        source: "google",
        editable: false,
        notes: "<script>private text</script>",
      },
    });
    expect(screen.getByText("<script>private text</script>")).toBeVisible();
    expect(
      screen.queryByRole("button", { name: a.saveEvent }),
    ).not.toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(api).not.toHaveBeenCalled();
  });
});
describe("tasks and plan review", () => {
  it("focuses a task linked from Today without scheduling it automatically", () => {
    const original = Object.getOwnPropertyDescriptor(
      Element.prototype,
      "scrollIntoView",
    );
    const scroll = vi.fn();
    Object.defineProperty(Element.prototype, "scrollIntoView", {
      configurable: true,
      value: scroll,
    });
    try {
      const task: Task = {
        id: "due-task",
        title: "Read paper",
        notes: "",
        due_date: "2026-11-04",
        goal_id: null,
        status: "todo",
        estimated_minutes: 30,
      };
      mount(
        <AgendaTasks
          tasks={[task]}
          goals={[]}
          online
          pending={false}
          error={null}
          onChange={onChange}
          onSchedule={vi.fn()}
          selectedTaskId={task.id}
        />,
      );
      const target = document.getElementById("agenda-task-due-task");
      expect(target).toHaveFocus();
      expect(target).toHaveClass("is-context-task");
      expect(scroll).toHaveBeenCalledWith({ block: "nearest" });
      expect(api).not.toHaveBeenCalled();
    } finally {
      if (original)
        Object.defineProperty(Element.prototype, "scrollIntoView", original);
      else Reflect.deleteProperty(Element.prototype, "scrollIntoView");
    }
  });

  it("marks a task done and schedules its details without creating an event automatically", async () => {
    const task: Task = {
      id: "task",
      title: "Read paper",
      notes: "Chapters 1–2",
      due_date: null,
      goal_id: null,
      status: "todo",
      estimated_minutes: 45,
    };
    const schedule = vi.fn();
    mount(
      <AgendaTasks
        tasks={[task]}
        goals={[]}
        online
        pending={false}
        error={null}
        onChange={onChange}
        onSchedule={schedule}
      />,
    );
    fireEvent.click(
      screen.getByRole("button", { name: `${a.scheduleTask}: ${task.title}` }),
    );
    expect(schedule).toHaveBeenCalledWith(task);
    expect(api).not.toHaveBeenCalled();
    fireEvent.click(
      screen.getByRole("button", { name: `${a.markDone}: ${task.title}` }),
    );
    await waitFor(() =>
      expect(api).toHaveBeenCalledWith("/tasks/task", "PATCH", {
        status: "done",
      }),
    );
  });
  it("applies a move only after showing the current and proposed times", async () => {
    const before = {
      id: "block",
      title: "Write",
      notes: "",
      start_at: "2026-11-02T09:00:00Z",
      end_at: "2026-11-02T10:00:00Z",
      goal_id: "goal",
      action_id: "action",
      planned_minutes: 60,
      status: "accepted" as const,
      reason: "Scheduled",
      week_start: "2026-11-02",
      moved_count: 0,
      google_event_id: null,
    };
    const change: PlanChange = {
      id: "change",
      block_id: "block",
      operation: "move",
      status: "pending",
      before,
      after: {
        ...before,
        start_at: "2026-11-02T13:00:00Z",
        end_at: "2026-11-02T14:00:00Z",
      },
      reason: "A meeting overlaps",
      created_at: "2026-11-01T09:00:00Z",
      applied_at: null,
    };
    mount(
      <AgendaChanges
        changes={[change]}
        timezone="UTC"
        online
        onChange={onChange}
      />,
    );
    expect(screen.getByText(a.before)).toBeVisible();
    expect(screen.getByText(a.after)).toBeVisible();
    expect(api).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Keep change" }));
    await waitFor(() =>
      expect(api).toHaveBeenCalledWith(
        "/plan/changes/change/accept",
        "POST",
        {},
      ),
    );
  });
  it("explains an empty draft instead of leaving an apparently inactive button", async () => {
    state.data = {
      "/tasks": [],
      "/goals": [],
      "/busy": [],
      "/calendar/busy": [],
      "/calendar/status": { configured: false },
    };
    vi.mocked(api).mockResolvedValue({
      blocks: [],
      message: "Add a goal and an action to draft your week.",
      empty_reason: "no_goals",
      changes: [],
    });
    mount(<Plan />);
    fireEvent.click(screen.getByRole("button", { name: c.plan.draft }));
    expect(
      await screen.findByText("Add a goal and an action to draft your week."),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: c.goals.new })).toBeVisible();
    expect(api).toHaveBeenCalledWith(
      "/plan/draft",
      "POST",
      expect.objectContaining({ week_start: expect.any(String) }),
    );
  });
});

it("hides consented Google details without disconnecting calendar availability", async () => {
  state.data = {
    "/tasks": [],
    "/goals": [],
    "/busy": [],
    "/calendar/busy": [],
    "/calendar/status": {
      configured: true,
      details_enabled: true,
      connected: true,
    },
  };
  const memory = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const oldWeek = ["owner", "/agenda?start=2026-10-05&end=2026-10-12"];
  memory.setQueryData(oldWeek, [
    { source: "google", title: "Private old event" },
  ]);
  memory.setQueryData(
    ["another-owner", oldWeek[1]],
    [{ title: "Separate account" }],
  );
  mount(<Plan />, memory);
  expect(api).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: a.hideDetails }));
  await waitFor(() =>
    expect(api).toHaveBeenCalledWith("/calendar/details", "DELETE", undefined),
  );
  await waitFor(() => expect(memory.getQueryData(oldWeek)).toBeUndefined());
  expect(memory.getQueryData(["another-owner", oldWeek[1]])).toEqual([
    { title: "Separate account" },
  ]);
  expect(api).not.toHaveBeenCalledWith(
    "/calendar/disconnect",
    expect.anything(),
    expect.anything(),
  );
});
