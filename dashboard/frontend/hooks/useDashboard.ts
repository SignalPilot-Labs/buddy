"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import type { Run, FeedEvent, RunStatus, SettingsStatus, RepoInfo, PendingMessage } from "@/lib/types";
import type { Dispatch, SetStateAction } from "react";
import {
  fetchAgentHealth,
  fetchRepos,
  setActiveRepo,
  startRun as apiStartRun,
  killAgent,
  resumeAgent,
  injectPrompt as apiInjectPrompt,
} from "@/lib/api";
import { useKeyboardShortcuts } from "@/hooks/useKeyboardShortcuts";
import type { AgentHealth, HealthRunEntry } from "@/lib/api";
import type { DashboardState } from "@/hooks/dashboardTypes";
import { AGENT_HEALTH_POLL_MS, TERMINAL_STATUSES, loadStoredModel } from "@/lib/constants";
import { fetchSettingsStatus } from "@/lib/settings-api";
import { isAtCapacity } from "@/lib/capacity";
import { loadRunHistory } from "@/lib/loadRunHistory";
import { useRuns } from "@/hooks/useRuns";
import { useSSE } from "@/hooks/useSSE";
import { useMobile } from "@/hooks/useMobile";
import { useEventState } from "@/hooks/useEventState";

export function useDashboard(): DashboardState {
  const [activeRepoFilter, setActiveRepoFilter] = useState<string | null>(() => {
    try { return localStorage.getItem("sp_improve_active_repo") || null; } catch { return null; }
  });
  const [repos, setRepos] = useState<RepoInfo[]>([]);
  const { runs, loading: runsLoading, refresh: refreshRuns } = useRuns(activeRepoFilter);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [selectedRun, setSelectedRun] = useState<Run | null>(null);
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
  const [showShortcuts, setShowShortcuts] = useState(false);

  const selectedRunIdRef = useRef<string | null>(null);
  useEffect(() => { selectedRunIdRef.current = selectedRunId; }, [selectedRunId]);
  const cursorsRef = useRef({ afterTool: 0, afterAudit: 0 });

  // Stable refs — wired to useEventState setters after useSSE (ordering constraint)
  const failAllPendingRef = useRef<() => void>(() => undefined);
  const refreshRunsRef = useRef(refreshRuns);
  refreshRunsRef.current = refreshRuns;
  const setHistoryEventsRef = useRef<(events: FeedEvent[]) => void>(() => undefined);
  const setHistoryLoadingRef = useRef<(v: boolean) => void>(() => undefined);
  const setHistoryTruncatedRef = useRef<(v: boolean) => void>(() => undefined);
  const setPendingMessagesRef = useRef<Dispatch<SetStateAction<PendingMessage[]>>>(() => undefined);
  const addEventRef = useRef<(event: FeedEvent) => void>(() => undefined);

  const handleRunEnded = useCallback(() => {
    refreshRunsRef.current();
    setBusy(false);
    failAllPendingRef.current();
  }, []);

  const handleSessionResumed = useCallback(() => {
    const runId = selectedRunIdRef.current;
    if (!runId) return;
    sseRef.current.disconnect();
    setPendingMessagesRef.current([]);
    setHistoryLoadingRef.current(true);
    loadRunHistory(runId).then(({ events, lastToolId, lastAuditId, truncated }) => {
      setHistoryEventsRef.current(events);
      setHistoryTruncatedRef.current(truncated);
      cursorsRef.current = { afterTool: lastToolId, afterAudit: lastAuditId };
      sseRef.current.clearEvents();
      sseRef.current.connect(runId, { afterTool: lastToolId, afterAudit: lastAuditId });
      setHistoryLoadingRef.current(false);
    }).catch((err) => {
      setHistoryLoadingRef.current(false);
      addEventRef.current({ _kind: "control", text: `Session resume failed: ${err}`, ts: new Date().toISOString() });
    });
  }, []);

  const { events: liveEvents, connected, connectionState, clearEvents, connect: sseConnect, disconnect: sseDisconnect } = useSSE(handleRunEnded, handleSessionResumed);
  const sseRef = useRef({ connect: sseConnect, disconnect: sseDisconnect, clearEvents });
  sseRef.current = { connect: sseConnect, disconnect: sseDisconnect, clearEvents };

  const evState = useEventState(liveEvents);
  const { allEvents, historyLoading, historyTruncated, pendingMessages } = evState;
  const { addEvent, addPendingMessage, markPendingFailed } = evState;

  failAllPendingRef.current = evState.failAllPending;
  setHistoryEventsRef.current = evState.setHistoryEvents;
  setHistoryLoadingRef.current = evState.setHistoryLoading;
  setHistoryTruncatedRef.current = evState.setHistoryTruncated;
  setPendingMessagesRef.current = evState.setPendingMessages;
  addEventRef.current = addEvent;

  const controlAction = useCallback((label: string, fn: (id: string) => Promise<unknown>): Promise<void> => {
    if (!selectedRunId) return Promise.resolve();
    return fn(selectedRunId).then(() => undefined).catch((e: unknown) => {
      const retry = () => controlAction(label, fn);
      addEvent({
        _kind: "control",
        text: `${label} failed: ${e}`,
        ts: new Date().toISOString(),
        retryAction: retry,
      });
      return Promise.reject(e);
    });
  }, [selectedRunId, addEvent]);

  const handleToggleSidebar = useCallback(() => {
    setSidebarCollapsed((prev) => {
      const next = !prev;
      try { localStorage.setItem("autofyn_sidebar_collapsed", String(next)); } catch {}
      return next;
    });
  }, []);

  const runStatus: RunStatus | null = (selectedRun?.status as RunStatus) || null;

  useKeyboardShortcuts({
    handleToggleSidebar,
    setStartModalOpen,
    showShortcuts,
    setShowShortcuts,
    controlAction,
    runStatus,
    busy,
  });

  useEffect(() => {
    const check = async () => {
      const h = await fetchAgentHealth();
      setAgentHealth((prev) => {
        const prevIds = new Set(prev?.runs.map((r) => r.run_id) ?? []);
        const newRun = h.runs.find((r) => !prevIds.has(r.run_id));
        if (newRun) {
          refreshRunsRef.current();
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
  }, []);

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
    setHistoryEventsRef.current([]);
    setPendingMessagesRef.current([]);
    sseRef.current.clearEvents();
    setBranches([]);
    if (repo) {
      try { await setActiveRepo(repo); } catch (e) { console.error("Failed to set active repo:", e); }
    }
    fetchRepos().then(setRepos);
  }, []);

  useEffect(() => {
    if (selectedRunId) {
      const found = runs.find((r) => r.id === selectedRunId);
      if (found) {
        setSelectedRun(found);
        if (TERMINAL_STATUSES.has(found.status as RunStatus)) setBusy(false);
      }
    }
  }, [runs, selectedRunId]);

  const handleSelectRun = useCallback(
    async (id: string): Promise<FeedEvent[]> => {
      const gen = ++selectGenRef.current;
      sseRef.current.disconnect();
      setSelectedRunId(id);
      setPendingMessagesRef.current([]);
      localStorage.setItem("autofyn_last_run_id", id);
      setHistoryLoadingRef.current(true);
      sseRef.current.clearEvents();
      let lastToolId = 0;
      let lastAuditId = 0;
      let loadedEvents: FeedEvent[] = [];
      try {
        const result = await loadRunHistory(id);
        if (gen !== selectGenRef.current) return loadedEvents;
        setHistoryEventsRef.current(result.events);
        setHistoryTruncatedRef.current(result.truncated);
        loadedEvents = result.events;
        lastToolId = result.lastToolId;
        lastAuditId = result.lastAuditId;
      } catch (err) {
        console.warn("Failed to load history:", err);
        if (gen === selectGenRef.current) setHistoryEventsRef.current([]);
      } finally {
        if (gen === selectGenRef.current) setHistoryLoadingRef.current(false);
      }
      if (gen !== selectGenRef.current) return loadedEvents;
      cursorsRef.current = { afterTool: lastToolId, afterAudit: lastAuditId };
      sseRef.current.connect(id, { afterTool: lastToolId, afterAudit: lastAuditId });
      refreshRunsRef.current();
      return loadedEvents;
    },
    [],
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
      model?: string,
    ) => {
      const resolvedModel = model ?? loadStoredModel();
      setStartModalOpen(false);
      setBusy(true);
      try {
        const result = await apiStartRun(prompt, budget, durationMinutes, baseBranch, resolvedModel, activeRepoFilter);
        refreshRunsRef.current();
        if (result.run_id) {
          const events = await handleSelectRun(result.run_id);
          if (prompt) {
            const hasPrompt = events.some((e) =>
              e._kind === "audit" && (e.data.event_type === "prompt_submitted" || e.data.event_type === "prompt_injected"),
            );
            if (!hasPrompt) addPendingMessage(prompt);
          }
        }
      } catch (err) {
        addEvent({ _kind: "control", text: `Failed to start run: ${err}`, ts: new Date().toISOString() });
      } finally {
        setBusy(false);
      }
    },
    [addEvent, addPendingMessage, handleSelectRun, activeRepoFilter],
  );

  const handleInject = useCallback(
    (prompt: string) => {
      if (!selectedRunId) return;
      const pid = addPendingMessage(prompt);
      apiInjectPrompt(selectedRunId, prompt).catch((e) => {
        markPendingFailed(pid);
        addEvent({ _kind: "control", text: `Inject failed: ${e}`, ts: new Date().toISOString() });
      });
    },
    [selectedRunId, addPendingMessage, markPendingFailed, addEvent],
  );

  const handleRestart = useCallback(
    (prompt: string) => {
      if (!selectedRunId) return;
      const pid = prompt ? addPendingMessage(prompt) : 0;
      resumeAgent(selectedRunId, prompt)
        .then(() => {
          const runId = selectedRunIdRef.current;
          if (runId) {
            sseRef.current.disconnect();
            sseRef.current.clearEvents();
            sseRef.current.connect(runId, cursorsRef.current);
          }
        })
        .catch((e) => {
          if (pid) markPendingFailed(pid);
          addEvent({ _kind: "control", text: `Restart failed: ${e}`, ts: new Date().toISOString() });
        });
    },
    [selectedRunId, addPendingMessage, markPendingFailed, addEvent],
  );

  const handleHeaderKill = useCallback(() => {
    if (!showKillConfirm) {
      setShowKillConfirm(true);
      setTimeout(() => setShowKillConfirm(false), 3000);
      return;
    }
    setBusy(true);
    void controlAction("Kill", killAgent);
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
    pendingMessages,
    runStatus,
    agentHealth,
    activeRunHealth,
    connected,
    connectionState,
    historyTruncated,
    branches,
    isMobile,
    isConfigured,
    atCapacity,
    busy,
    historyLoading,
    activeRepoFilter,
    startModalOpen,
    showKillConfirm,
    onboardingOpen,
    settingsStatus,
    sidebarCollapsed,
    mobilePanel,
    controlsOpen,
    rightPanel,
    showShortcuts,
    setShowShortcuts,
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
