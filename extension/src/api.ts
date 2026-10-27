export interface FocusState {
  active_session: { id: string; title: string } | null;
  blocklist: string[];
  ends_at: string | null;
  pause_until?: string | null;
}
export class PairingRequired extends Error {}
export interface Config {
  apiBase: string;
  token: string;
}
export async function config(): Promise<Config> {
  const data = await chrome.storage.local.get(["apiBase", "token"]);
  return {
    apiBase:
      typeof data.apiBase === "string" ? data.apiBase : "http://localhost:8000",
    token: typeof data.token === "string" ? data.token : "",
  };
}
export function safeBase(value: string): string {
  const url = new URL(value);
  if (
    url.protocol !== "https:" &&
    !(
      ["localhost", "127.0.0.1"].includes(url.hostname) &&
      url.protocol === "http:"
    )
  )
    throw new Error("Use HTTPS, or localhost for development.");
  if (
    url.username ||
    url.password ||
    url.search ||
    url.hash ||
    url.pathname !== "/"
  )
    throw new Error("Enter the server origin only.");
  return url.origin;
}
export async function request<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const { apiBase, token } = await config();
  const response = await fetch(safeBase(apiBase) + "/api/v1/ext" + path, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: "Bearer " + token } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
    signal: AbortSignal.timeout(10000),
  });
  if (response.status === 401)
    throw new PairingRequired("Pair the extension again.");
  if (!response.ok) throw new Error("Kairos could not be reached. Try again.");
  return (await response.json()) as T;
}
