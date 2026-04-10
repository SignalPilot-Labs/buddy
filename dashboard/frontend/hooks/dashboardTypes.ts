import type { Run, FeedEvent, RunStatus, SettingsStatus, RepoInfo, PendingMessage } from "@/lib/types";
import type { AgentHealth, HealthRunEntry } from "@/lib/api";

export interface DashboardState {
  // Data
  repos: RepoInfo[];
  runs: Run[];
  runsLoading: boolean;
  selectedRunId: string | null;
  selectedRun: Run | null;
  allEvents: FeedEvent[];
  pendingMessages: PendingMessage[];
  runStatus: RunStatus | null;
  agentHealth: AgentHealth | null;
  activeRunHealth: HealthRunEntry | undefined;
  connected: boolean;
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
  showKillConfirm: boolean;
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
    budget: number,
    durationMinutes: number,
    baseBranch: string,
    model?: string | undefined,
  ) => Promise<void>;
  handleInject: (prompt: string) => void;
  handleRestart: (prompt: string) => void;
  handleHeaderKill: () => void;
  setStartModalOpen: (v: boolean) => void;
  setOnboardingOpen: (v: boolean) => void;
  setMobilePanel: (v: "feed" | "runs" | "changes" | "logs") => void;
  setControlsOpen: (v: boolean) => void;
  setRightPanel: (v: "changes" | "logs") => void;
  setBranches: (v: string[]) => void;
  setSettingsStatus: (v: SettingsStatus) => void;
  setRepos: (v: RepoInfo[]) => void;
}
