"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import type { Run, FeedEvent, RunStatus, SettingsStatus, RepoInfo } from "@/lib/types";
import {
  fetchAgentHealth,
  fetchRepos,
  setActiveRepo,
} from "@/lib/api";
import { useKeyboardShortcuts } from "@/hooks/useKeyboardShortcuts";
import type { AgentHealth } from "@/lib/api";
import type { DashboardState } from "@/hooks/dashboardTypes";
import { AGENT_HEALTH_POLL_MS, TERMINAL_STATUSES, isActiveStatus } from "@/lib/constants";
import { fetchSettingsStatus } from "@/lib/settings-api";
import { isAtCapacity } from "@/lib/capacity";
import { loadRunHistory } from "@/lib/loadRunHistory";
import { useRuns } from "@/hooks/useRuns";
import { useSSE } from "@/hooks/useSSE";
import { useMobile } from "@/hooks/useMobile";
import { useEventState } from "@/hooks/useEventState";
import { useRunActions } from "@/hooks/useRunActions";

export function useDashboard(): DashboardState {
  const [activeRepoFilter, setActiveRepoFilter] = useState<string | null>(() => {
    try { return localStorage.getItem("sp_improve_active_repo") || null; } catch { return null; }
  });
  const [repos, setRepos] = useState<RepoInfo[]>([]);
  const { runs, loading: runsLoading, refresh: refreshRuns } = useRuns(activeRepoFilter);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [selectedRun, setSelectedRun] = useState<Run | null>(null);
  const [startModalOpen, setStartModalOpen] = useState(false);
  const [agentHealth, setAgentHealth] = useState<AgentHealth | null>(null);
  const [branches, setBranches] = useState<string[]>(["main"]);
  const [settingsStatus, setSettingsStatus] = useState<SettingsStatus | null>(null);
  const [onboardingOpen, setOnboardingOpen] = useState(false);
  const selectGenRef = useRef(0);
  const resumeGenRef = useRef(0);
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
  const refreshRunsRef = useRef(refreshRuns);
  refreshRunsRef.current = refreshRuns;
  const setHistoryEventsRef = useRef<(events: FeedEvent[]) => void>(() => undefined);
  const setHistoryLoadingRef = useRef<(v: boolean) => void>(() => undefined);
  const setHistoryTruncatedRef = useRef<(v: boolean) => void>(() => undefined);
  const addEventRef = useRef<(event: FeedEvent) => void>(() => undefined);

  const handleRunEnded = useCallback(() => {
    refreshRunsRef.current();
    setBusy(false);
  }, []);

  const handleSessionResumed = useCallback(() => {
    const runId = selectedRunIdRef.current;
    if (!runId) return;
    const gen = ++resumeGenRef.current;
    sseRef.current.disconnect();
    setHistoryLoadingRef.current(true);
    loadRunHistory(runId).then(({ events, lastToolId, lastAuditId, truncated }) => {
      if (gen !== resumeGenRef.current) return;
      setHistoryEventsRef.current(events);
      setHistoryTruncatedRef.current(truncated);
      cursorsRef.current = { afterTool: lastToolId, afterAudit: lastAuditId };
      sseRef.current.clearEvents();
      sseRef.current.connect(runId, { afterTool: lastToolId, afterAudit: lastAuditId });
      setHistoryLoadingRef.current(false);
    }).catch((err) => {
      if (gen !== resumeGenRef.current) return;
      setHistoryLoadingRef.current(false);
      addEventRef.current({ _kind: "control", text: `Session resume failed: ${err}`, ts: new Date().toISOString() });
    });
  }, []);

  const { events: liveEvents, connected, connectionState, clearEvents, connect: sseConnect, disconnect: sseDisconnect } = useSSE(handleRunEnded, handleSessionResumed);
  const sseRef = useRef({ connect: sseConnect, disconnect: sseDisconnect, clearEvents });
  sseRef.current = { connect: sseConnect, disconnect: sseDisconnect, clearEvents };

  const evState = useEventState(liveEvents);
  const { allEvents, historyLoading, historyTruncated, addEvent } = evState;

  setHistoryEventsRef.current = evState.setHistoryEvents;
  setHistoryLoadingRef.current = evState.setHistoryLoading;
  setHistoryTruncatedRef.current = evState.setHistoryTruncated;
  addEventRef.current = addEvent;

  const handleToggleSidebar = useCallback(() => {
    setSidebarCollapsed((prev) => {
      const next = !prev;
      try { localStorage.setItem("autofyn_sidebar_collapsed", String(next)); } catch {}
      return next;
    });
  }, []);

  const runStatus: RunStatus | null = (selectedRun?.status as RunStatus) || null;

  const handleSelectRun = useCallback(
    async (id: string): Promise<FeedEvent[]> => {
      const gen = ++selectGenRef.current;
      sseRef.current.disconnect();
      setSelectedRunId(id);
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

  const runActions = useRunActions({
    selectedRunId,
    selectedRunIdRef,
    addEvent,
    sseRef,
    cursorsRef,
    refreshRunsRef,
    handleSelectRun,
    activeRepoFilter,
    setStartModalOpen,
    setBusy,
  });

  const { controlAction } = runActions;

  useKeyboardShortcuts({
    handleToggleSidebar,
    setStartModalOpen,
    showShortcuts,
    setShowShortcuts,
    controlAction,
    runStatus,
    busy,
    activeRepoFilter,
  });

  // Health poll: only updates agentHealth state and triggers runs refresh
  // when a new run appears. Run selection is handled by the auto-selection
  // effect below — keeping selection logic in one place prevents races
  // (e.g. health poll re-selecting a run that handleStartRun just selected).
  useEffect(() => {
    const check = async () => {
      const h = await fetchAgentHealth();
      setAgentHealth((prev) => {
        const prevIds = new Set(prev?.runs.map((r) => r.run_id) ?? []);
        const hasNewRun = h.runs.some((r) => !prevIds.has(r.run_id));
        const selectedId = selectedRunIdRef.current;
        const selectedWasActive = selectedId !== null && prev?.runs.some((r) => r.run_id === selectedId);
        const selectedGone = selectedWasActive === true && !h.runs.some((r) => r.run_id === selectedId);
        if (hasNewRun || selectedGone) {
          refreshRunsRef.current();
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
        if (!stored) return; // User never picked a repo — don't force one
        const valid = r.some((repo) => repo.repo === stored);
        if (!valid) {
          // Stored repo no longer exists — fall back to one with runs
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
    selectGenRef.current += 1;
    setSelectedRunId(null);
    setSelectedRun(null);
    setHistoryEventsRef.current([]);
    sseRef.current.clearEvents();
    setBranches(["main"]);
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

  // Auto-selection: pick a run ONLY when none is selected. Never yank the
  // user away from a run they deliberately clicked — even if it's terminal
  // and an active run exists. The user can click the active run themselves.
  useEffect(() => {
    if (selectedRunId || runs.length === 0) return;
    if (activeRepoFilter && !runs.some((r) => r.github_repo === activeRepoFilter)) return;

    const active = runs.find((r) => isActiveStatus(r.status));
    if (active) {
      handleSelectRun(active.id);
      return;
    }
    const skipRestore = skipLastRunRestoreRef.current;
    skipLastRunRestoreRef.current = false;
    if (!skipRestore) {
      const lastRunId = localStorage.getItem("autofyn_last_run_id");
      if (lastRunId && runs.some((r) => r.id === lastRunId)) {
        handleSelectRun(lastRunId);
        return;
      }
    }
    handleSelectRun(runs[0].id);
  }, [runs, selectedRunId, handleSelectRun, activeRepoFilter]);

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
    onboardingOpen,
    settingsStatus,
    sidebarCollapsed,
    mobilePanel,
    controlsOpen,
    rightPanel,
    showShortcuts,
    setShowShortcuts,
    handleToggleSidebar,
    handleRepoSwitch,
    handleSelectRun,
    setStartModalOpen,
    setOnboardingOpen,
    setMobilePanel,
    setControlsOpen,
    setRightPanel,
    setBranches,
    setSettingsStatus,
    setRepos,
    ...runActions,
  };
}
