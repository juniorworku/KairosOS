import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../api/client";
import { FocusPage } from "./Focus";
const fixtures = vi.hoisted(() => ({
  goal: {
    id: "goal",
    title: "Write a book",
    metric_name: "Chapters",
    metric_unit: "chapters",
    metric_start: 2,
    checkins: [],
    status: "active",
    actions: [{ id: "action", title: "Draft a chapter" }],
  },
  session: {
    id: "session",
    goal_id: "goal",
    action_id: "action",
    time_block_id: "block",
    title: "Draft a chapter",
    planned_minutes: 25,
    started_at: new Date(Date.now() - 600000).toISOString(),
    ends_at: new Date(Date.now() + 900000).toISOString(),
    ended_at: null,
    self_rating: null,
    actual_minutes: null,
    blocklist_snapshot: ["example.test"],
  },
}));
vi.mock("../lib/auth", () => ({
  useAuth: () => ({ user: { id: "owner", timezone: "UTC" } }),
}));
vi.mock("../lib/hooks", () => ({
  useOnline: () => true,
  useData: (path: string) => ({
    data:
      path === "/goals"
        ? [fixtures.goal]
        : path.startsWith("/focus/sessions")
          ? { items: [], next_cursor: null }
          : [],
  }),
}));
vi.mock("../api/client", () => ({ api: vi.fn(), queueWrite: vi.fn() }));
afterEach(() => {
  cleanup();
  vi.mocked(api).mockReset();
});
it("connects stopping and rating to a separate explicit outcome check-in", async () => {
  let active = true;
  vi.mocked(api).mockImplementation(async (path, method) => {
    if (path === "/focus/active") return active ? fixtures.session : null;
    if (path === "/focus/session/end" && method === "POST") {
      active = false;
      return {
        ...fixtures.session,
        ended_at: new Date().toISOString(),
        actual_minutes: 10,
      };
    }
    return {};
  });
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <FocusPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  fireEvent.click(await screen.findByRole("button", { name: "End session" }));
  fireEvent.click(
    await screen.findByRole("button", { name: "4" }),
  );
  fireEvent.click(screen.getByRole("button", { name: "Save session" }));
  await waitFor(() =>
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
  );
  expect(screen.getByRole("link", { name: "View goal" })).toHaveAttribute(
    "href",
    "/goals/goal",
  );
  expect(
    screen
      .getByRole("link", { name: "View this block in the plan" })
      .getAttribute("href"),
  ).toContain("goal=goal&block=block");
  expect(
    screen.getByRole("spinbutton", { name: "Chapters (chapters)" }),
  ).toHaveValue(2);
  expect(
    vi
      .mocked(api)
      .mock.calls.filter((call) => call[0] === "/goals/goal/checkins"),
  ).toHaveLength(0);
  fireEvent.change(
    screen.getByRole("spinbutton", { name: "Chapters (chapters)" }),
    { target: { value: "3" } },
  );
  fireEvent.click(screen.getByRole("button", { name: "Log progress" }));
  await waitFor(() =>
    expect(api).toHaveBeenCalledWith("/goals/goal/checkins", "POST", {
      metric_value: 3,
      note: "",
    }),
  );
});
