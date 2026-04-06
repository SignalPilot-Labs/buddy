/**Authenticated fetch wrapper — injects X-API-Key on every request.*/

import { API_KEY, getApiBase } from "./constants";

function authHeaders(extra?: Record<string, string>): Record<string, string> {
  return { "X-API-Key": API_KEY, ...extra };
}

export async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  const headers = authHeaders(
    init?.headers as Record<string, string> | undefined,
  );
  return fetch(`${getApiBase()}${path}`, { ...init, headers });
}
