import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
function mount(path = "/today") {
  return render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
beforeEach(() => {
  vi.stubGlobal(
    "matchMedia",
    vi.fn(() => ({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  );
  localStorage.clear();
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
describe("foundation shell", () => {
  it("explains the empty state without fabricating activity", () => {
    mount();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "Make room for what matters.",
    );
    expect(
      screen.getByText("Every meaningful week starts with a goal."),
    ).toBeVisible();
  });
  it("navigates to honest milestone details", () => {
    mount();
    fireEvent.click(screen.getByRole("link", { name: "Goals" }));
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "Give your ambition a direction.",
    );
    expect(screen.getByText("Coming in a later milestone")).toBeVisible();
  });
  it("saves appearance and reports unavailable API", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    mount("/settings");
    fireEvent.change(screen.getByLabelText("Color theme"), {
      target: { value: "dark" },
    });
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(localStorage.getItem("kairos.theme")).toBe("dark");
    expect(await screen.findByText("API is not running")).toBeVisible();
  });
});
