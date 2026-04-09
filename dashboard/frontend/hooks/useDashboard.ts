"use client";

import { useState, useCallback, useEffect, useRef, useMemo } from "react";
import type { Run, FeedEvent, RunStatus, SettingsStatus, RepoInfo } from "@/lib/types";
import {
  fetchAgentHealth,
  fetchRepos,
  setActiveRepo,
  startRun as apiStartRun,
  killAgent,
  resumeAgent,
  injectPrompt as apiInjectPrompt,
} from "@/lib/api";
import type { AgentHealth, HealthRunEntry } from "@/lib/api";
import { AGENT_HEALTH_POLL_MS, TERMINAL_STATUSES } from "@/lib/constants";
import { fetchSettingsStatus } from "@/lib/settings-api";
import { isAtCapacity } from "@/lib/capacity";
import { loadRunHistory } from "@/lib/loadRunHistory";
import { useRuns } from "@/hooks/useRuns";
import { useSSE } from "@/hooks/useSSE";
import { useMobile } from "@/hooks/useMobile";

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
  branches: string[];
  isMobile: boolean;
  // Derived booleans
  isConfigured: boolean;
  atCapacity: boolean;
  busy: boolean;

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

  // Actions
  controlAction: (label: string, fn: (id: string) => Promise<unknown>) => void;
  handleToggleSidebar: () => void;
  handleRepoSwitch: (repo: string) => Promise<void>;
  handleSelectRun: (id: string) => Promise<void>;
  handleStartRun: (
    prompt: string | undefined,
    budget: number,
    durationMinutes: number,
    baseBranch: string,
    extendedContext?: boolean,
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

export function useDashboard(): DashboardState {
  const [activeRepoFilter, setActiveRepoFilter] = useState<string | null>(() => {
    try { return localStorage.getItem("sp_improve_active_repo") || null; } catch { return null; }
  });
  const [repos, setRepos] = useState<RepoInfo[]>([]);
  const { runs, loading: runsLoading, refresh: refreshRuns } = useRuns(activeRepoFilter);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [selectedRun, setSelectedRun] = useState<Run | null>(null);
  const [historyEvents, setHistoryEvents] = useState<FeedEvent[]>([]);
  const [startModalOpen, setStartModalOpen] = useState(false);
  const [showKillConfirm, setShowKillConfirm] = useState(false);
  const [agentHealth, setAgentHealth] = useState<AgentHealth | null>(null);
  const [branches, setBranches] = useState<string[]>(["main"]);
  const [settingsStatus, setSettingsStatus] = useState<SettingsStatus | null>(null);
  const [onboardingOpen, setOnboardingOpen] = useState(false);
  const selectGenRef = useRef(0);
  const skipLastRunRestoreRef = useRef(false);
  const isMobile = useMobile();
  const [mobilePanel, setMobilePanel] = useState<"feed" | "runs" | "changes" | "logs">("feed");
  const [controlsOpen, setControlsOpen] = useState(false);
  const [rightPanel, setRightPanel] = useState<"changes" | "logs">("changes");
  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(() => {
    try { return localStorage.getItem("autofyn_sidebar_collapsed") === "true"; } catch { return false; }
  });
  const [busy, setBusy] = useState(false);

  const selectedRunIdRef = useRef<string | null>(null);
  useEffect(() => { selectedRunIdRef.current = selectedRunId; }, [selectedRunId]);

  const handleSessionResumed = useCallback(() => {
    const runId = selectedRunIdRef.current;
    if (!runId) return;
    sseRef.current.disconnect();
    loadRunHistory(runId).then(({ events, lastToolId, lastAuditId }) => {
      setHistoryEvents((prev) => {
        const pendingSynthetics = prev.filter((e) => e._kind === "audit" && e.data.id < 0 && e.data.details._pending);
        if (pendingSynthetics.length === 0) return events;
        // Count real prompt events that arrived AFTER the oldest synthetic was created
        const oldestSyntheticTs = pendingSynthetics[0]._kind === "audit" ? pendingSynthetics[0].data.ts : "";
        const confirmedCount = events.filter(
          (e) => e._kind === "audit"
            && (e.data.event_type === "prompt_injected" || e.data.event_type === "prompt_submitted")
            && e.data.ts >= oldestSyntheticTs,
        ).length;
        const stillPending = pendingSynthetics.slice(confirmedCount);
        return stillPending.length > 0 ? [...events, ...stillPending] : events;
      });
      sseRef.current.clearEvents();
      sseRef.current.connect(runId, { afterTool: lastToolId, afterAudit: lastAuditId });
    }).catch(() => {});
  }, []);

  const { events: liveEvents, connected, clearEvents, connect: sseConnect, disconnect: sseDisconnect } = useSSE(refreshRuns, handleSessionResumed);
  const sseRef = useRef({ connect: sseConnect, disconnect: sseDisconnect, clearEvents });
  sseRef.current = { connect: sseConnect, disconnect: sseDisconnect, clearEvents };

  // Track synthetic prompt IDs for dedup — survives historyEvents resets
  const syntheticIdsRef = useRef<Set<number>>(new Set());

  // When real prompt_injected arrives via SSE, clear _pending on oldest unmatched synthetic
  useEffect(() => {
    const realCount = liveEvents.filter(
      (e) => e._kind === "audit" && (e.data.event_type === "prompt_injected" || e.data.event_type === "prompt_submitted"),
    ).length;
    if (realCount === 0) return;
    setHistoryEvents((prev) => {
      const pendingSynthetics = prev.filter(
        (e) => e._kind === "audit" && e.data.details._pending && e.data.id < 0,
      );
      // Clear _pending on synthetics that have been confirmed (match count-based, FIFO)
      const toConfirm = Math.min(realCount, pendingSynthetics.length);
      if (toConfirm === 0) return prev;
      const confirmIds = new Set(pendingSynthetics.slice(0, toConfirm).map((e) => e._kind === "audit" ? e.data.id : 0));
      return prev.map((e) => {
        if (e._kind === "audit" && confirmIds.has(e.data.id)) {
          return { ...e, data: { ...e.data, details: { ...e.data.details, _pending: false } } };
        }
        return e;
      });
    });
  }, [liveEvents]);

  // Merge history + live, filtering out live prompt events that duplicate a synthetic
  const allEvents = useMemo(() => {
    const syntheticIds = syntheticIdsRef.current;
    if (syntheticIds.size === 0) return [...historyEvents, ...liveEvents];
    // Count synthetics still in history (confirmed or pending)
    const syntheticsInHistory = historyEvents.filter(
      (e) => e._kind === "audit" && e.data.id < 0 && syntheticIds.has(e.data.id),
    ).length;
    if (syntheticsInHistory === 0) {
      syntheticIdsRef.current = new Set();
      return [...historyEvents, ...liveEvents];
    }
    // Filter out that many real prompt events from live to avoid duplicates
    let skipRemaining = syntheticsInHistory;
    const filtered = liveEvents.filter((e) => {
      if (skipRemaining <= 0) return true;
      if (e._kind !== "audit") return true;
      if (e.data.event_type !== "prompt_injected" && e.data.event_type !== "prompt_submitted") return true;
      skipRemaining--;
      return false;
    });
    const merged = [...historyEvents, ...filtered];
    // Synthetics are appended to historyEvents and may be out of order — sort by timestamp
    if (syntheticIds.size > 0) {
      merged.sort((a, b) => {
        const tsA = a._kind === "tool" || a._kind === "audit" || a._kind === "usage" ? a.data.ts : a.ts;
        const tsB = b._kind === "tool" || b._kind === "audit" || b._kind === "usage" ? b.data.ts : b.ts;
        return tsA < tsB ? -1 : tsA > tsB ? 1 : 0;
      });
    }
    return merged;
  }, [historyEvents, liveEvents]);

  const addEvent = useCallback((event: FeedEvent) => {
    setHistoryEvents((prev) => [...prev, event]);
  }, []);

  const controlAction = useCallback((label: string, fn: (id: string) => Promise<unknown>) => {
    if (selectedRunId) {
      fn(selectedRunId).catch((e) =>
        addEvent({ _kind: "control", text: `${label} failed: ${e}`, ts: new Date().toISOString() })
      );
    }
  }, [selectedRunId, addEvent]);

  const handleToggleSidebar = useCallback(() => {
    setSidebarCollapsed((prev) => {
      const next = !prev;
      try { localStorage.setItem("autofyn_sidebar_collapsed", String(next)); } catch {}
      return next;
    });
  }, []);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "b") {
        e.preventDefault();
        handleToggleSidebar();
        return;
      }
      // 'N' to open new run modal (only when not focused in an input)
      const tag = (e.target as HTMLElement)?.tagName;
      if (e.key === "n" && !e.metaKey && !e.ctrlKey && tag !== "INPUT" && tag !== "TEXTAREA" && tag !== "SELECT") {
        e.preventDefault();
        setStartModalOpen(true);
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [handleToggleSidebar]);

  useEffect(() => {
    const check = async () => {
      const h = await fetchAgentHealth();
      setAgentHealth((prev) => {
        const prevIds = new Set(prev?.runs.map((r) => r.run_id) ?? []);
        const newRun = h.runs.find((r) => !prevIds.has(r.run_id));
        if (newRun) {
          refreshRuns();
          const currentId = selectedRunIdRef.current;
          const currentRunInHealth = prev?.runs.find((r) => r.run_id === currentId);
          const currentIsTerminal = currentRunInHealth
            ? TERMINAL_STATUSES.has(currentRunInHealth.status as RunStatus)
            : true;
          if (currentId === null || currentIsTerminal) {
            setSelectedRunId(newRun.run_id);
          }
        }
        return h;
      });
    };
    check();
    const id = setInterval(check, AGENT_HEALTH_POLL_MS);
    return () => clearInterval(id);
  }, [refreshRuns]);

  useEffect(() => {
    fetchSettingsStatus().then((s) => {
      setSettingsStatus(s);
      if (!s.configured) setOnboardingOpen(true);
    });
    fetchRepos().then((r) => {
      setRepos(r);
      if (r.length > 0) {
        const stored = activeRepoFilter;
        const valid = stored && r.some((repo) => repo.repo === stored);
        if (!valid) {
          const withRuns = r.find((repo) => repo.run_count > 0);
          const picked = withRuns?.repo || r[0].repo;
          setActiveRepoFilter(picked);
          try { localStorage.setItem("sp_improve_active_repo", picked); } catch {}
        }
      }
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleRepoSwitch = useCallback(async (repo: string) => {
    skipLastRunRestoreRef.current = true;
    setActiveRepoFilter(repo || null);
    try {
      if (repo) localStorage.setItem("sp_improve_active_repo", repo);
      else localStorage.removeItem("sp_improve_active_repo");
    } catch {}
    sseRef.current.disconnect();
    setSelectedRunId(null);
    setSelectedRun(null);
    setHistoryEvents([]);
    sseRef.current.clearEvents();
    if (repo) {
      try { await setActiveRepo(repo); } catch (e) { console.error("Failed to set active repo:", e); }
    }
    fetchRepos().then(setRepos);
  }, []);

  useEffect(() => {
    if (selectedRunId) {
      const found = runs.find((r) => r.id === selectedRunId);
      if (found) setSelectedRun(found);
    }
  }, [runs, selectedRunId]);

  const handleSelectRun = useCallback(
    async (id: string) => {
      const gen = ++selectGenRef.current;
      sseRef.current.disconnect();
      setSelectedRunId(id);
      localStorage.setItem("autofyn_last_run_id", id);
      setHistoryEvents([]);
      sseRef.current.clearEvents();
      let lastToolId = 0;
      let lastAuditId = 0;
      try {
        const result = await loadRunHistory(id);
        if (gen !== selectGenRef.current) return;
        setHistoryEvents(result.events);
        lastToolId = result.lastToolId;
        lastAuditId = result.lastAuditId;
      } catch (err) {
        console.warn("Failed to load history:", err);
      }
      if (gen !== selectGenRef.current) return;
      sseRef.current.connect(id, { afterTool: lastToolId, afterAudit: lastAuditId });
      refreshRuns();
    },
    [refreshRuns],
  );

  useEffect(() => {
    if (!selectedRunId && runs.length > 0) {
      if (activeRepoFilter && !runs.some((r) => r.github_repo === activeRepoFilter)) return;
      const skipRestore = skipLastRunRestoreRef.current;
      skipLastRunRestoreRef.current = false;
      if (!skipRestore) {
        const lastRunId = localStorage.getItem("autofyn_last_run_id");
        if (lastRunId && runs.some((r) => r.id === lastRunId)) {
          handleSelectRun(lastRunId);
          return;
        }
      }
      const active = runs.find((r) => ["running", "paused", "rate_limited"].includes(r.status));
      handleSelectRun(active?.id || runs[0].id);
    }
  }, [runs, selectedRunId, handleSelectRun, activeRepoFilter]);

  const handleStartRun = useCallback(
    async (
      prompt: string | undefined,
      budget: number,
      durationMinutes: number,
      baseBranch: string,
      extendedContext: boolean = false,
    ) => {
      setStartModalOpen(false);
      setBusy(true);
      try {
        const result = await apiStartRun(prompt, budget, durationMinutes, baseBranch, extendedContext, activeRepoFilter);
        refreshRuns();
        if (result.run_id) handleSelectRun(result.run_id);
      } catch (err) {
        addEvent({ _kind: "control", text: `Failed to start run: ${err}`, ts: new Date().toISOString() });
      } finally {
        setBusy(false);
      }
    },
    [addEvent, handleSelectRun, refreshRuns, activeRepoFilter],
  );

  const runStatus: RunStatus | null = (selectedRun?.status as RunStatus) || null;

  const addSyntheticPrompt = useCallback(
    (prompt: string): number => {
      const syntheticId = -Date.now();
      const ts = new Date().toISOString();
      const synthetic: FeedEvent = {
        _kind: "audit",
        data: { id: syntheticId, run_id: selectedRunId ?? "", ts, event_type: "prompt_submitted", details: { prompt, _pending: true } },
      };
      syntheticIdsRef.current.add(syntheticId);
      setHistoryEvents((prev) => [...prev, synthetic]);
      return syntheticId;
    },
    [selectedRunId],
  );

  const markSyntheticFailed = useCallback(
    (syntheticId: number) => {
      setHistoryEvents((prev) =>
        prev.map((e) =>
          e._kind === "audit" && e.data.id === syntheticId
            ? { ...e, data: { ...e.data, details: { ...e.data.details, _pending: false, _failed: true } } }
            : e,
        ),
      );
    },
    [],
  );

  const handleInject = useCallback(
    (prompt: string) => {
      if (!selectedRunId) return;
      const sid = addSyntheticPrompt(prompt);
      apiInjectPrompt(selectedRunId, prompt).catch((e) => {
        markSyntheticFailed(sid);
        addEvent({ _kind: "control", text: `Inject failed: ${e}`, ts: new Date().toISOString() });
      });
    },
    [selectedRunId, addSyntheticPrompt, markSyntheticFailed, addEvent],
  );

  const handleRestart = useCallback(
    (prompt: string) => {
      if (!selectedRunId) return;
      const sid = prompt ? addSyntheticPrompt(prompt) : 0;
      resumeAgent(selectedRunId, prompt).catch((e) => {
        if (sid) markSyntheticFailed(sid);
        addEvent({ _kind: "control", text: `Restart failed: ${e}`, ts: new Date().toISOString() });
      });
    },
    [selectedRunId, addSyntheticPrompt, markSyntheticFailed, addEvent],
  );

  const handleHeaderKill = useCallback(() => {
    if (!showKillConfirm) {
      setShowKillConfirm(true);
      setTimeout(() => setShowKillConfirm(false), 3000);
      return;
    }
    controlAction("Kill", killAgent);
    setShowKillConfirm(false);
  }, [showKillConfirm, controlAction]);

  const isConfigured = settingsStatus?.configured ?? false;
  const atCapacity = isAtCapacity(agentHealth);
  const activeRunHealth = selectedRunId
    ? agentHealth?.runs.find((r) => r.run_id === selectedRunId)
    : undefined;

  return {
    repos,
    runs,
    runsLoading,
    selectedRunId,
    selectedRun,
    allEvents,
    runStatus,
    agentHealth,
    activeRunHealth,
    connected,
    branches,
    isMobile,
    isConfigured,
    atCapacity,
    busy,
    activeRepoFilter,
    startModalOpen,
    showKillConfirm,
    onboardingOpen,
    settingsStatus,
    sidebarCollapsed,
    mobilePanel,
    controlsOpen,
    rightPanel,
    controlAction,
    handleToggleSidebar,
    handleRepoSwitch,
    handleSelectRun,
    handleStartRun,
    handleInject,
    handleRestart,
    handleHeaderKill,
    setStartModalOpen,
    setOnboardingOpen,
    setMobilePanel,
    setControlsOpen,
    setRightPanel,
    setBranches,
    setSettingsStatus,
    setRepos,
  };
}
