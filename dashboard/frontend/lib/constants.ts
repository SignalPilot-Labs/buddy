/**Shared constants for the dashboard frontend.
 *
 * Ports must match config/config.yml (source of truth for deployment values).
 */

export const API_PORT = 3401;
export const UI_PORT = 3400;
/** API key injected server-side by layout.tsx into inline script at render time. */
declare global {
  interface Window {
    __AUTOFYN_API_KEY__?: string;
  }
}

export function getApiKey(): string {
  if (typeof window === "undefined") return "";
  const key = window.__AUTOFYN_API_KEY__;
  if (!key) throw new Error("API key not injected — check AUTOFYN_API_KEY env var on Next.js process");
  return key;
}

export const API_KEY = getApiKey();

// Polling intervals (ms)
export const AGENT_HEALTH_POLL_MS = 10_000;
export const NETWORK_INFO_POLL_MS = 30_000;
export const SSE_POLL_INTERVAL_MS = 1_000;
export const SSE_FALLBACK_TIMEOUT_MS = 3_000;
export const DIFF_POLL_INTERVAL_MS = 15_000;
// Hard cap on diff text size held in memory. Enormous diffs (stale cache
// bugs, unrelated-history merges) lock up the main thread on every parse.
// Above this we drop the diff and the Changes panel shows a 'too large'
// message instead of freezing.
export const DIFF_MAX_BYTES = 10 * 1024 * 1024;

// Fetch limits
export const HISTORY_FETCH_LIMIT = 5000;
export const API_FETCH_TIMEOUT_MS = 15_000;

// Container logs
export const CONTAINER_LOGS_POLL_MS = 3000;
export const CONTAINER_LOGS_DEFAULT_TAIL = 500;

// Sidebar
export const PROMPT_LABEL_MAX_LEN = 40;
export const STATUS_FLASH_DURATION_MS = 500;

// Toast notifications
export const TOAST_DURATION_MS = 3000;
export const MAX_VISIBLE_TOASTS = 3;

// Event feed
export const TOOL_CATEGORIES_DEFAULT_EXPANDED: ReadonlySet<string> = new Set(["todo"]);
export const SCROLL_BOTTOM_THRESHOLD = 20;
export const AGENT_IDLE_TIMER_INTERVAL_MS = 5000;

// Skeleton loading state
export const SKELETON_COUNT = 5;
export const SKELETON_HEIGHT = "h-12";
export const SKELETON_WIDTHS: ReadonlyArray<string> = ["w-1/3", "w-1/2", "w-2/5", "w-3/5", "w-1/4"];

// Connection banner grace period — suppress transient "Disconnected" flash
// during run switches where SSE disconnects and reconnects within seconds.
export const CONNECTION_BANNER_DELAY_MS = 5000;

// SSE reconnect backoff
export const RECONNECT_BASE_MS = 1000;
export const RECONNECT_MAX_MS = 30000;
export const RECONNECT_MAX_ATTEMPTS = 10;

// Default base branch for new runs.
export const DEFAULT_BASE_BRANCH = "main";

// Effort levels for the thinking-effort picker.
export const EFFORT_LEVELS = ["low", "medium", "high", "max"] as const;
export type EffortLevel = (typeof EFFORT_LEVELS)[number];
export const DEFAULT_EFFORT: EffortLevel = "high";

// Safety timeout for the stop-busy lock (ms). If SSE and polling both fail to
// deliver run_ended within this window, the UI unlocks so the user isn't stuck.
export const STOP_BUSY_TIMEOUT_MS = 60_000;

// Starter presets for the "Quick Start" cards in the new-run modal.
// Keys must match STARTER_PRESET_KEYS in db/constants.py — sync test enforces this.
export const STARTER_PRESETS = {
  security_hardening: { label: "Security hardening", icon: "shield", desc: "Fix security vulnerabilities" },
  bug_bash: { label: "Bug bash", icon: "bug", desc: "Find and squash bugs" },
  code_quality: { label: "Code quality", icon: "sparkle", desc: "Refactor for quality and performance" },
  test_coverage: { label: "Test coverage", icon: "flask", desc: "Add missing tests" },
} as const;
export type StarterPresetKey = keyof typeof STARTER_PRESETS;
export const STARTER_PRESET_KEYS: StarterPresetKey[] = Object.keys(STARTER_PRESETS) as StarterPresetKey[];

// Branches pinned to the top of the branch picker, in display order.
export const PINNED_BRANCHES: ReadonlyArray<string> = ["main", "staging"];

// Run ID display
export const RUN_ID_DISPLAY_LENGTH = 8;
export const COPY_FEEDBACK_MS = 1500;

// Model selector — uses exact SDK model IDs, no aliases.
export type ModelId = "claude-opus-4-6" | "claude-sonnet-4-6" | "claude-opus-4-5";

