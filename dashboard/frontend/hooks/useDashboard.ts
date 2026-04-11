"use client";

import { useState, useCallback, useEffect, useRef, useMemo } from "react";
import type { Run, FeedEvent, RunStatus, SettingsStatus, RepoInfo, PendingMessage } from "@/lib/types";
import {
  fetchAgentHealth,
  fetchRepos,
  setActiveRepo,
  startRun as apiStartRun,
  killAgent,
  resumeAgent,
  injectPrompt as apiInjectPrompt,
  pollEvents,
} from "@/lib/api";
import { useKeyboardShortcuts } from "@/hooks/useKeyboardShortcuts";
import type { AgentHealth, HealthRunEntry } from "@/lib/api";
import type { DashboardState } from "@/hooks/dashboardTypes";
import { AGENT_HEALTH_POLL_MS, TERMINAL_STATUSES, loadStoredModel } from "@/lib/constants";
import { getFeedEventTs } from "@/lib/groupEvents";
import { fetchSettingsStatus } from "@/lib/settings-api";
import { isAtCapacity } from "@/lib/capacity";
import { loadRunHistory } from "@/lib/loadRunHistory";
import { mergeToolEvent } from "@/lib/eventMerge";
import { useRuns } from "@/hooks/useRuns";
import { useSSE } from "@/hooks/useSSE";
import { useMobile } from "@/hooks/useMobile";

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
  const [historyLoading, setHistoryLoading] = useState(false);
  const [pendingMessages, setPendingMessages] = useState<PendingMessage[]>([]);
  const [showShortcuts, setShowShortcuts] = useState(false);

  const selectedRunIdRef = useRef<string | null>(null);
  useEffect(() => { selectedRunIdRef.current = selectedRunId; }, [selectedRunId]);
  const cursorsRef = useRef({ afterTool: 0, afterAudit: 0 });

  const applyCatchUpEvents = useCallback((runId: string, afterTool: number, afterAudit: number): void => {
    pollEvents(runId, afterTool, afterAudit).then((result) => {
      if (result.tool_calls.length === 0 && result.audit_events.length === 0) return;
      let newAfterTool = afterTool;
      let newAfterAudit = afterAudit;
      setHistoryEvents((prev) => {
        let next = prev;
        for (const tc of result.tool_calls) {
          newAfterTool = Math.max(newAfterTool, tc.id ?? 0);
          next = mergeToolEvent(next, tc);
        }
        for (const ae of result.audit_events) {
          newAfterAudit = Math.max(newAfterAudit, ae.id ?? 0);
          const details = typeof ae.details === "string" ? JSON.parse(ae.details) : ae.details || {};
          next = [...next, { _kind: "audit", data: { ...ae, details } }];
          if (ae.event_type === "session_resumed") {
            // session_resumed during catch-up means we need a full reload — handled by SSE event
          }
        }
        return next;
      });
      cursorsRef.current = { afterTool: newAfterTool, afterAudit: newAfterAudit };
    }).catch((err) => {
      console.warn("Catch-up poll failed:", err);
    });
  }, []);

  const handleRunEnded = useCallback(() => {
    refreshRuns();
    setBusy(false);
    setPendingMessages((prev) => {
      if (prev.length === 0) return prev;
      return prev.map((m) => m.status === "pending" ? { ...m, status: "failed" } : m);
    });
  }, [refreshRuns]);

  const handleSessionResumed = useCallback(() => {
    const runId = selectedRunIdRef.current;
    if (!runId) return;
    sseRef.current.disconnect();
    setPendingMessages([]);
    setHistoryLoading(true);
    loadRunHistory(runId).then(({ events, lastToolId, lastAuditId }) => {
      setHistoryEvents(events);
      cursorsRef.current = { afterTool: lastToolId, afterAudit: lastAuditId };
      sseRef.current.clearEvents();
      sseRef.current.connect(runId, { afterTool: lastToolId, afterAudit: lastAuditId }, () => {
        applyCatchUpEvents(runId, lastToolId, lastAuditId);
      });
      setHistoryLoading(false);
    }).catch((err) => {
      setHistoryLoading(false);
      setHistoryEvents((prev) => [
        ...prev,
        { _kind: "control", text: `Session resume failed: ${err}`, ts: new Date().toISOString() },
      ]);
    });
  }, [applyCatchUpEvents]);

  const { events: liveEvents, connected, clearEvents, connect: sseConnect, disconnect: sseDisconnect } = useSSE(handleRunEnded, handleSessionResumed);
  const sseRef = useRef({ connect: sseConnect, disconnect: sseDisconnect, clearEvents });
  sseRef.current = { connect: sseConnect, disconnect: sseDisconnect, clearEvents };

  // Clear pending messages by prompt text matching when prompt events arrive via SSE
  const confirmedPromptsRef = useRef<Set<string>>(new Set());
  useEffect(() => {
    // Reset when liveEvents is cleared (run switch, session resumed, etc.)
    if (liveEvents.length === 0) {
      confirmedPromptsRef.current = new Set();
      return;
    }
    const confirmedTexts = liveEvents
      .filter((e) => e._kind === "audit" && (e.data.event_type === "prompt_injected" || e.data.event_type === "prompt_submitted"))
      .map((e) => {
        if (e._kind !== "audit") return "";
        return String(e.data.details.prompt || "");
      })
      .filter((t) => t.length > 0);
    const newConfirmed = confirmedTexts.filter((t) => !confirmedPromptsRef.current.has(t));
    if (newConfirmed.length === 0) return;
    for (const t of newConfirmed) confirmedPromptsRef.current.add(t);
    const confirmedSet = new Set(newConfirmed);
    setPendingMessages((prev) =>
      prev.filter((m) => m.status !== "pending" || !confirmedSet.has(m.prompt)),
    );
  }, [liveEvents]);

  const allEvents = useMemo(
    () => [...historyEvents, ...liveEvents].sort((a, b) => getFeedEventTs(a) - getFeedEventTs(b)),
    [historyEvents, liveEvents],
  );

  const addEvent = useCallback((event: FeedEvent) => {
    setHistoryEvents((prev) => [...prev, event]);
  }, []);

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
    setPendingMessages([]);
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
      setPendingMessages([]);
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
      sseRef.current.connect(id, { afterTool: lastToolId, afterAudit: lastAuditId }, () => {
        applyCatchUpEvents(id, lastToolId, lastAuditId);
      });
      refreshRuns();
      return loadedEvents;
    },
    [refreshRuns, applyCatchUpEvents],
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

  const addPendingMessage = useCallback(
    (prompt: string): number => {
      const id = -Date.now();
      setPendingMessages((prev) => [...prev, { id, prompt, ts: new Date().toISOString(), status: "pending" }]);
      return id;
    },
    [],
  );

  const markPendingFailed = useCallback(
    (id: number) => {
      setPendingMessages((prev) => prev.map((m) => m.id === id ? { ...m, status: "failed" } : m));
    },
    [],
  );

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
        refreshRuns();
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
    [addEvent, addPendingMessage, handleSelectRun, refreshRuns, activeRepoFilter],
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
          // Run was terminal → SSE was disconnected. Reconnect so new events arrive.
          const runId = selectedRunIdRef.current;
          if (runId) {
            const { afterTool, afterAudit } = cursorsRef.current;
            sseRef.current.disconnect();
            sseRef.current.clearEvents();
            sseRef.current.connect(runId, cursorsRef.current, () => {
              applyCatchUpEvents(runId, afterTool, afterAudit);
            });
          }
        })
        .catch((e) => {
          if (pid) markPendingFailed(pid);
          addEvent({ _kind: "control", text: `Restart failed: ${e}`, ts: new Date().toISOString() });
        });
    },
    [selectedRunId, addPendingMessage, markPendingFailed, addEvent, applyCatchUpEvents],
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
