/**Authenticated fetch wrapper.
 *
 * The API key is no longer attached here. The browser calls the same-origin
 * Next.js proxy (app/api/[...path]/route.ts), which attaches it server-side.
 */

import { API_FETCH_TIMEOUT_MS } from "./constants";

export async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), API_FETCH_TIMEOUT_MS);
  try {
    return await fetch(path, {
      ...init,
      signal: init?.signal ?? controller.signal,
    });
  } finally {
    clearTimeout(timeout);
  }
}