export const LOCALSTORAGE_MODEL_KEY = "autofyn_model";
export const DEFAULT_MODEL: ModelId = "claude-opus-4-6";

export interface ModelSpec {
  /** Full product label shown in the picker. */
  label: string;
  /** Short badge label for run cards and stats bar. */
  badge: string;
  /** One-line description for the picker. */
  description: string;
  /** Context window size blurb. */
  context: string;
  /** Tailwind class tokens for the badge (text + bg). */
  color: string;
}

export const MODELS: Record<ModelId, ModelSpec> = {
  "claude-opus-4-6": {
    label: "Claude Opus 4.6",
    badge: "Opus",
    description: "Most capable, best for agents",
    context: "1M context",
    color: "text-[#cc88ff] bg-[#cc88ff]/10",
  },
  "claude-sonnet-4-6": {
    label: "Claude Sonnet 4.6",
    badge: "Sonnet",
    description: "Fast and capable",
    context: "1M context",
    color: "text-[#88ccff] bg-[#88ccff]/10",
  },
  "claude-opus-4-5": {
    label: "Claude Opus 4.5",
    badge: "Opus 4.5",
    description: "Legacy Opus model",
    context: "200K context",
    color: "text-[#ffaa66] bg-[#ffaa66]/10",
  },
};

/** Ordered list for rendering the picker; derived from MODELS to avoid drift. */
export const MODEL_IDS: ReadonlyArray<ModelId> = ["claude-opus-4-6", "claude-sonnet-4-6", "claude-opus-4-5"];

/** Normalise a raw model_name from the DB to a ModelId. */
export function resolveModelId(modelName: string | null | undefined): ModelId | null {
  if (!modelName) return null;
  const lower = modelName.toLowerCase();
  if (lower.includes("opus-4-5") || lower.includes("opus-4.5")) return "claude-opus-4-5";
  if (lower.includes("opus")) return "claude-opus-4-6";
  if (lower.includes("sonnet")) return "claude-sonnet-4-6";
  return null;
}

/** Parse a localStorage string into a valid ModelId, or null if missing/invalid. */
export function parseStoredModel(raw: string | null): ModelId | null {
  if (raw === "claude-opus-4-6" || raw === "claude-sonnet-4-6" || raw === "claude-opus-4-5") return raw;
  // Migrate old aliases
  if (raw === "opus") return "claude-opus-4-6";
  if (raw === "sonnet") return "claude-sonnet-4-6";
  if (raw === "opus-4-5") return "claude-opus-4-5";
  return null;
}

/** Read the user's preferred model from localStorage, falling back to DEFAULT_MODEL. */
export function loadStoredModel(): ModelId {
  if (typeof window === "undefined") return DEFAULT_MODEL;
  return parseStoredModel(localStorage.getItem(LOCALSTORAGE_MODEL_KEY)) ?? DEFAULT_MODEL;
}

/** Persist the user's preferred model to localStorage. */
export function saveStoredModel(id: ModelId): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(LOCALSTORAGE_MODEL_KEY, id);
}

// Run status sets for control bar enabling logic.
// Must match backend's accepted statuses in resume_run and inject_prompt endpoints.
import type { RunStatus } from "./types";

export const ACTIVE_STATUSES: ReadonlyArray<RunStatus> = [
  "starting",
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

// MCP Servers
export const MAX_MCP_SERVERS = 10;
export const MCP_SERVER_TYPES = ["stdio", "sse", "http"] as const;
export type McpServerType = (typeof MCP_SERVER_TYPES)[number];

// Panel resize
export const SIDEBAR_DEFAULT_WIDTH = 260;
export const SIDEBAR_MIN_WIDTH = 180;
export const SIDEBAR_MAX_WIDTH = 400;
export const RIGHT_PANEL_DEFAULT_WIDTH = 280;
export const RIGHT_PANEL_MIN_WIDTH = 200;
// Ratio of viewport width the right panel may occupy, capped by _PX for huge monitors.
export const RIGHT_PANEL_MAX_WIDTH_RATIO = 0.7;
export const RIGHT_PANEL_MAX_WIDTH_PX = 1600;
export const SIDEBAR_COLLAPSED_WIDTH = 48;
export const PANEL_WIDTH_STORAGE_PREFIX = "autofyn_panel_";

export function getApiBase(): string {
  // Server-side: call FastAPI directly.
  // Client-side: use empty string so all /api/* requests go to the same origin
  // (Next.js rewrites proxy them to the backend).
  if (typeof window === "undefined") return `http://localhost:${API_PORT}`;
  return "";
}

/** Capitalize the first character of a string. */
export function capitalize(s: string): string {
  if (s.length === 0) return s;
  return s[0].toUpperCase() + s.slice(1);
}
