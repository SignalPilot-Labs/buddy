/**Shared constants for the dashboard frontend.
 *
 * Ports must match config/config.yml (source of truth for deployment values).
 */

export const API_PORT = 3401;
export const UI_PORT = 3400;

export function getApiBase(): string {
  // Server-side: call FastAPI directly.
  // Client-side: use empty string so all /api/* requests go to the same origin
  // (Next.js rewrites proxy them to the backend). This is critical for tunnel
  // access where only port 3400 is exposed.
  if (typeof window === "undefined") return `http://localhost:${API_PORT}`;
  return "";
}
