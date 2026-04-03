import type { SettingsStatus, Settings, PoolToken } from "./types";
import { API_KEY, getApiBase } from "./constants";

function authHeaders(extra?: Record<string, string>): Record<string, string> {
  return { "X-API-Key": API_KEY, ...extra };
}

async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  const headers = authHeaders(
    init?.headers as Record<string, string> | undefined,
  );
  return fetch(`${getApiBase()}${path}`, { ...init, headers });
}

export async function fetchSettingsStatus(): Promise<SettingsStatus> {
  try {
    const res = await apiFetch(`/api/settings/status`);
    if (!res.ok) throw new Error("Failed to fetch settings status");
    return res.json();
  } catch (err) {
    console.warn("Failed to fetch settings status:", err);
    return { configured: false, has_claude_token: false, has_git_token: false, has_github_repo: false };
  }
}

export async function fetchSettings(): Promise<Settings> {
  const res = await apiFetch(`/api/settings`);
  if (!res.ok) throw new Error("Failed to fetch settings");
  return res.json();
}

export async function updateSettings(
  settings: Partial<Settings>
): Promise<{ ok: boolean; updated: string[] }> {
  const res = await apiFetch(`/api/settings`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settings),
  });
  if (!res.ok) throw new Error("Failed to update settings");
  return res.json();
}

export async function fetchPoolTokens(): Promise<PoolToken[]> {
  try {
    const res = await apiFetch(`/api/tokens`);
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

export async function addPoolToken(token: string): Promise<{ ok: boolean; count: number }> {
  const res = await apiFetch(`/api/tokens`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token }),
  });
  if (!res.ok) throw new Error("Failed to add token");
  return res.json();
}

export async function removePoolToken(index: number): Promise<{ ok: boolean; count: number }> {
  const res = await apiFetch(`/api/tokens/${index}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error("Failed to remove token");
  return res.json();
}
