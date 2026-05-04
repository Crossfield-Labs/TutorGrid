const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";
const DEFAULT_WS_URL = "ws://127.0.0.1:3210/ws/orchestrator";
const DEFAULT_WEB_HOME_ROUTE = "/landing";

function trimTrailingSlash(value: string): string {
  return value.replace(/\/+$/, "");
}

function normalizeRoute(value: string | undefined): string {
  const raw = (value || "").trim();
  if (!raw) return DEFAULT_WEB_HOME_ROUTE;
  return raw.startsWith("/") ? raw : `/${raw}`;
}

function deriveWsUrl(apiBaseUrl: string): string {
  try {
    const url = new URL(apiBaseUrl);
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    url.pathname = "/ws/orchestrator";
    url.search = "";
    url.hash = "";
    return url.toString();
  } catch {
    return DEFAULT_WS_URL;
  }
}

const rawApiBaseUrl = trimTrailingSlash(
  import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE_URL
);

const rawWsUrl = (import.meta.env.VITE_WS_URL || "").trim();

export const API_BASE_URL = rawApiBaseUrl || DEFAULT_API_BASE_URL;
export const WS_URL = rawWsUrl || deriveWsUrl(API_BASE_URL);
export const CHAT_SSE_ENDPOINT = `${API_BASE_URL}/api/chat/stream`;
export const WEB_DEFAULT_HOME_ROUTE = normalizeRoute(
  import.meta.env.VITE_DEFAULT_HOME_ROUTE
);

