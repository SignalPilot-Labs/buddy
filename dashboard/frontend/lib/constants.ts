/**Shared constants for the dashboard frontend.
 *
 * Ports must match config/config.yml (source of truth for deployment values).
 */

export const API_PORT = 3401;
export const UI_PORT = 3400;
/** API key injected by entrypoint.sh into /public/config.js at runtime. */
declare global {
  interface Window { __BUDDY_API_KEY__?: string; }
}

export function getApiKey(): string {
  if (typeof window !== "undefined" && window.__BUDDY_API_KEY__) {
    return window.__BUDDY_API_KEY__;
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

export function getApiBase(): string {
  // Server-side: call FastAPI directly.
  // Client-side: use empty string so all /api/* requests go to the same origin
  // (Next.js rewrites proxy them to the backend).
  if (typeof window === "undefined") return `http://localhost:${API_PORT}`;
  return "";
}

// Error status fallback messages for runs without an error_message field
export const ERROR_STATUS_FALLBACK_MESSAGES: Record<"error" | "crashed" | "killed", string> = {
  error: "Run ended with an error — check the event feed for details.",
  crashed: "Run crashed unexpectedly — the agent process may have exited.",
  killed: "Run was force-killed.",
};

// Audit event types that represent fatal/severe failures
export const FATAL_AUDIT_EVENT_TYPES: readonly string[] = [
  "fatal_error",
  "push_failed",
  "pr_failed",
  "subagent_timeout",
  "subagent_stuck",
  "killed",
];

// Warning message for completed runs with zero tokens consumed
export const ZERO_TOKEN_WARNING_MSG =
  "This run completed with 0 tokens. This may indicate an authentication failure with the Claude API.";

// Connectivity error messages
export const AGENT_UNREACHABLE_MSG = "Agent unreachable — check Docker";
export const API_FETCH_ERROR_MSG = "Could not reach the dashboard API. Retrying…";
