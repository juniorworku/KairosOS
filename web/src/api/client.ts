import { openDB } from "idb";
import { copy as c } from "../copy/en";
import type { User, FocusSession } from "./types";
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}
const db = () =>
  openDB("kairos-offline", 1, {
    upgrade(database) {
      database.createObjectStore("reads");
      database.createObjectStore("queue", { keyPath: "id" });
    },
  });
let accountId = "";
let csrf = "";
export function setAccount(id: string) {
  accountId = id;
}
export async function rememberUser(user: User) {
  accountId = user.id;
  await (await db()).put("reads", user, "profile");
}
export async function offlineUser(): Promise<User | undefined> {
  return (await db()).get("reads", "profile");
}
export async function clearPrivateData() {
  accountId = "";
  csrf = "";
  const database = await db();
  await Promise.all([database.clear("reads"), database.clear("queue")]);
}
export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  const requestAccount = accountId;
  const key = `${requestAccount}:${path}`;
  const cacheable =
    method === "GET" &&
    accountId &&
    /^\/(goals|plan\/week|focus\/(stats|active|sessions)|trajectory|reflection|busy|seasons|agenda(?:\?|$)|tasks(?:\/|\?|$)|events(?:\/|\?|$))/.test(
      path,
    );
  if (!navigator.onLine && cacheable) {
    const cached = (await (await db()).get("reads", key)) as T | undefined;
    if (cached !== undefined) return cached;
  }
  if (method !== "GET" && !csrf) {
    const response = await fetch("/api/v1/auth/csrf", {
      credentials: "include",
    });
    if (!response.ok)
      throw new ApiError(response.status, "csrf", "Sign in again to continue.");
    const data = (await response.json()) as { csrf_token: string };
    csrf = data.csrf_token;
  }
  let response: Response;
  try {
    response = await fetch(`/api/v1${path}`, {
      method,
      signal,
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...(method !== "GET" ? { "X-CSRF-Token": csrf } : {}),
      },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
  } catch (error) {
    if (signal?.aborted) throw error;
    if (cacheable) {
      const cached = (await (await db()).get("reads", key)) as T | undefined;
      if (cached !== undefined) return cached;
    }
    throw error;
  }
  if (!response.ok) {
    const data = (await response.json().catch(() => ({}))) as {
      error?: { code?: string; message?: string; resets_at?: string };
      detail?: string | { msg: string }[];
    };
    let message = data.error?.message;
    if (data.error?.code === "quota_exceeded" && data.error.resets_at) {
      const reset = new Date(data.error.resets_at);
      if (!Number.isNaN(reset.getTime()))
        message = c.coach.quotaReset(
          reset.toLocaleString(undefined, {
            month: "short",
            day: "numeric",
            hour: "numeric",
            minute: "2-digit",
          }),
        );
    }
    if (!message)
      message =
        typeof data.detail === "string"
          ? data.detail
          : Array.isArray(data.detail)
            ? data.detail.map((d) => d.msg).join(". ")
            : `Request failed (${response.status}).`;
    throw new ApiError(
      response.status,
      data.error?.code || "request_failed",
      message,
    );
  }
  if (response.status === 204) return undefined as T;
  const result = (await response.json()) as T;
  if (path === "/calendar/details" && method === "DELETE" && requestAccount) {
    const database = await db();
    const transaction = database.transaction("reads", "readwrite");
    for (const savedKey of await transaction.store.getAllKeys()) {
      if (
        typeof savedKey === "string" &&
        savedKey.startsWith(`${requestAccount}:/agenda?`)
      )
        await transaction.store.delete(savedKey);
    }
    await transaction.done;
  }
  if (path === "/auth/magic/verify") csrf = "";
  if (cacheable && !signal?.aborted && accountId === requestAccount)
    await (await db()).put("reads", result, key);
  if (method !== "GET" && /^\/focus\/(start|[^/]+\/end)$/.test(path))
    syncExtension();
  return result;
}
interface Queued {
  id: string;
  account: string;
  path: string;
  body: unknown;
  queued_at: number;
  failure?: string;
}
export async function queueWrite(path: string, body: Record<string, unknown>) {
  const id = crypto.randomUUID();
  const database = await db();
  const transaction = database.transaction(["queue", "reads"], "readwrite");
  const sequence = Math.max(
    Date.now(),
    Number(
      (await transaction.objectStore("reads").get("queue-sequence")) || 0,
    ) + 1,
  );
  await transaction.objectStore("reads").put(sequence, "queue-sequence");
  await transaction.objectStore("queue").put({
    id,
    account: accountId,
    path,
    body: { ...body, client_event_id: id },
    queued_at: sequence,
  } satisfies Queued);
  if (/^\/focus\/[^/]+\/end$/.test(path)) {
    const store = transaction.objectStore("reads");
    const active = (await store.get(`${accountId}:/focus/active`)) as
      FocusSession | null | undefined;
    if (active?.id === path.split("/")[2]) {
      await store.put(null, `${accountId}:/focus/active`);
    }
  }
  await transaction.done;
}
export async function replayQueue() {
  if (!navigator.onLine || !accountId) return;
  const database = await db();
  const queued = ((await database.getAll("queue")) as Queued[]).sort(
    (a, b) => (a.queued_at || 0) - (b.queued_at || 0),
  );
  const failures: string[] = [];
  for (const item of queued) {
    if (item.account !== accountId) continue;
    if (item.failure) {
      failures.push(item.failure);
      continue;
    }
    try {
      await api(item.path, "POST", item.body);
      await database.delete("queue", item.id);
    } catch (error) {
      if (
        error instanceof ApiError &&
        error.status < 500 &&
        error.status !== 401 &&
        error.status !== 403
      ) {
        item.failure = error.message;
        await database.put("queue", item);
        failures.push(error.message);
        continue;
      }
      throw error;
    }
  }
  if (failures.length)
    throw new Error(
      `${failures.length} offline update(s) could not sync. ${failures[0]}`,
    );
}
export async function resetFailedQueue() {
  const database = await db();
  for (const item of (await database.getAll("queue")) as Queued[]) {
    if (item.account === accountId && item.failure) {
      delete item.failure;
      await database.put("queue", item);
    }
  }
}
export async function discardFailedQueue() {
  const database = await db();
  for (const item of (await database.getAll("queue")) as Queued[]) {
    if (item.account === accountId && item.failure)
      await database.delete("queue", item.id);
  }
}
export async function readDraft<T>(key: string): Promise<T | undefined> {
  return (await db()).get("reads", `${accountId}:draft:${key}`);
}
export async function saveDraft(key: string, value: unknown) {
  await (await db()).put("reads", value, `${accountId}:draft:${key}`);
}
export async function deleteDraft(key: string) {
  await (await db()).delete("reads", `${accountId}:draft:${key}`);
}
export async function streamRequest(
  path: string,
  body: unknown,
  signal?: AbortSignal,
) {
  if (!csrf) {
    const data = await api<{ csrf_token: string }>("/auth/csrf");
    csrf = data.csrf_token;
  }
  const response = await fetch(`/api/v1${path}`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
    body: JSON.stringify(body),
    signal,
  });
  if (!response.ok) {
    const data = (await response.json()) as {
      error?: { message?: string };
      detail?: { message?: string } | string;
    };
    throw new Error(
      data.error?.message ||
        (typeof data.detail === "string"
          ? data.detail
          : data.detail?.message) ||
        "Could not get a reply.",
    );
  }
  return response;
}

interface ChromeBridge {
  runtime?: {
    lastError?: { message?: string };
    sendMessage: (
      id: string,
      message: { type: string },
      callback: () => void,
    ) => void;
  };
}
export function syncExtension() {
  const id = import.meta.env.VITE_EXTENSION_ID as string | undefined;
  const bridge = (window as Window & { chrome?: ChromeBridge }).chrome?.runtime;
  if (id && /^[a-p]{32}$/.test(id) && bridge) {
    try {
      bridge.sendMessage(id, { type: "SESSION_CHANGED" }, () => {
        void bridge.lastError;
      });
    } catch {
      /* Polling and local expiry remain available. */
    }
  }
}
