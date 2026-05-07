import type { Run, FeedEvent, RunStatus, SettingsStatus, RepoInfo, ConnectionState } from "@/lib/types";
import type { AgentHealth, HealthRunEntry } from "@/lib/api";
import type { RefObject } from "react";

export interface RunActionsConfig {
  selectedRunId: string | null;
  selectedRunIdRef: RefObject<string | null>;
  runStatus: RunStatus | null;
  addEvent: (event: FeedEvent) => void;
  filterEvents: (predicate: (e: FeedEvent) => boolean) => void;
  sseRef: RefObject<{ disconnect: () => void; clearEvents: () => void; connect: (id: string, cursors: { afterTool: number; afterAudit: number }) => void }>;
  cursorsRef: RefObject<{ afterTool: number; afterAudit: number }>;
  refreshRunsRef: RefObject<() => void>;
  handleSelectRun: (id: string) => Promise<FeedEvent[]>;
  activeRepoFilter: string | null;
  setStartModalOpen: (v: boolean) => void;
  setBusy: (v: boolean) => void;
}

export interface RunActions {
  controlAction: (label: string, fn: (id: string) => Promise<unknown>) => Promise<void>;
  handleStartRun: (
    prompt: string | undefined,
    preset: string | undefined,
    budget: number,
    durationMinutes: number,
    baseBranch: string,
    model: string,
    effort: string,
    sandboxId: string | null,
    startCmd: string,
  ) => Promise<void>;

  handleInject: (prompt: string) => void;
  handleRestart: (prompt?: string) => void;
  showStopDialog: boolean;
  handleStopClick: () => void;
  handleStopConfirm: (openPr: boolean) => void;
  handleStopCancel: () => void;
}

export interface DashboardState {
  // Data
  repos: RepoInfo[];
  runs: Run[];
  runsLoading: boolean;
  selectedRunId: string | null;
  selectedRun: Run | null;
  allEvents: FeedEvent[];
  runStatus: RunStatus | null;
  agentHealth: AgentHealth | null;
  activeRunHealth: HealthRunEntry | undefined;
  connected: boolean;
  connectionState: ConnectionState;
  historyTruncated: boolean;
  branches: string[];
  isMobile: boolean;
  // Derived booleans
  isConfigured: boolean;
  atCapacity: boolean;
  busy: boolean;
  historyLoading: boolean;

  // UI state
  activeRepoFilter: string | null;
  startModalOpen: boolean;
  showStopDialog: boolean;
  onboardingOpen: boolean;
  settingsStatus: SettingsStatus | null;
  sidebarCollapsed: boolean;
  mobilePanel: "feed" | "runs" | "changes" | "logs";
  controlsOpen: boolean;
  rightPanel: "changes" | "logs";

  // UI state (continued)
  showShortcuts: boolean;
  setShowShortcuts: (v: boolean) => void;

  // Actions
  controlAction: (label: string, fn: (id: string) => Promise<unknown>) => Promise<void>;
  handleToggleSidebar: () => void;
  handleRepoSwitch: (repo: string) => Promise<void>;
  handleSelectRun: (id: string) => Promise<FeedEvent[]>;
  handleStartRun: (
    prompt: string | undefined,
    preset: string | undefined,
    budget: number,
    durationMinutes: number,
    baseBranch: string,
    model: string,
    effort: string,
    sandboxId: string | null,
    startCmd: string,
  ) => Promise<void>;

  handleInject: (prompt: string) => void;
  handleRestart: (prompt?: string) => void;
  handleStopClick: () => void;
  handleStopConfirm: (openPr: boolean) => void;
  handleStopCancel: () => void;
  setStartModalOpen: (v: boolean) => void;
  setOnboardingOpen: (v: boolean) => void;
  setMobilePanel: (v: "feed" | "runs" | "changes" | "logs") => void;
  setControlsOpen: (v: boolean) => void;
  setRightPanel: (v: "changes" | "logs") => void;
  setBranches: (v: string[]) => void;
  setSettingsStatus: (v: SettingsStatus) => void;
  setRepos: (v: RepoInfo[]) => void;
}
