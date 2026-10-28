import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../api/client";
import { copy as c } from "../copy/en";
import { Plan } from "./Plan";

vi.mock("../lib/auth", () => ({
  useAuth: () => ({ user: { id: "race-owner", timezone: "UTC" } }),
}));
vi.mock("../api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/client")>()),
  api: vi.fn(),
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
  vi.mocked(api).mockReset();
});

it("shows newly drafted blocks when an older initial week read finishes after the write", async () => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  let releaseOldRead: (blocks: unknown[]) => void = () => {};
  const oldRead = new Promise<unknown[]>((resolve) => {
    releaseOldRead = resolve;
  });
  let drafted = false;
  let weekReads = 0;
  const block = {
    id: "race-block",
    title: "Race regression block",
    goal_id: "goal",
    action_id: "action",
    start_at: "2026-11-02T09:00:00Z",
    end_at: "2026-11-02T10:00:00Z",
    planned_minutes: 60,
    status: "proposed",
    notes: "",
    reason: "Available time",
    week_start: "2026-11-02",
    moved_count: 0,
    google_event_id: null,
  };
  vi.mocked(api).mockImplementation(async (path, method) => {
    if (path.startsWith("/plan/week?")) {
      weekReads++;
      if (weekReads === 1) return oldRead;
      return drafted ? [block] : [];
    }
    if (path === "/plan/draft" && method === "POST") {
      drafted = true;
      return {
        blocks: [block],
        changes: [],
        message: "1 proposed block ready to review.",
        empty_reason: null,
        capacity_warning: null,
        dropped_minutes: 0,
      };
    }
    if (path === "/calendar/status") return { configured: false };
    return [];
  });
  // Deliver the pre-write snapshot only when mutation invalidation reaches the read.
  const unsubscribe = client.getQueryCache().subscribe((event) => {
    if (
      event.type === "updated" &&
      event.action.type === "invalidate" &&
      String(event.query.queryKey[1]).startsWith("/plan/week?")
    )
      queueMicrotask(() => releaseOldRead([]));
  });
  try {
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <Plan />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: c.plan.draft }));
    expect(
      await screen.findByText("1 proposed block ready to review."),
    ).toBeVisible();
    expect(
      await screen.findByRole("button", { name: c.plan.accept }),
    ).toBeVisible();
    expect(weekReads).toBeGreaterThan(1);
  } finally {
    unsubscribe();
    client.clear();
  }
});
