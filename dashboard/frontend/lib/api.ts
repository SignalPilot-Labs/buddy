import type { Run, ToolCall, AuditEvent, RepoInfo } from "./types";
import { API_KEY, getApiBase, UI_PORT } from "./constants";

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
  limit: number
): Promise<ToolCall[]> {
  const res = await apiFetch(`/api/runs/${runId}/tools?limit=${limit}`);
  if (!res.ok) throw new Error("Failed to fetch tool calls");
  return res.json();
}

export async function fetchAuditLog(
  runId: string,
  limit: number
): Promise<AuditEvent[]> {
  const res = await apiFetch(`/api/runs/${runId}/audit?limit=${limit}`);
  if (!res.ok) throw new Error("Failed to fetch audit log");
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

export function createSSE(runId: string, afterTool: number, afterAudit: number): EventSource {
  return new EventSource(
    `${getApiBase()}/api/stream/${runId}?api_key=${encodeURIComponent(API_KEY)}&after_tool=${afterTool}&after_audit=${afterAudit}`,
  );
}

export type PollEventItem =
  | (ToolCall & { _event_type: "tool_call" })
  | (AuditEvent & { _event_type: "audit" });

export interface PollResult {
  events: PollEventItem[];
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

export interface HealthRunEntry {
  run_id: string;
  status: string;
  started_at: number;
  elapsed_minutes?: number | null;
  time_remaining?: string | null;
  session_unlocked?: boolean | null;
}

export interface AgentHealth {
  status: "idle" | "running" | "bootstrapping" | "unreachable";
  active_runs: number;
  max_concurrent: number;
  runs: HealthRunEntry[];
}

const UNREACHABLE_HEALTH: AgentHealth = { status: "unreachable", active_runs: 0, max_concurrent: 0, runs: [] };

export async function fetchAgentHealth(): Promise<AgentHealth> {
  try {
    const res = await apiFetch(`/api/agent/health`);
    if (!res.ok) return UNREACHABLE_HEALTH;
    return res.json();
  } catch (err) {
    console.warn("Agent health check failed:", err);
    return UNREACHABLE_HEALTH;
  }
}

export async function startRun(
  prompt: string | undefined,
  maxBudgetUsd: number,
  durationMinutes: number,
  baseBranch: string,
  model: string,
  effort: string,
  repo: string | null,
): Promise<{ ok: boolean; run_id?: string }> {
  const res = await apiFetch(`/api/agent/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      prompt: prompt || null,
      max_budget_usd: maxBudgetUsd,
      duration_minutes: durationMinutes,
      base_branch: baseBranch,
      model: model,
      effort: effort,
      repo: repo || null,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function fetchRepoEnv(repo: string): Promise<Record<string, string>> {
  const res = await apiFetch(`/api/repos/${repo}/env`);
  if (!res.ok) return {};
  const data = await res.json();
  return data.env_vars || {};
}

export async function saveRepoEnv(repo: string, envVars: Record<string, string>): Promise<void> {
  const res = await apiFetch(`/api/repos/${repo}/env`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ env_vars: envVars }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(err.detail || `Failed to save env vars (HTTP ${res.status})`);
  }
}

export interface HostMount {
  host_path: string;
  container_path: string;
  mode: "ro" | "rw";
}

export async function fetchRepoMounts(repo: string): Promise<HostMount[]> {
  const res = await apiFetch(`/api/repos/${repo}/mounts`);
  if (!res.ok) return [];
  const data = await res.json();
  return data.mounts || [];
}

export async function saveRepoMounts(repo: string, mounts: HostMount[]): Promise<void> {
  const res = await apiFetch(`/api/repos/${repo}/mounts`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mounts }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(err.detail || `Failed to save mounts (HTTP ${res.status})`);
  }
}

export async function stopRun(runId: string, skipPr: boolean): Promise<{ ok: boolean }> {
  const res = await apiFetch(`/api/runs/${runId}/stop`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ skip_pr: skipPr }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function pauseAgent(runId: string): Promise<{ ok: boolean }> {
  const res = await apiFetch(`/api/runs/${runId}/pause`, { method: "POST" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function unlockAgent(runId: string): Promise<{ ok: boolean }> {
  const res = await apiFetch(`/api/runs/${runId}/unlock`, { method: "POST" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function resumeAgent(runId: string, prompt?: string): Promise<{ ok: boolean }> {
  const res = await apiFetch(`/api/runs/${runId}/resume`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(prompt ? { payload: prompt } : {}),
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

// ── Container Logs ───────────────────────────────────────────────────────────

export interface ContainerLogs {
  lines: string[];
  container?: string;
  total: number;
}

export async function fetchContainerLogs(tail: number): Promise<ContainerLogs> {
  try {
    const res = await apiFetch(`/api/agent/logs?tail=${tail}`);
    if (!res.ok) return { lines: [], total: 0 };
    return res.json();
  } catch {
    return { lines: [], total: 0 };
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

export async function fetchBranches(repo: string): Promise<string[]> {
  const res = await apiFetch(`/api/agent/branches?repo=${encodeURIComponent(repo)}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    throw new Error(err.detail || `Failed to fetch branches (HTTP ${res.status})`);
  }
  return res.json();
}
