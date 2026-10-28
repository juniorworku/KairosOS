import "fake-indexeddb/auto";
import { openDB } from "idb";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  api,
  clearPrivateData,
  discardFailedQueue,
  offlineUser,
  queueWrite,
  readDraft,
  rememberUser,
  replayQueue,
  resetFailedQueue,
  saveDraft,
  setAccount,
} from "./client";
import type { User } from "./types";

interface StoredWrite {
  id: string;
  account: string;
  path: string;
  body: { client_event_id: string; metric_value?: number };
  queued_at: number;
  failure?: string;
}

const fetchMock = vi.fn<typeof fetch>();
function online(value: boolean) {
  Object.defineProperty(navigator, "onLine", { configurable: true, value });
}
function json(value: unknown, status = 200) {
  return new Response(JSON.stringify(value), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
async function queued(): Promise<StoredWrite[]> {
  const database = await openDB("kairos-offline", 1);
  try {
    return (await database.getAll("queue")) as StoredWrite[];
  } finally {
    database.close();
  }
}
function profile(id: string): User {
  const value = {
    id,
    email: `${id}@example.test`,
    name: id,
    avatar_url: null,
    timezone: "UTC",
    work_days: [0, 1, 2, 3, 4],
    work_start: "09:00",
    work_end: "17:00",
    daily_max_focus_minutes: 240,
    energy_peak: "morning" as const,
    role: "user" as const,
    plan_id: "plan",
    ai_enabled: true,
    disabled_at: null,
    onboarding_completed_at: null,
  };
  return value;
}
function writes() {
  return fetchMock.mock.calls.filter(([, init]) => init?.method === "POST");
}
function requestBody(init: RequestInit | undefined) {
  return JSON.parse(String(init?.body)) as Record<string, unknown>;
}

beforeEach(async () => {
  vi.restoreAllMocks();
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  online(true);
  await clearPrivateData();
  setAccount("account-a");
});
afterEach(async () => {
  vi.restoreAllMocks();
  await clearPrivateData();
  online(true);
  vi.unstubAllGlobals();
});

describe("durable offline updates", () => {
  it("replays in creation order rather than random UUID key order", async () => {
    vi.spyOn(crypto, "randomUUID")
      .mockReturnValueOnce("ffffffff-ffff-4fff-afff-ffffffffffff")
      .mockReturnValueOnce("00000000-0000-4000-a000-000000000000");
    const clock = vi.spyOn(Date, "now").mockReturnValue(1000);
    await queueWrite("/goals/goal/checkins", { metric_value: 10 });
    clock.mockReturnValue(2000);
    await queueWrite("/goals/goal/checkins", { metric_value: 20 });
    const original = await queued();
    expect(original).toHaveLength(2);
    fetchMock.mockImplementation(async (input) =>
      json(String(input).endsWith("/auth/csrf") ? { csrf_token: "csrf" } : {}),
    );
    await replayQueue();
    expect(writes().map(([, init]) => requestBody(init).metric_value)).toEqual([
      10, 20,
    ]);
    expect(
      writes().map(([, init]) => requestBody(init).client_event_id),
    ).toEqual([
      "ffffffff-ffff-4fff-afff-ffffffffffff",
      "00000000-0000-4000-a000-000000000000",
    ]);
    expect(await queued()).toEqual([]);
  });

  it("retains the event ID after a transient failure, allowing idempotent retry", async () => {
    await queueWrite("/goals/goal/checkins", { metric_value: 42 });
    const [original] = await queued();
    let fail = true;
    fetchMock.mockImplementation(async (input) => {
      if (String(input).endsWith("/auth/csrf"))
        return json({ csrf_token: "csrf" });
      return fail
        ? json({ error: { message: "Try again", code: "unavailable" } }, 503)
        : json({ id: "saved" });
    });
    await expect(replayQueue()).rejects.toThrow("Try again");
    expect((await queued())[0].id).toBe(original.id);
    fail = false;
    await replayQueue();
    expect(
      writes().map(([, init]) => requestBody(init).client_event_id),
    ).toEqual([original.id, original.id]);
    expect(await queued()).toEqual([]);
  });

  it("quarantines a missing goal while delivering subsequent valid updates", async () => {
    const clock = vi.spyOn(Date, "now").mockReturnValue(1000);
    await queueWrite("/goals/deleted/checkins", { metric_value: 10 });
    clock.mockReturnValue(2000);
    await queueWrite("/goals/present/checkins", { metric_value: 20 });
    fetchMock.mockImplementation(async (input) => {
      if (String(input).endsWith("/auth/csrf"))
        return json({ csrf_token: "csrf" });
      return String(input).includes("/deleted/")
        ? json({ error: { code: "not_found", message: "Goal removed" } }, 404)
        : json({ id: "saved" });
    });
    await expect(replayQueue()).rejects.toThrow("Goal removed");
    expect(writes()).toHaveLength(2);
    const remaining = await queued();
    expect(remaining).toHaveLength(1);
    expect(remaining[0].failure).toBe("Goal removed");
    fetchMock.mockClear();
    await expect(replayQueue()).rejects.toThrow("Goal removed");
    expect(writes()).toHaveLength(0);
    await resetFailedQueue();
    expect((await queued())[0].failure).toBeUndefined();
    fetchMock.mockImplementation(async () => json({ id: "restored" }));
    await replayQueue();
    expect(await queued()).toEqual([]);
  });

  it("retries and discards only the current account's failed updates", async () => {
    await queueWrite("/goals/a/checkins", { metric_value: 1 });
    setAccount("account-b");
    await queueWrite("/goals/b/checkins", { metric_value: 2 });
    fetchMock.mockImplementation(async (input) =>
      String(input).endsWith("/auth/csrf")
        ? json({ csrf_token: "csrf" })
        : json({ error: { message: "Removed", code: "not_found" } }, 404),
    );
    await expect(replayQueue()).rejects.toThrow("Removed");
    expect(writes().map(([input]) => String(input))).toEqual([
      "/api/v1/goals/b/checkins",
    ]);
    setAccount("account-a");
    await discardFailedQueue();
    expect(await queued()).toHaveLength(2);
    setAccount("account-b");
    await discardFailedQueue();
    const remaining = await queued();
    expect(remaining).toHaveLength(1);
    expect(remaining[0].account).toBe("account-a");
  });

  it("clears the persisted active timer when its end is queued", async () => {
    fetchMock.mockImplementation(async () =>
      json({ id: "session", started_at: "2026-10-28T09:00:00Z" }),
    );
    await api("/focus/active");
    online(false);
    await queueWrite("/focus/session/end", {
      ended_at: "2026-10-28T09:05:00Z",
      self_rating: 4,
    });
    fetchMock.mockClear();
    await expect(api("/focus/active")).resolves.toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
    expect(await queued()).toHaveLength(1);
  });
});

describe("private offline reads", () => {
  it("purges cached Google agenda details when details are turned off, preserving tasks", async () => {
    const path = "/agenda?start=2026-10-26&end=2026-11-02";
    fetchMock.mockImplementation(async () =>
      json([{ title: "Private Google title" }]),
    );
    await api(path);
    await api("/tasks");
    fetchMock.mockImplementation(async (input) =>
      json(
        String(input).endsWith("/auth/csrf")
          ? { csrf_token: "csrf" }
          : { status: "disabled" },
      ),
    );
    await api("/calendar/details", "DELETE");
    online(false);
    fetchMock.mockRejectedValue(new TypeError("Offline"));
    await expect(api(path)).rejects.toThrow("Offline");
    expect(await api("/tasks")).toEqual([{ title: "Private Google title" }]);
  });

  it("keeps agenda notes and tasks scoped to the account and clears them on sign out", async () => {
    const paths = [
      "/agenda?start=2026-10-26&end=2026-11-02",
      "/tasks",
      "/events/event-a",
    ];
    fetchMock.mockImplementation(async () =>
      json([{ title: "Private event", notes: "Private notes" }]),
    );
    for (const path of paths) await api(path);
    online(false);
    fetchMock.mockRejectedValue(new TypeError("Offline"));
    for (const path of paths)
      expect(await api(path)).toEqual([
        { title: "Private event", notes: "Private notes" },
      ]);
    setAccount("account-b");
    for (const path of paths)
      await expect(api(path)).rejects.toThrow("Offline");
    setAccount("account-a");
    await clearPrivateData();
    setAccount("account-a");
    for (const path of paths)
      await expect(api(path)).rejects.toThrow("Offline");
  });

  it("keeps cached goals and wizard drafts separate for each account", async () => {
    fetchMock.mockImplementation(async () => json([{ title: "Private A" }]));
    await api("/goals");
    await saveDraft("new-goal", { title: "Draft A" });
    setAccount("account-b");
    fetchMock.mockImplementation(async () => json([{ title: "Private B" }]));
    await api("/goals");
    await saveDraft("new-goal", { title: "Draft B" });
    online(false);
    fetchMock.mockImplementation(async () => {
      throw new TypeError("Offline");
    });
    await expect(api("/goals")).resolves.toEqual([{ title: "Private B" }]);
    await expect(readDraft("new-goal")).resolves.toEqual({ title: "Draft B" });
    setAccount("account-a");
    await expect(api("/goals")).resolves.toEqual([{ title: "Private A" }]);
    await expect(readDraft("new-goal")).resolves.toEqual({ title: "Draft A" });
  });

  it("does not fall back to another account's cached goals", async () => {
    fetchMock.mockImplementation(async () => json([{ title: "Private A" }]));
    await api("/goals");
    setAccount("account-b");
    online(false);
    fetchMock.mockImplementation(async () => {
      throw new TypeError("Offline");
    });
    await expect(api("/goals")).rejects.toThrow("Offline");
  });

  it("clears profile, cached goals, drafts and queued updates on local logout cleanup", async () => {
    await rememberUser(profile("account-a"));
    fetchMock.mockImplementation(async () => json([{ title: "Private A" }]));
    await api("/goals");
    await saveDraft("new-goal", { title: "Unfinished" });
    await queueWrite("/goals/goal/checkins", { metric_value: 5 });
    await clearPrivateData();
    setAccount("account-a");
    online(false);
    fetchMock.mockImplementation(async () => {
      throw new TypeError("Offline");
    });
    await expect(offlineUser()).resolves.toBeUndefined();
    await expect(readDraft("new-goal")).resolves.toBeUndefined();
    await expect(api("/goals")).rejects.toThrow("Offline");
    expect(await queued()).toEqual([]);
  });

  it("never caches authentication request responses", async () => {
    fetchMock.mockImplementation(async () =>
      json({ csrf_token: "sensitive", google_enabled: true }),
    );
    await api("/auth/csrf");
    await api("/auth/config");
    fetchMock.mockClear();
    online(false);
    fetchMock.mockImplementation(async () => {
      throw new TypeError("Offline");
    });
    await expect(api("/auth/csrf")).rejects.toThrow("Offline");
    await expect(api("/auth/config")).rejects.toThrow("Offline");
    expect(fetchMock).toHaveBeenCalledTimes(2);
    const database = await openDB("kairos-offline", 1);
    try {
      expect(await database.getAllKeys("reads")).toEqual([]);
    } finally {
      database.close();
    }
  });
});
