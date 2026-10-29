import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api, queueWrite } from "../api/client";
import { GoalCheckin } from "./GoalCheckin";
import { BlockingStatus } from "./BlockingStatus";
import type { Goal } from "../api/types";
const mode = vi.hoisted(() => ({ online: true }));
vi.mock("../lib/hooks", () => ({
  useData: () => ({
    data: [{ id: "paired", last_used_at: "2026-10-28T10:00:00Z" }],
  }),
  useOnline: () => mode.online,
}));
vi.mock("../lib/auth", () => ({
  useAuth: () => ({ user: { id: "owner", timezone: "UTC" } }),
}));
vi.mock("../api/client", () => ({ api: vi.fn(), queueWrite: vi.fn() }));
afterEach(() => {
  cleanup();
  mode.online = true;
  vi.mocked(api).mockReset();
  vi.mocked(queueWrite).mockReset();
});
const goal = {
  id: "goal",
  metric_name: "Chapters",
  metric_unit: "chapters",
  metric_start: 2,
  checkins: [],
} as unknown as Goal;
function renderCheckin() {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <GoalCheckin goal={goal} />
    </QueryClientProvider>,
  );
}
describe("completion feedback", () => {
  it("records the explicit outcome value independently of session minutes", async () => {
    vi.mocked(api).mockResolvedValue({});
    renderCheckin();
    expect(api).not.toHaveBeenCalled();
    expect(screen.getByRole("spinbutton")).toHaveValue(2);
    fireEvent.change(screen.getByRole("spinbutton"), {
      target: { value: "3" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Log progress" }));
    await waitFor(() =>
      expect(api).toHaveBeenCalledWith("/goals/goal/checkins", "POST", {
        metric_value: 3,
        note: "",
      }),
    );
  });
  it("queues the same explicit check-in offline", async () => {
    mode.online = false;
    vi.mocked(queueWrite).mockResolvedValue(undefined);
    renderCheckin();
    fireEvent.click(screen.getByRole("button", { name: "Log progress" }));
    await waitFor(() =>
      expect(queueWrite).toHaveBeenCalledWith("/goals/goal/checkins", {
        metric_value: 2,
        note: "",
      }),
    );
    expect(api).not.toHaveBeenCalled();
  });
  it("pairing metadata never claims current blocking is verified", () => {
    vi.mocked(api).mockResolvedValue([]);
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <BlockingStatus domains={["example.test"]} timezone="UTC" />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(screen.getByText("Device paired")).toBeInTheDocument();
    expect(
      screen.getByText("Current blocking is not verified here."),
    ).toBeInTheDocument();
    expect(screen.getByText("example.test")).toBeInTheDocument();
  });
});
