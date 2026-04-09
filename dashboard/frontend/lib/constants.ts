/**Shared constants for the dashboard frontend.
 *
 * Ports must match config/config.yml (source of truth for deployment values).
 */

export const API_PORT = 3401;
export const UI_PORT = 3400;
/** API key injected by entrypoint.sh into /public/config.js at runtime. */
declare global {
  interface Window {
    __AUTOFYN_API_KEY__?: string;
  }
}

export function getApiKey(): string {
  if (typeof window !== "undefined" && window.__AUTOFYN_API_KEY__) {
    return window.__AUTOFYN_API_KEY__;
  }
  return process.env.DASHBOARD_API_KEY || "";
}

export const API_KEY = getApiKey();

// Polling intervals (ms)
export const AGENT_HEALTH_POLL_MS = 10_000;
export const NETWORK_INFO_POLL_MS = 30_000;
export const SSE_POLL_INTERVAL_MS = 1_000;
export const SSE_FALLBACK_TIMEOUT_MS = 3_000;

// Fetch limits
export const HISTORY_FETCH_LIMIT = 500;

// Container logs
export const CONTAINER_LOGS_POLL_MS = 3000;
export const CONTAINER_LOGS_DEFAULT_TAIL = 500;

// Sidebar
export const PROMPT_LABEL_MAX_LEN = 40;

// localStorage keys
export const LOCALSTORAGE_EXTENDED_CONTEXT_KEY = "autofyn_extended_context";

// Run status sets for control bar enabling logic.
// Must match backend's accepted statuses in resume_run and inject_prompt endpoints.
import type { RunStatus } from "./types";

export const ACTIVE_STATUSES: ReadonlyArray<RunStatus> = [
  "running",
  "paused",
  "rate_limited",
];

export const RESUMABLE_STATUSES: ReadonlyArray<RunStatus> = [
  "paused",
  "completed",
  "stopped",
  "error",
];

export const INJECTABLE_STATUSES: ReadonlyArray<RunStatus> = [
  "running",
  "paused",
  "rate_limited",
  "completed",
  "stopped",
  "error",
];

export const TERMINAL_STATUSES: ReadonlySet<RunStatus> = new Set<RunStatus>([
  "completed",
  "stopped",
  "error",
  "crashed",
  "killed",
  "completed_no_changes",
]);

export function getApiBase(): string {
  // Server-side: call FastAPI directly.
  // Client-side: use empty string so all /api/* requests go to the same origin
  // (Next.js rewrites proxy them to the backend).
  if (typeof window === "undefined") return `http://localhost:${API_PORT}`;
  return "";
}
