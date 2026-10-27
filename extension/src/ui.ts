import { config, request, safeBase, type FocusState } from "./api";
import { cleanDomains, remaining } from "./rules";
function element<T extends HTMLElement>(id: string): T {
  const value = document.getElementById(id);
  if (!value) throw new Error("Missing interface element");
  return value as T;
}
function message(value: string): void {
  element("message").textContent = value;
}
function timer(state: FocusState): void {
  const seconds = remaining(state.ends_at);
  element("timer").textContent =
    String(Math.floor(seconds / 60)).padStart(2, "0") +
    ":" +
    String(seconds % 60).padStart(2, "0");
  element("session").textContent =
    state.active_session?.title ?? "No active session";
}
async function refresh(): Promise<void> {
  const stored = await chrome.storage.local.get("focusState");
  const state = stored.focusState as FocusState | undefined;
  timer(state ?? { active_session: null, blocklist: [], ends_at: null });
  window.setTimeout(() => void refresh(), 1000);
}

async function start(): Promise<void> {
  const page = document.body.dataset.page;
  if (page === "options") {
    const stored = await config();
    element<HTMLInputElement>("server").value = stored.apiBase;
    element<HTMLFormElement>("settings").onsubmit = (event) => {
      event.preventDefault();
      void (async () => {
        try {
          const base = safeBase(element<HTMLInputElement>("server").value);
          await chrome.permissions.request({ origins: [base + "/*"] });
          await chrome.storage.local.set({ apiBase: base });
          message("Server saved.");
        } catch (e) {
          message(e instanceof Error ? e.message : "Could not save server");
        }
      })();
    };
    return;
  }
  if (page === "blocked") {
    const domain = new URLSearchParams(location.search).get("d") ?? "";
    if (cleanDomains([domain]).length)
      void request("/event", "POST", { type: "blocked", domain }).catch(
        () => undefined,
      );
    element("back").onclick = () => {
      if (history.length > 1) history.back();
      else window.close();
    };
  }
  const pair = document.getElementById("pair");
  if (pair)
    pair.onsubmit = (event) => {
      event.preventDefault();
      void (async () => {
        try {
          const data = await request<{ token: string }>(
            "/pair/redeem",
            "POST",
            { code: element<HTMLInputElement>("code").value, label: "Chrome" },
          );
          await chrome.storage.local.set({ token: data.token });
          message("Paired.");
          await chrome.runtime.sendMessage({ type: "SYNC" });
          void refresh();
        } catch (e) {
          message(e instanceof Error ? e.message : "Could not pair");
        }
      })();
    };
  element("end").onclick = () => {
    void chrome.runtime
      .sendMessage({ type: "LOCAL_END" })
      .then(() => {
        element("session").textContent = "Session ended";
        element("timer").textContent = "00:00";
        message("Session ended on this browser.");
      })
      .catch((e) => message(String(e)));
  };
  element("pause").onclick = () => {
    void chrome.runtime
      .sendMessage({ type: "LOCAL_PAUSE" })
      .then(() => message("Sites unblocked for five minutes."))
      .catch((e) => message(String(e)));
  };
  const allow = document.getElementById("allow");
  if (allow)
    allow.onclick = () => {
      void chrome.permissions
        .request({ origins: ["https://*/*", "http://*/*"] })
        .then(() => chrome.runtime.sendMessage({ type: "SYNC" }));
    };
  void chrome.runtime.sendMessage({ type: "SYNC" }).catch(() => undefined);
  void refresh();
}
void start();
