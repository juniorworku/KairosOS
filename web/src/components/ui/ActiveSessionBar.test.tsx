import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { ActiveSessionBar } from "./ActiveSessionBar";
const state = vi.hoisted(() => ({
  session: null as null | { title: string; ends_at: string },
}));
vi.mock("../../lib/hooks", () => ({
  useData: () => ({ data: state.session }),
}));
afterEach(() => {
  cleanup();
  state.session = null;
});
function mount(path = "/goals") {
  render(
    <MemoryRouter initialEntries={[path]}>
      <ActiveSessionBar />
    </MemoryRouter>,
  );
}
describe("session continuity", () => {
  it("keeps the active action reachable while recording goal progress", () => {
    state.session = {
      title: "Read chapter two",
      ends_at: new Date(Date.now() + 60000).toISOString(),
    };
    mount();
    expect(
      screen.getByRole("complementary", { name: "Current focus session" }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Read chapter two" }),
    ).toHaveAttribute("href", "/focus");
    expect(
      screen.getByRole("link", { name: "Return to session" }),
    ).toHaveAttribute("href", "/focus");
  });
  it("offers completion rather than a negative countdown after the deadline", () => {
    state.session = {
      title: "Read chapter two",
      ends_at: new Date(Date.now() - 1000).toISOString(),
    };
    mount();
    expect(screen.getByLabelText("Session ready to finish")).toHaveTextContent(
      "Ready to finish",
    );
    expect(screen.getByRole("link", { name: "Finish session" })).toBeVisible();
  });
  it("avoids a second timer on the focus screen and hides when there is no session", () => {
    state.session = { title: "Read", ends_at: new Date().toISOString() };
    mount("/focus");
    expect(screen.queryByRole("complementary")).not.toBeInTheDocument();
    cleanup();
    state.session = null;
    mount();
    expect(screen.queryByRole("complementary")).not.toBeInTheDocument();
  });
});
