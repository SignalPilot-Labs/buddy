/**Authenticated fetch wrapper — injects X-API-Key on every request.*/

import { getApiKey, getApiBase } from "./constants";

function authHeaders(extra?: Record<string, string>): Record<string, string> {
  return { "X-API-Key": getApiKey(), ...extra };
}

export async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  const headers = authHeaders(
    init?.headers as Record<string, string> | undefined,
  );
  return fetch(`${getApiBase()}${path}`, { ...init, headers });
}
