import "fake-indexeddb/auto";
import {
  render,
  screen,
  fireEvent,
  cleanup,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import { AuthProvider } from "./lib/auth";
import { clearPrivateData, setAccount } from "./api/client";
import type { User } from "./api/types";
vi.mock("virtual:pwa-register", () => ({ registerSW: () => vi.fn() }));
const user: User = {
  id: "test-user",
  email: "test@example.test",
  name: "Test",
  timezone: "Africa/Addis_Ababa",
  work_days: [0, 1, 2, 3, 4],
  work_start: "09:00",
  work_end: "17:00",
  daily_max_focus_minutes: 240,
  energy_peak: "morning",
  role: "owner",
  plan_id: "owner",
  ai_enabled: false,
  avatar_url: null,
  onboarding_completed_at: null,
  disabled_at: null,
};
function mount(path = "/today") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  client.setQueryData(["me"], user);
  setAccount(user.id);
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <AuthProvider>
          <App />
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
beforeEach(async () => {
  await clearPrivateData();
  vi.stubGlobal(
    "matchMedia",
    vi.fn(() => ({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  );
  vi.stubGlobal("scrollTo", vi.fn());
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string | URL | Request) => {
      const path = String(input);
      let data: unknown = [];
      if (path.endsWith("/me")) data = user;
      else if (path.includes("/auth/csrf")) data = { csrf_token: "test-csrf" };
      else if (path.includes("/focus/stats"))
        data = {
          completed_sessions: 0,
          total_minutes: 0,
          average_rating: null,
        };
      else if (path.includes("/focus/active")) data = null;
      else if (path.includes("/coach/status"))
        data = { enabled: false, configured: false };
      return new Response(JSON.stringify(data), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
  localStorage.clear();
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
describe("functional shell", () => {
  it("shows a plain Today page with real empty states", async () => {
    mount();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "Today",
    );
    expect(
      await screen.findByText("No blocks planned for today."),
    ).toBeVisible();
    expect(
      screen.queryByText(/Make room for what matters/),
    ).not.toBeInTheDocument();
  });
  it("allows the default action estimate and enforces the five-action limit", async () => {
    mount("/goals/new");
    await waitFor(() => expect(screen.getByLabelText("Goal")).toBeVisible());
    fireEvent.change(screen.getByLabelText("Goal"), {
      target: { value: "Read 12 books" },
    });
    fireEvent.change(screen.getByLabelText("Measure"), {
      target: { value: "Books" },
    });
    fireEvent.change(screen.getByLabelText("Unit"), {
      target: { value: "books" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByLabelText("Minutes per week")).toBeValid();
    for (let i = 0; i < 4; i++)
      fireEvent.click(screen.getByRole("button", { name: "Add action" }));
    expect(screen.getByRole("button", { name: "Add action" })).toBeDisabled();
    expect(screen.getAllByLabelText("What will you do?")).toHaveLength(5);
  });
  it("keeps coaching off without hiding the manual workflow", async () => {
    mount("/coach");
    expect(
      await screen.findByText(
        "Coaching is off. You can enable it in Settings.",
      ),
    ).toBeVisible();
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
    expect(screen.getByRole("link", { name: "Plan" })).toBeVisible();
  });
});
