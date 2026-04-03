/**Shared constants for the dashboard frontend.
 *
 * Ports must match config/config.yml (source of truth for deployment values).
 */

export const API_PORT = 3401;
export const UI_PORT = 3400;

export function getApiBase(): string {
  if (typeof window === "undefined") return `http://localhost:${API_PORT}`;
  return `${window.location.protocol}//${window.location.hostname}:${API_PORT}`;
}
