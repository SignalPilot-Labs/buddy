/**Shared constants for the dashboard frontend.
 *
 * Ports must match config/config.yml (source of truth for deployment values).
 */

export const API_PORT = 3401;
export const UI_PORT = 3400;
export const DEFAULT_API_KEY = "hell0buddy";

/** API key sent with every request. Reads from env at build time, falls back to default. */
export const API_KEY = process.env.NEXT_PUBLIC_DASHBOARD_API_KEY || DEFAULT_API_KEY;

export function getApiBase(): string {
  // Server-side: call FastAPI directly.
  // Client-side: use empty string so all /api/* requests go to the same origin
  // (Next.js rewrites proxy them to the backend).
  if (typeof window === "undefined") return `http://localhost:${API_PORT}`;
  return "";
}
