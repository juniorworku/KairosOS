import "fake-indexeddb/auto";
import {
  render,
  screen,
  fireEvent,
  cleanup,
  waitFor,
  within,
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
  it("defaults to warm light tokens and preserves an explicit dark preference", async () => {
    const first = mount();
    await waitFor(() =>
      expect(document.documentElement).toHaveAttribute("data-theme", "light"),
    );
    expect(document.documentElement).not.toHaveClass("dark");
    first.unmount();
    localStorage.setItem("kairos.theme", "dark");
    mount();
    await waitFor(() =>
      expect(document.documentElement).toHaveAttribute("data-theme", "dark"),
    );
    expect(document.documentElement).toHaveClass("dark");
    expect(localStorage.getItem("kairos.theme")).toBe("dark");
  });
  it("switches light and dark from the shell and persists the choice after remount", async () => {
    const first = mount();
    const sidebar = document.querySelector(".sidebar")! as HTMLElement;
    fireEvent.click(
      within(sidebar).getByRole("button", { name: "Dark theme" }),
    );
    await waitFor(() =>
      expect(document.documentElement).toHaveAttribute("data-theme", "dark"),
    );
    expect(
      within(sidebar).getByRole("button", { name: "Dark theme" }),
    ).toHaveAttribute("aria-pressed", "true");
    first.unmount();
    mount();
    expect(document.documentElement).toHaveClass("dark");
    fireEvent.click(
      within(document.querySelector(".sidebar")! as HTMLElement).getByRole(
        "button",
        { name: "Light theme" },
      ),
    );
    await waitFor(() =>
      expect(document.documentElement).toHaveAttribute("data-theme", "light"),
    );
    expect(localStorage.getItem("kairos.theme")).toBe("light");
  });
  it("traps mobile navigation focus and restores the trigger after Escape", async () => {
    mount();
    const trigger = screen.getByRole("button", { name: "Open navigation" });
    fireEvent.click(trigger);
    const drawer = await screen.findByRole("dialog", { name: "Kairos" });
    const close = within(drawer).getByRole("button", {
      name: "Close navigation",
    });
    const last = within(drawer).getByRole("button", { name: "Sign out" });
    last.focus();
    fireEvent.keyDown(drawer, { key: "Tab" });
    expect(close).toHaveFocus();
    fireEvent.keyDown(drawer, { key: "Escape", code: "Escape" });
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
    );
    expect(trigger).toHaveFocus();
  });
  it("hides user administration and redirects its former route", async () => {
    mount("/admin");
    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent(
      "Today",
    );
    expect(
      screen.queryByRole("link", { name: /^Users$/ }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Invites" }),
    ).not.toBeInTheDocument();
  });
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
