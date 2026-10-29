import { cleanup, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../api/client";
import { NativeBlockingStatus } from "./NativeBlocking";
const mode = vi.hoisted(() => ({ online: true }));
vi.mock("../lib/auth", () => ({
  useAuth: () => ({ user: { id: "owner", timezone: "UTC" } }),
}));
vi.mock("../lib/hooks", () => ({ useOnline: () => mode.online }));
vi.mock("../api/client", () => ({ api: vi.fn() }));
afterEach(() => {
  cleanup();
  vi.mocked(api).mockReset();
  mode.online = true;
});
const report = {
  credential_id: "credential",
  last_seen_at: "2026-10-28T01:00:00Z",
  label: "Linux companion",
  mode: "blocking",
  suspended_count: 2,
  connected: true,
};
function mount() {
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <MemoryRouter>
        <NativeBlockingStatus />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
it("shows a recent helper report without claiming measured attention or OS verification", async () => {
  vi.mocked(api).mockResolvedValue([report]);
  mount();
  expect(
    await screen.findByText("Last report: 2 app processes paused."),
  ).toBeVisible();
  expect(screen.queryByText(/attention score/i)).not.toBeInTheDocument();
  expect(
    screen.getByRole("link", { name: "Set up native blocking" }),
  ).toHaveAttribute("href", "/settings#native-blocking");
  expect(
    vi.mocked(api).mock.calls.every(([, method]) => method === "GET"),
  ).toBe(true);
});
it("does not present stale blocking counts as current", async () => {
  vi.mocked(api).mockResolvedValue([{ ...report, connected: false }]);
  mount();
  expect(
    await screen.findByText(
      "No recent verified report. Check the companion on this device.",
    ),
  ).toBeVisible();
  expect(
    screen.queryByText("Last report: 2 app processes paused."),
  ).not.toBeInTheDocument();
});
it("does not claim a live helper while the app is offline", async () => {
  mode.online = false;
  vi.mocked(api).mockResolvedValue([report]);
  mount();
  expect(await screen.findByText("Not verified")).toBeVisible();
  expect(screen.queryByText("Recent helper report")).not.toBeInTheDocument();
});
