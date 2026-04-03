/**Shared constants for the dashboard frontend.
 *
 * Ports must match config/config.yml (source of truth for deployment values).
 */

export const API_PORT = 3401;
export const UI_PORT = 3400;

// API fetch limits
export const DEFAULT_FETCH_LIMIT = 500;

// Run start defaults
export const DEFAULT_BUDGET_USD = 0;
export const DEFAULT_DURATION_MINUTES = 0;
export const DEFAULT_BASE_BRANCH = "main";

// Responsive breakpoints (px)
export const MOBILE_BREAKPOINT = 640;

// SSE / polling intervals (ms)
export const SSE_FALLBACK_TIMEOUT_MS = 3000;
export const SSE_POLL_INTERVAL_MS = 1000;

// Tunnel polling intervals (ms)
export const TUNNEL_POLL_INTERVAL_MS = 10_000;
export const TUNNEL_RAPID_POLLS_MS = [1000, 3000, 5000];

// UI feedback durations (ms)
export const COPY_FEEDBACK_DURATION_MS = 2000;

export function getApiBase(): string {
  // Server-side: call FastAPI directly.
  // Client-side: use empty string so all /api/* requests go to the same origin
  // (Next.js rewrites proxy them to the backend). This is critical for tunnel
  // access where only port 3400 is exposed.
  if (typeof window === "undefined") return `http://localhost:${API_PORT}`;
  return "";
}
