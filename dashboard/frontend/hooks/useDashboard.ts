"use client";

import { useState, useCallback, useEffect, useRef, useMemo } from "react";
import type { Run, FeedEvent, RunStatus, SettingsStatus, RepoInfo } from "@/lib/types";
import {
  fetchAgentHealth,
  fetchRepos,
  setActiveRepo,
  killAgent,
} from "@/lib/api";
import { useKeyboardShortcuts } from "@/hooks/useKeyboardShortcuts";
import type { AgentHealth, HealthRunEntry } from "@/lib/api";
import type { DashboardState } from "@/hooks/dashboardTypes";
import { AGENT_HEALTH_POLL_MS, TERMINAL_STATUSES } from "@/lib/constants";
import { fetchSettingsStatus } from "@/lib/settings-api";
import { isAtCapacity } from "@/lib/capacity";
import { loadRunHistory } from "@/lib/loadRunHistory";
import { useRuns } from "@/hooks/useRuns";
import { useSSE } from "@/hooks/useSSE";
import { useMobile } from "@/hooks/useMobile";
import { getTs } from "@/lib/groupEvents";
import { useRunActions } from "@/hooks/useRunActions";

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
  const [historyLoading, setHistoryLoading] = useState(false);
  const [showShortcuts, setShowShortcuts] = useState(false);

  const selectedRunIdRef = useRef<string | null>(null);
  useEffect(() => { selectedRunIdRef.current = selectedRunId; }, [selectedRunId]);
  const cursorsRef = useRef({ afterTool: 0, afterAudit: 0 });

  // Declared early so handleSessionResumed and handleSelectRun can reference it;
  // updated after useRunActions is called.
  const clearPendingMessagesRef = useRef<() => void>(() => undefined);

  const handleSessionResumed = useCallback(() => {
    const runId = selectedRunIdRef.current;
    if (!runId) return;
    sseRef.current.disconnect();
    clearPendingMessagesRef.current();
    setHistoryLoading(true);
    loadRunHistory(runId).then(({ events, lastToolId, lastAuditId }) => {
      setHistoryEvents(events);
      cursorsRef.current = { afterTool: lastToolId, afterAudit: lastAuditId };
      sseRef.current.clearEvents();
      sseRef.current.connect(runId, { afterTool: lastToolId, afterAudit: lastAuditId });
      setHistoryLoading(false);
    }).catch((err) => {
      setHistoryLoading(false);
      setHistoryEvents((prev) => [
        ...prev,
        { _kind: "control", text: `Session resume failed: ${err}`, ts: new Date().toISOString() },
      ]);
    });
  }, []);

  // handleRunEnded is defined after useRunActions; use a ref to break the cycle
  const handleRunEndedRef = useRef<() => void>(() => undefined);

  const { events: liveEvents, connected, clearEvents, connect: sseConnect, disconnect: sseDisconnect } = useSSE(
    useCallback(() => handleRunEndedRef.current(), []),
    handleSessionResumed,
  );
  const sseRef = useRef({ connect: sseConnect, disconnect: sseDisconnect, clearEvents });
  sseRef.current = { connect: sseConnect, disconnect: sseDisconnect, clearEvents };

  const addEvent = useCallback((event: FeedEvent) => {
    setHistoryEvents((prev) => [...prev, event]);
  }, []);

  // Derive confirmed prompts from liveEvents to pass into useRunActions
  const confirmedPrompts = useMemo(() => {
    return liveEvents
      .filter(
        (e) =>
          e._kind === "audit" &&
          (e.data.event_type === "prompt_injected" ||
            e.data.event_type === "prompt_submitted"),
      )
      .map((e) => {
        if (e._kind !== "audit") return "";
        return String(e.data.details.prompt || "");
      })
      .filter((t) => t.length > 0);
  }, [liveEvents]);

  const handleSelectRun = useCallback(
    async (id: string): Promise<FeedEvent[]> => {
      const gen = ++selectGenRef.current;
      sseRef.current.disconnect();
      setSelectedRunId(id);
      clearPendingMessagesRef.current();
      localStorage.setItem("autofyn_last_run_id", id);
      setHistoryLoading(true);
      sseRef.current.clearEvents();
      let lastToolId = 0;
      let lastAuditId = 0;
      let loadedEvents: FeedEvent[] = [];
      try {
        const result = await loadRunHistory(id);
        if (gen !== selectGenRef.current) return loadedEvents;
        setHistoryEvents(result.events);
        loadedEvents = result.events;
        lastToolId = result.lastToolId;
        lastAuditId = result.lastAuditId;
      } catch (err) {
        console.warn("Failed to load history:", err);
        if (gen === selectGenRef.current) setHistoryEvents([]);
      } finally {
        if (gen === selectGenRef.current) setHistoryLoading(false);
      }
      if (gen !== selectGenRef.current) return loadedEvents;
      cursorsRef.current = { afterTool: lastToolId, afterAudit: lastAuditId };
      sseRef.current.connect(id, { afterTool: lastToolId, afterAudit: lastAuditId });
      refreshRuns();
      return loadedEvents;
    },
    [refreshRuns],
  );

  const runActions = useRunActions({
    selectedRunId,
    selectedRunIdRef,
    cursorsRef,
    sseRef,
    refreshRuns,
    addEvent,
    activeRepoFilter,
    confirmedPrompts,
    handleSelectRun,
    setStartModalOpen,
  });

  // Keep clearPendingMessagesRef up to date after useRunActions is initialized
  clearPendingMessagesRef.current = runActions.clearPendingMessages;

  const handleRunEnded = useCallback(() => {
    runActions.onRunEnded();
  }, [runActions]);
  handleRunEndedRef.current = handleRunEnded;

  const allEvents = useMemo(() => {
    if (liveEvents.length === 0) return historyEvents;
    const merged = [...historyEvents, ...liveEvents];
    const lastHistory = historyEvents[historyEvents.length - 1];
    const firstLive = liveEvents[0];
    if (lastHistory && firstLive && getTs(lastHistory) > getTs(firstLive)) {
      merged.sort((a, b) => getTs(a) - getTs(b));
    }
    return merged;
  }, [historyEvents, liveEvents]);

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
    busy: runActions.busy,
  });

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
    runActions.clearPendingMessages();
    sseRef.current.clearEvents();
    setBranches([]);
    if (repo) {
      try { await setActiveRepo(repo); } catch (e) { console.error("Failed to set active repo:", e); }
    }
    fetchRepos().then(setRepos);
  }, [runActions]);

  useEffect(() => {
    if (selectedRunId) {
      const found = runs.find((r) => r.id === selectedRunId);
      if (found) {
        setSelectedRun(found);
        if (TERMINAL_STATUSES.has(found.status as RunStatus)) runActions.setBusy(false);
      }
    }
  }, [runs, selectedRunId, runActions]);

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

  const handleHeaderKill = useCallback(() => {
    if (!showKillConfirm) {
      setShowKillConfirm(true);
      setTimeout(() => setShowKillConfirm(false), 3000);
      return;
    }
    runActions.setBusy(true);
    void controlAction("Kill", killAgent);
    setShowKillConfirm(false);
  }, [showKillConfirm, controlAction, runActions]);

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
    pendingMessages: runActions.pendingMessages,
    runStatus,
    agentHealth,
    activeRunHealth,
    connected,
    branches,
    isMobile,
    isConfigured,
    atCapacity,
    busy: runActions.busy,
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
    handleStartRun: runActions.handleStartRun,
    handleInject: runActions.handleInject,
    handleRestart: runActions.handleRestart,
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
