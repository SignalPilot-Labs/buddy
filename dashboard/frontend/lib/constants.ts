/**Shared constants for the dashboard frontend.
 *
 * Ports must match config/config.yml (source of truth for deployment values).
 */

export const API_PORT = 3401;
export const UI_PORT = 3400;
/** API key injected by entrypoint.sh into /public/config.js at runtime. */
declare global {
  interface Window {
    __AUTOFYN_API_KEY__?: string;
  }
}

export function getApiKey(): string {
  if (typeof window !== "undefined" && window.__AUTOFYN_API_KEY__) {
    return window.__AUTOFYN_API_KEY__;
  }
  return process.env.DASHBOARD_API_KEY || "";
}

export const API_KEY = getApiKey();

// Polling intervals (ms)
export const AGENT_HEALTH_POLL_MS = 10_000;
export const NETWORK_INFO_POLL_MS = 30_000;
export const SSE_POLL_INTERVAL_MS = 1_000;
export const SSE_FALLBACK_TIMEOUT_MS = 3_000;

// Fetch limits
export const HISTORY_FETCH_LIMIT = 500;
export const API_FETCH_TIMEOUT_MS = 15_000;

// Container logs
export const CONTAINER_LOGS_POLL_MS = 3000;
export const CONTAINER_LOGS_DEFAULT_TAIL = 500;

// Sidebar
export const PROMPT_LABEL_MAX_LEN = 40;

// Model selector
export type ModelId = "opus" | "sonnet" | "haiku";

// localStorage keys
export const LOCALSTORAGE_MODEL_KEY = "autofyn_model";
export const DEFAULT_MODEL: ModelId = "opus";

export interface ModelOption {
  id: ModelId;
  label: string;
  description: string;
  context: string;
}

export const MODEL_OPTIONS: ModelOption[] = [
  { id: "opus",   label: "Claude Opus 4.6",   description: "Most capable, best for agents", context: "1M context" },
  { id: "sonnet", label: "Claude Sonnet 4.6", description: "Fast and capable",               context: "1M context" },
  { id: "haiku",  label: "Claude Haiku 4.5",  description: "Fastest, lowest cost",           context: "200K context" },
];

/** Normalise a raw model_name (e.g. "claude-opus-4-6-20250514") to a ModelId. */
export function resolveModelId(modelName: string | null | undefined): ModelId | null {
  if (!modelName) return null;
  const lower = modelName.toLowerCase();
  if (lower.includes("opus")) return "opus";
  if (lower.includes("haiku")) return "haiku";
  if (lower.includes("sonnet")) return "sonnet";
  return null;
}

/** Maps raw model_name strings (or ModelId keys) to a short badge label. */
export const MODEL_BADGE_LABEL: Record<string, string> = {
  opus:   "Opus",
  sonnet: "Sonnet",
  haiku:  "Haiku",
};

/** Color tokens for model badges. */
export const MODEL_BADGE_COLOR: Record<string, string> = {
  opus:   "text-[#cc88ff] bg-[#cc88ff]/10",
  sonnet: "text-[#88ccff] bg-[#88ccff]/10",
  haiku:  "text-[#00ff88] bg-[#00ff88]/10",
};

// Run status sets for control bar enabling logic.
// Must match backend's accepted statuses in resume_run and inject_prompt endpoints.
import type { RunStatus } from "./types";

export const ACTIVE_STATUSES: ReadonlyArray<RunStatus> = [
  "running",
  "paused",
  "rate_limited",
];

export const RESUMABLE_STATUSES: ReadonlyArray<RunStatus> = [
  "paused",
  "completed",
  "stopped",
  "error",
];

export const INJECTABLE_STATUSES: ReadonlyArray<RunStatus> = [
  "running",
  "paused",
  "rate_limited",
  "completed",
  "stopped",
  "error",
];

export const TERMINAL_STATUSES: ReadonlySet<RunStatus> = new Set<RunStatus>([
  "completed",
  "stopped",
  "error",
  "crashed",
  "killed",
  "completed_no_changes",
]);

export function getApiBase(): string {
  // Server-side: call FastAPI directly.
  // Client-side: use empty string so all /api/* requests go to the same origin
  // (Next.js rewrites proxy them to the backend).
  if (typeof window === "undefined") return `http://localhost:${API_PORT}`;
  return "";
}
