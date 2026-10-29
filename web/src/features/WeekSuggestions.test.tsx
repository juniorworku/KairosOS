import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/client";
import { WeekSuggestions } from "./WeekSuggestions";
import type { FocusStats } from "../api/types";
vi.mock("../lib/hooks", () => ({
  useData: () => ({ data: { configured: true, enabled: true } }),
  useOnline: () => true,
}));
vi.mock("../api/client", () => ({ api: vi.fn() }));
afterEach(() => {
  cleanup();
  vi.mocked(api).mockReset();
});
describe("weekly recommendations", () => {
  it("requires consent and sends only the displayed week before linking to a preview", async () => {
    vi.mocked(api).mockResolvedValue({
      summary: "Keep a smaller plan",
      wins: [],
      risks: [],
      suggestions: [{ type: "planning", text: "Review one shorter block" }],
    });
    render(
      <MemoryRouter>
        <WeekSuggestions
          week="2026-10-26"
          stats={
            {
              total_minutes: 45,
              completed_sessions: 2,
              average_rating: 4,
            } as FocusStats
          }
          reflection={{
            wins: "A chapter",
            misses: "Late start",
            adjustments: "Earlier start",
          }}
        />
      </MemoryRouter>,
    );
    expect(api).not.toHaveBeenCalled();
    const button = screen.getByRole("button", { name: "Suggest adjustments" });
    expect(button).toBeDisabled();
    fireEvent.click(screen.getByRole("checkbox"));
    expect(api).not.toHaveBeenCalled();
    fireEvent.click(button);
    await waitFor(() =>
      expect(
        screen.getByRole("link", { name: "Review in plan" }),
      ).toHaveAttribute("href", "/plan?date=2026-10-26"),
    );
    const request = vi.mocked(api).mock.calls[0];
    expect(request[0]).toBe("/coach/weekly-review");
    const body = request[2] as { text: string; include_context: boolean };
    expect(body.include_context).toBe(false);
    expect(JSON.parse(body.text)).toMatchObject({
      week: "2026-10-26",
      focus: { total_minutes: 45, completed_sessions: 2, self_rating: 4 },
      reflection: { wins: "A chapter" },
    });
    expect(api).toHaveBeenCalledTimes(1);
  });
});
