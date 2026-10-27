import { describe, it, expect, vi } from "vitest";
import { cleanDomains, makeRules, remaining } from "./rules";
vi.stubGlobal("chrome", {
  declarativeNetRequest: {
    RuleActionType: { REDIRECT: "redirect", BLOCK: "block" },
    ResourceType: { MAIN_FRAME: "main_frame" },
  },
});
describe("focus rules", () => {
  it("rejects invalid hosts and removes duplicates", () =>
    expect(
      cleanDomains([
        "youtube.com",
        "YOUTUBE.COM",
        "bad\nsite.com",
        "localhost",
        "https://site.com",
        "work.example",
      ]),
    ).toEqual(["youtube.com", "work.example"]));
  it("reserves a fixed rule range and targets navigation only", () => {
    const rule = makeRules(["youtube.com"], false)[0];
    expect(rule.id).toBe(1000);
    expect(rule.condition.resourceTypes).toEqual(["main_frame"]);
    expect(rule.action.type).toBe("block");
  });
  it("uses a local reminder redirect only when host consent exists", () =>
    expect(
      makeRules(["example.com"], true)[0].action.redirect?.extensionPath,
    ).toBe("/blocked.html?d=example.com"));
  it("never lets a session run beyond its deadline", () => {
    expect(
      remaining("2026-10-28T00:00:00Z", Date.parse("2026-10-28T00:00:01Z")),
    ).toBe(0);
    expect(remaining(null)).toBe(0);
  });
});
