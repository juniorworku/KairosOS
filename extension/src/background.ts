import { request, config, PairingRequired, type FocusState } from "./api";
import { makeRules, remaining } from "./rules";
const EMPTY: FocusState = {
  active_session: null,
  blocklist: [],
  ends_at: null,
};
interface PendingEvent {
  id: string;
  kind: "pause" | "end";
  sessionId: string;
  until?: string;
  endedAt?: string;
}
interface Overrides {
  locallyEndedSession?: string;
  localPauseUntil?: string;
  localPauseSession?: string;
}
let inFlight: Promise<void> | null = null;
let updates: Promise<void> = Promise.resolve();
let flushing: Promise<void> | null = null;
async function installNow(state: FocusState): Promise<void> {
  const flags = (await chrome.storage.local.get([
    "locallyEndedSession",
    "localPauseUntil",
    "localPauseSession",
  ])) as Overrides;
  if (state.active_session?.id === flags.locallyEndedSession) state = EMPTY;
  if (
    state.active_session?.id === flags.localPauseSession &&
    flags.localPauseUntil &&
    Date.parse(flags.localPauseUntil) > Date.now()
  )
    state = { ...state, pause_until: flags.localPauseUntil };
  const seconds = remaining(state.ends_at);
  const paused =
    state.pause_until && Date.parse(state.pause_until) > Date.now();
  const existing = await chrome.declarativeNetRequest.getDynamicRules();
  const server = new URL((await config()).apiBase).hostname;
  const domains =
    seconds && !paused
      ? state.blocklist.filter(
          (domain) => server !== domain && !server.endsWith("." + domain),
        )
      : [];
  const redirect =
    domains.length > 0 &&
    (await chrome.permissions.contains({
      origins: domains.flatMap((d) => [
        "https://*." + d + "/*",
        "http://*." + d + "/*",
      ]),
    }));
  await chrome.declarativeNetRequest.updateDynamicRules({
    removeRuleIds: existing
      .filter((r) => r.id >= 1000 && r.id < 1100)
      .map((r) => r.id),
    addRules: makeRules(domains, redirect),
  });
  await chrome.storage.local.set({ focusState: state });
  if (seconds)
    await chrome.alarms.create("session-end", {
      when: Date.parse(state.ends_at!),
    });
  else await chrome.alarms.clear("session-end");
  if (paused)
    await chrome.alarms.create("pause-end", {
      when: Date.parse(state.pause_until!),
    });
  await chrome.action.setBadgeText({
    text: seconds ? String(Math.ceil(seconds / 60)) : "",
  });
  await chrome.action.setBadgeBackgroundColor({ color: "#315c43" });
}
function install(state: FocusState): Promise<void> {
  updates = updates.catch(() => undefined).then(() => installNow(state));
  return updates;
}
async function flushEvents(): Promise<void> {
  if (flushing) return flushing;
  flushing = (async () => {
    const data = await chrome.storage.local.get("pendingEvents");
    const pending = (data.pendingEvents ?? []) as PendingEvent[];
    for (const event of pending) {
      await request(
        event.kind === "end" ? "/end" : "/event",
        "POST",
        event.kind === "end"
          ? { session_id: event.sessionId, ended_at: event.endedAt }
          : {
              type: "pause",
              session_id: event.sessionId,
              pause_until: event.until,
              event_id: event.id,
            },
      );
    }
    if (pending.length) {
      const processed = new Set(pending.map((event) => event.id));
      const latest = await chrome.storage.local.get("pendingEvents");
      await chrome.storage.local.set({
        pendingEvents: ((latest.pendingEvents ?? []) as PendingEvent[]).filter(
          (event) => !processed.has(event.id),
        ),
      });
    }
  })().finally(() => {
    flushing = null;
  });
  return flushing;
}

async function localEscape(kind: "pause" | "end"): Promise<void> {
  const stored = await chrome.storage.local.get([
    "focusState",
    "pendingEvents",
  ]);
  const state = stored.focusState as FocusState | undefined;
  if (!state?.active_session) return;
  const event: PendingEvent = {
    id: crypto.randomUUID(),
    kind,
    sessionId: state.active_session.id,
  };
  if (kind === "pause") {
    event.until = new Date(Date.now() + 5 * 60000).toISOString();
    await chrome.storage.local.set({
      localPauseUntil: event.until,
      localPauseSession: event.sessionId,
    });
  } else {
    event.endedAt = new Date().toISOString();
    await chrome.storage.local.set({ locallyEndedSession: event.sessionId });
  }
  const pending = (stored.pendingEvents ?? []) as PendingEvent[];
  await chrome.storage.local.set({
    pendingEvents: [...pending, event].slice(-20),
  });
  await install(state);
  void flushEvents().catch(() => undefined);
}
async function reconcile(): Promise<void> {
  if (inFlight) return inFlight;
  inFlight = (async () => {
    try {
      await flushEvents();
      await install(await request<FocusState>("/state"));
    } catch (error) {
      if (error instanceof PairingRequired) {
        await chrome.storage.local.set({ pendingEvents: [] });
        await install(EMPTY);
        return;
      }
      const stored = await chrome.storage.local.get("focusState");
      const state = stored.focusState as FocusState | undefined;
      if (state && remaining(state.ends_at)) await install(state);
      else await install(EMPTY);
    }
  })().finally(() => {
    inFlight = null;
  });
  return inFlight;
}
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "session-end") void install(EMPTY);
  else void reconcile();
});
chrome.runtime.onStartup.addListener(() => void reconcile());
chrome.runtime.onInstalled.addListener(() => {
  void chrome.alarms.create("sync", { periodInMinutes: 0.5 });
  void reconcile();
});
chrome.runtime.onMessageExternal.addListener((_message, sender, respond) => {
  if (
    !sender.url ||
    !["http://localhost:5173", "http://127.0.0.1:5173"].includes(
      new URL(sender.url).origin,
    )
  ) {
    respond({ ok: false });
    return false;
  }
  void reconcile().then(() => respond({ ok: true }));
  return true;
});
chrome.runtime.onMessage.addListener((message: unknown, _sender, respond) => {
  const type =
    typeof message === "object" && message !== null && "type" in message
      ? message.type
      : "";
  const action =
    type === "LOCAL_PAUSE"
      ? localEscape("pause")
      : type === "LOCAL_END"
        ? localEscape("end")
        : reconcile();
  void action
    .then(() => respond({ ok: true }))
    .catch(() => respond({ ok: false }));
  return true;
});
void reconcile();
