/**Authenticated fetch wrapper — injects X-API-Key on every request.*/

import { API_KEY, getApiBase, API_FETCH_TIMEOUT_MS } from "./constants";

function authHeaders(extra?: Record<string, string>): Record<string, string> {
  return { "X-API-Key": API_KEY, ...extra };
}

export async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  const headers = authHeaders(
    init?.headers as Record<string, string> | undefined,
  );
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), API_FETCH_TIMEOUT_MS);
  try {
    return await fetch(`${getApiBase()}${path}`, {
      ...init,
      headers,
      signal: init?.signal ?? controller.signal,
    });
  } finally {
    clearTimeout(timeout);
  }
}
