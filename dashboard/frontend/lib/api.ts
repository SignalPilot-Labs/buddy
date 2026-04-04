import type { Run, ToolCall, AuditEvent, RepoInfo } from "./types";
import { API_KEY, getApiBase, HISTORY_FETCH_LIMIT, UI_PORT } from "./constants";

import { apiFetch } from "./fetch";

export async function fetchRuns(repo?: string): Promise<Run[]> {
  const params = repo ? `?repo=${encodeURIComponent(repo)}` : "";
  const res = await apiFetch(`/api/runs${params}`);
  if (!res.ok) throw new Error("Failed to fetch runs");
  return res.json();
}

export async function fetchRepos(): Promise<RepoInfo[]> {
  try {
    const res = await apiFetch(`/api/repos`);
    if (!res.ok) return [];
    return res.json();
  } catch (err) {
    console.warn("Failed to fetch repos:", err);
    return [];
  }
}

export async function setActiveRepo(repo: string): Promise<{ ok: boolean }> {
  const res = await apiFetch(`/api/repos/active`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ repo }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function fetchRun(id: string): Promise<Run> {
  const res = await apiFetch(`/api/runs/${id}`);
  if (!res.ok) throw new Error("Failed to fetch run");
  return res.json();
}

export async function fetchToolCalls(
  runId: string,
  limit = HISTORY_FETCH_LIMIT
): Promise<ToolCall[]> {
  const res = await apiFetch(`/api/runs/${runId}/tools?limit=${limit}`);
  if (!res.ok) throw new Error("Failed to fetch tool calls");
  return res.json();
}

export async function fetchAuditLog(
  runId: string,
  limit = HISTORY_FETCH_LIMIT
): Promise<AuditEvent[]> {
  const res = await apiFetch(`/api/runs/${runId}/audit?limit=${limit}`);
  if (!res.ok) throw new Error("Failed to fetch audit log");
  return res.json();
}

export async function sendSignal(
  runId: string,
  signal: "pause" | "resume" | "stop",
  payload?: string
): Promise<{ ok: boolean }> {
  const res = await apiFetch(`/api/runs/${runId}/${signal}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ payload: payload || null }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function injectPrompt(
  runId: string,
  prompt: string
): Promise<{ ok: boolean }> {
  const res = await apiFetch(`/api/runs/${runId}/inject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ payload: prompt }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export function createSSE(runId: string): EventSource {
  return new EventSource(
    `${getApiBase()}/api/stream/${runId}?api_key=${encodeURIComponent(API_KEY)}`,
  );
}

export interface PollResult {
  tool_calls: ToolCall[];
  audit_events: AuditEvent[];
}

export async function pollEvents(
  runId: string,
  afterTool: number,
  afterAudit: number,
): Promise<PollResult> {
  const res = await apiFetch(
    `/api/poll/${runId}?after_tool=${afterTool}&after_audit=${afterAudit}`,
  );
  if (!res.ok) throw new Error("Failed to poll events");
  return res.json();
}

export interface AgentHealth {
  status: "idle" | "running" | "unreachable";
  current_run_id: string | null;
  elapsed_minutes?: number | null;
  time_remaining?: string | null;
  session_unlocked?: boolean | null;
  error?: string;
}

export async function fetchAgentHealth(): Promise<AgentHealth> {
  try {
    const res = await apiFetch(`/api/agent/health`);
    if (!res.ok) return { status: "unreachable", current_run_id: null };
    return res.json();
  } catch (err) {
    console.warn("Agent health check failed:", err);
    return { status: "unreachable", current_run_id: null };
  }
}

export async function startRun(
  prompt?: string,
  maxBudgetUsd = 0,
  durationMinutes = 0,
  baseBranch = "main"
): Promise<{ ok: boolean; run_id?: string }> {
  const res = await apiFetch(`/api/agent/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      prompt: prompt || null,
      max_budget_usd: maxBudgetUsd,
      duration_minutes: durationMinutes,
      base_branch: baseBranch,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function resumeRun(
  runId: string,
  maxBudgetUsd = 0
): Promise<{ ok: boolean; run_id?: string }> {
  const res = await apiFetch(`/api/agent/resume`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ run_id: runId, max_budget_usd: maxBudgetUsd }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function stopAgentInstant(): Promise<{ ok: boolean }> {
  const res = await apiFetch(`/api/agent/stop`, { method: "POST" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function killAgent(): Promise<{ ok: boolean }> {
  const res = await apiFetch(`/api/agent/kill`, { method: "POST" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function unlockSession(
  runId: string
): Promise<{ ok: boolean }> {
  const res = await apiFetch(`/api/runs/${runId}/unlock`, {
    method: "POST",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export interface DiffFile {
  path: string;
  added: number;
  removed: number;
  status: "added" | "modified" | "deleted" | "renamed";
}

export interface DiffStats {
  files: DiffFile[];
  total_files: number;
  total_added: number;
  total_removed: number;
  source: "stored" | "live" | "agent" | "unavailable";
}

export async function fetchRunDiff(runId: string): Promise<DiffStats> {
  try {
    const res = await apiFetch(`/api/runs/${runId}/diff`);
    if (!res.ok) return { files: [], total_files: 0, total_added: 0, total_removed: 0, source: "unavailable" };
    return res.json();
  } catch (err) {
    console.warn("Failed to fetch run diff:", err);
    return { files: [], total_files: 0, total_added: 0, total_removed: 0, source: "unavailable" };
  }
}

// ── Network ──────────────────────────────────────────────────────────────────

export interface NetworkInfo {
  url: string | null;
  ip: string | null;
  port: number;
}

export async function fetchNetworkInfo(): Promise<NetworkInfo> {
  try {
    const res = await apiFetch(`/api/network-info`);
    if (!res.ok) return { url: null, ip: null, port: UI_PORT };
    return res.json();
  } catch {
    return { url: null, ip: null, port: UI_PORT };
  }
}

// ── Branches ─────────────────────────────────────────────────────────────────

export async function fetchBranches(): Promise<string[]> {
  try {
    const res = await apiFetch(`/api/agent/branches`);
    if (!res.ok) return ["main"];
    return res.json();
  } catch (err) {
    console.warn("Failed to fetch branches:", err);
    return ["main"];
  }
}
