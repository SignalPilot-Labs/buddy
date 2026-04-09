"use client";

import { useState, useCallback, useEffect, useRef, useMemo } from "react";
import Image from "next/image";
import Link from "next/link";
import type { Run, FeedEvent, RunStatus, ToolCall, SettingsStatus, RepoInfo } from "@/lib/types";
import { fetchToolCalls, fetchAuditLog, fetchAgentHealth, fetchBranches, fetchRepos, setActiveRepo } from "@/lib/api";
import { AGENT_HEALTH_POLL_MS, HISTORY_FETCH_LIMIT, TERMINAL_STATUSES } from "@/lib/constants";
import { mergeHistoryWithLive } from "@/lib/eventMerge";
import type { AgentHealth } from "@/lib/api";
import { fetchSettingsStatus } from "@/lib/settings-api";
import { isAtCapacity } from "@/lib/capacity";
import { useRuns } from "@/hooks/useRuns";
import { useSSE } from "@/hooks/useSSE";
import { useMobile } from "@/hooks/useMobile";
import { startRun as apiStartRun, stopAgentInstant, killAgent, pauseAgent, resumeAgent, unlockAgent, injectPrompt as apiInjectPrompt } from "@/lib/api";
import { RunList } from "@/components/sidebar/RunList";
import { EventFeed } from "@/components/feed/EventFeed";
import { CommandInput } from "@/components/controls/CommandInput";
import { StartRunModal } from "@/components/controls/StartRunModal";
import { RateLimitBanner } from "@/components/controls/RateLimitBanner";
import { WorkTree } from "@/components/worktree/WorkTree";
import { StatusBadge } from "@/components/ui/Badge";
import { OnboardingModal } from "@/components/onboarding/OnboardingModal";
import { MobileTab } from "@/components/mobile/MobileTab";
import { MobileControlSheet } from "@/components/mobile/MobileControlSheet";
import { MobileAccessPopover } from "@/components/ui/MobileAccessPopover";
import { ContainerLogs } from "@/components/logs/ContainerLogs";
import { DashboardHeader } from "@/components/header/DashboardHeader";
import { RightPanel } from "@/components/layout/RightPanel";


export default function MonitorPage() {
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
  const [pendingPrompt, setPendingPrompt] = useState<{
    prompt: string; ts: string; clearOn: "prompt_injected"; knownCount: number;
    status: "delivering" | "failed";
  } | null>(null);

  const { events: liveEvents, connected, clearEvents } = useSSE(selectedRunId, refreshRuns);

  // Merge live events into history — SSE post events need to find their pre in history
  const allEvents = useMemo(
    () => mergeHistoryWithLive(historyEvents, liveEvents),
    [historyEvents, liveEvents],
  );

  // Count matching audit events in the live SSE stream to detect delivery
  const pendingClearCount = useMemo(() => {
    if (!pendingPrompt) return 0;
    return liveEvents.filter(
      (e) => e._kind === "audit" && e.data.event_type === pendingPrompt.clearOn,
    ).length;
  }, [liveEvents, pendingPrompt]);

  // Clear pending bubble when backend delivers the matching event, or on run switch
  useEffect(() => {
    if (!pendingPrompt) return;
    if (pendingClearCount > pendingPrompt.knownCount) setPendingPrompt(null);
  }, [pendingClearCount, pendingPrompt]);
  useEffect(() => { setPendingPrompt(null); }, [selectedRunId]);

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

  // Keyboard shortcut: Cmd+B / Ctrl+B to toggle sidebar
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "b") {
        e.preventDefault();
        handleToggleSidebar();
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [handleToggleSidebar]);

  const [busy, setBusy] = useState(false);

  const selectedRunIdRef = useRef<string | null>(null);
  useEffect(() => { selectedRunIdRef.current = selectedRunId; }, [selectedRunId]);

  // Poll agent health — auto-select new runs when they appear, but only if
  // the user isn't already watching an active run.
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

  // Check settings status on mount and load repos
  useEffect(() => {
    fetchSettingsStatus().then((s) => {
      setSettingsStatus(s);
      if (!s.configured) setOnboardingOpen(true);
    });
    fetchRepos().then((r) => {
      setRepos(r);
      if (r.length > 0) {
        // Prefer stored repo if it still exists in the list, otherwise pick first with runs
        const stored = activeRepoFilter;
        const valid = stored && r.some((repo) => repo.repo === stored);
        if (!valid) {
          const withRuns = r.find((repo) => repo.run_count > 0);
          const picked = withRuns?.repo || r[0].repo;
          setActiveRepoFilter(picked);
          try {
            localStorage.setItem("sp_improve_active_repo", picked);
          } catch {}
        }
      }
    });
  }, []);

  // Handle repo switch
  const handleRepoSwitch = useCallback(async (repo: string) => {
    skipLastRunRestoreRef.current = true;
    setActiveRepoFilter(repo || null);
    try {
      if (repo) localStorage.setItem("sp_improve_active_repo", repo);
      else localStorage.removeItem("sp_improve_active_repo");
    } catch {}
    setSelectedRunId(null);
    setSelectedRun(null);
    setHistoryEvents([]);
    clearEvents();
    if (repo) {
      try {
        await setActiveRepo(repo);
      } catch (e) {
        console.error("Failed to set active repo:", e);
      }
    }
    fetchRepos().then(setRepos);
  }, [clearEvents]);

  // Keep selectedRun fresh
  useEffect(() => {
    if (selectedRunId) {
      const found = runs.find((r) => r.id === selectedRunId);
      if (found) setSelectedRun(found);
    }
  }, [runs, selectedRunId]);

  // Load history when selecting a run
  const handleSelectRun = useCallback(
    async (id: string) => {
      const gen = ++selectGenRef.current;
      setSelectedRunId(id);
      localStorage.setItem("autofyn_last_run_id", id);
      setHistoryEvents([]);
      clearEvents();

      try {
        const [tools, audits] = await Promise.all([
          fetchToolCalls(id, HISTORY_FETCH_LIMIT),
          fetchAuditLog(id, HISTORY_FETCH_LIMIT),
        ]);

        if (gen !== selectGenRef.current) return;

        tools.sort((a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime());
        audits.sort((a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime());

        const mergedTools: ToolCall[] = [];

        for (const t of tools) {
          if (t.phase === "pre") {
            mergedTools.push({ ...t });
          } else {
            let matched = false;

            if (t.tool_use_id) {
              for (let j = mergedTools.length - 1; j >= 0; j--) {
                const pre = mergedTools[j];
                if (pre.tool_use_id === t.tool_use_id && pre.phase === "pre") {
                  pre.output_data = t.output_data;
                  pre.duration_ms = t.duration_ms;
                  pre.phase = "post";
                  matched = true;
                  break;
                }
              }
            }

            if (!matched) {
              for (let j = mergedTools.length - 1; j >= 0; j--) {
                const pre = mergedTools[j];
                if (
                  pre.tool_name === t.tool_name &&
                  pre.phase === "pre" &&
                  !pre.output_data
                ) {
                  pre.output_data = t.output_data;
                  pre.duration_ms = t.duration_ms;
                  pre.phase = "post";
                  matched = true;
                  break;
                }
              }
            }

            if (!matched) {
              mergedTools.push({ ...t });
            }
          }
        }

        const toolEvents: FeedEvent[] = mergedTools.map((t) => ({
          _kind: "tool" as const,
          data: t,
        }));

        const auditEvents: FeedEvent[] = [];
        for (const a of audits) {
          const details = typeof a.details === "string" ? JSON.parse(a.details) : a.details || {};
          if (a.event_type === "llm_text" || a.event_type === "llm_thinking") {
            const kind = a.event_type === "llm_text" ? "llm_text" as const : "llm_thinking" as const;
            const role = details.agent_role || "worker";
            const last = auditEvents[auditEvents.length - 1];
            if (last && last._kind === kind && last.agent_role === role) {
              auditEvents[auditEvents.length - 1] = { ...last, text: last.text + (details.text || "") };
            } else {
              auditEvents.push({ _kind: kind, text: details.text || "", ts: a.ts, agent_role: role });
            }
          } else {
            auditEvents.push({ _kind: "audit" as const, data: { ...a, details } });
          }
        }

        const getTs = (e: FeedEvent): string =>
          e._kind === "tool" ? e.data.ts
          : e._kind === "audit" ? e.data.ts
          : e._kind === "usage" ? e.data.ts
          : e.ts;
        const merged = [...toolEvents, ...auditEvents].sort((a, b) =>
          new Date(getTs(a)).getTime() - new Date(getTs(b)).getTime()
        );

        setHistoryEvents(merged);
      } catch (err) {
        console.warn("Failed to load historical events, SSE will provide live data:", err);
      }

      refreshRuns();
    },
    [clearEvents, refreshRuns]
  );

  // Auto-select: restore last viewed run on initial load, most recent on repo switch
  useEffect(() => {
    if (!selectedRunId && runs.length > 0) {
      // Guard against stale runs from the previous repo — if a filter is active but
      // none of the current runs match it, the new fetch hasn't arrived yet; skip.
      if (activeRepoFilter && !runs.some((r) => r.github_repo === activeRepoFilter)) {
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
      const active = runs.find((r) => ["running", "paused", "rate_limited"].includes(r.status));
      handleSelectRun(active?.id || runs[0].id);
    }
  }, [runs, selectedRunId, handleSelectRun, activeRepoFilter]);

  // Start a new run
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
        if (result.run_id) {
          handleSelectRun(result.run_id);
        }
      } catch (err) {
        addEvent({
          _kind: "control",
          text: `Failed to start run: ${err}`,
          ts: new Date().toISOString(),
        });
      } finally {
        setBusy(false);
      }
    },
    [addEvent, handleSelectRun, refreshRuns, activeRepoFilter],
  );

  const runStatus: RunStatus | null =
    (selectedRun?.status as RunStatus) || null;

  const handleInject = useCallback(
    (prompt: string) => {
      if (!selectedRunId) return;
      setPendingPrompt({ prompt, ts: new Date().toISOString(), clearOn: "prompt_injected", knownCount: pendingClearCount, status: "delivering" });
      apiInjectPrompt(selectedRunId, prompt).catch((e) => {
        setPendingPrompt(null);
        addEvent({ _kind: "control", text: `Inject failed: ${e}`, ts: new Date().toISOString() });
      });
    },
    [selectedRunId, pendingClearCount, addEvent],
  );

  const handleRestart = useCallback(
    (prompt: string) => {
      if (!selectedRunId) return;
      if (prompt) {
        setPendingPrompt({ prompt, ts: new Date().toISOString(), clearOn: "prompt_injected", knownCount: pendingClearCount, status: "delivering" });
      }
      resumeAgent(selectedRunId).catch((e) => {
        setPendingPrompt(null);
        addEvent({ _kind: "control", text: `Restart failed: ${e}`, ts: new Date().toISOString() });
      });
    },
    [selectedRunId, pendingClearCount, addEvent],
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

  // Mark pending bubble as failed when run reaches a terminal state
  useEffect(() => {
    if (!pendingPrompt || pendingPrompt.status === "failed") return;
    if (runStatus && TERMINAL_STATUSES.has(runStatus)) {
      setPendingPrompt((prev) => prev ? { ...prev, status: "failed" } : null);
    }
  }, [runStatus, pendingPrompt]);

  const agentReachable = agentHealth != null && agentHealth.status !== "unreachable";
  const agentIdle = agentHealth?.status === "idle";
  const agentBootstrapping = agentHealth?.status === "bootstrapping";
  const isConfigured = settingsStatus?.configured ?? false;
  const atCapacity = isAtCapacity(agentHealth);
  const activeRunHealth = selectedRunId
    ? agentHealth?.runs.find((r) => r.run_id === selectedRunId)
    : undefined;

  return (
    <div className="h-screen flex flex-col bg-[var(--color-bg)]">
      {/* ── Mobile Top Bar ── */}
      <header className="mobile-top-bar items-center gap-2 px-3 py-2 border-b border-[#1a1a1a] bg-[#0a0a0a] header-glow safe-area-top">
        {/* Logo */}
        <div className="relative flex items-center justify-center h-7 w-7">
          <svg width="28" height="28" viewBox="0 0 28 28" className="absolute">
            <circle cx="14" cy="14" r="12" fill="none"
              stroke={runStatus === "running" ? "rgba(0,255,136,0.2)" : "rgba(255,255,255,0.06)"}
              strokeWidth="1" strokeDasharray="4 3"
              style={runStatus === "running" ? { animation: "spin 8s linear infinite" } : undefined}
            />
          </svg>
          <Image src="/logo.svg" alt="AutoFyn" width={18} height={18} className="relative z-[1]" />
        </div>

        <div>
          <h1 className="text-[12px] font-bold text-[#e8e8e8] tracking-tight">AutoFyn</h1>
          <p className="text-[8px] text-[#777] tracking-[0.1em] uppercase -mt-0.5">Monitor</p>
        </div>

        <div className="flex-1" />

        {/* Agent health dot */}
        <span
          className={`h-2 w-2 rounded-full ${
            agentReachable ? (agentIdle ? "bg-[#00ff88]/60" : "bg-[#00ff88]") : "bg-[#ff4444]/60"
          }`}
          style={!agentIdle && agentReachable ? { boxShadow: "0 0 4px rgba(0,255,136,0.3)" } : undefined}
        />

        {/* Mobile access QR */}
        <MobileAccessPopover />

        {/* Run status */}
        {selectedRun && <StatusBadge status={selectedRun.status as RunStatus} size="md" />}

        {/* Settings */}
        <Link href="/settings" className="p-2 rounded hover:bg-white/[0.04] text-[#888] hover:text-[#ccc] transition-colors">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
          </svg>
        </Link>
      </header>

      {/* ── Desktop Header ── */}
      <DashboardHeader
        repos={repos}
        activeRepo={activeRepoFilter}
        onRepoSwitch={handleRepoSwitch}
        selectedRun={selectedRun}
        runStatus={runStatus}
        agentHealth={agentHealth}
        activeRunHealth={activeRunHealth}
        isConfigured={isConfigured}
        atCapacity={atCapacity}
        busy={busy}
        showKillConfirm={showKillConfirm}
        onStop={() => controlAction("Stop", stopAgentInstant)}
        onKill={handleHeaderKill}
        onNewRun={() => { fetchBranches(activeRepoFilter || undefined).then(setBranches); setStartModalOpen(true); }}
        sidebarCollapsed={sidebarCollapsed}
        onToggleSidebar={handleToggleSidebar}
      />


      {/* Start Run Modal */}
      <StartRunModal
        open={startModalOpen}
        onClose={() => setStartModalOpen(false)}
        onStart={handleStartRun}
        busy={busy}
        branches={branches}
        activeRepo={activeRepoFilter}
      />

      {/* Onboarding Modal */}
      {settingsStatus && (
        <OnboardingModal
          open={onboardingOpen}
          onComplete={() => {
            setOnboardingOpen(false);
            fetchSettingsStatus().then(setSettingsStatus);
            fetchRepos().then((r) => {
              setRepos(r);
              if (r.length > 0) setActiveRepoFilter(r[0].repo);
            });
          }}
          initialStatus={settingsStatus}
        />
      )}

      {/* Rate Limit Banner */}
      {selectedRun?.status === "rate_limited" && selectedRun.rate_limit_resets_at && (
        <RateLimitBanner
          resetsAt={selectedRun.rate_limit_resets_at}
          onRetry={() => {
            if (!selectedRun) return;
            handleStartRun(
              selectedRun.custom_prompt || undefined,
              0,
              selectedRun.duration_minutes || 0,
              selectedRun.base_branch || "main",
            );
          }}
          busy={busy}
        />
      )}

      {/* Main Content */}
      {!isMobile && (
        <div className="flex flex-1 min-h-0">
          {/* Left sidebar - Run list */}
          <div className={`desktop-sidebar overflow-hidden transition-all duration-200 ${sidebarCollapsed ? "w-[48px]" : "w-[260px]"}`}>
            <RunList
              runs={runs}
              activeId={selectedRunId}
              onSelect={(id) => { handleSelectRun(id); }}
              loading={runsLoading}
              collapsed={sidebarCollapsed}
            />
          </div>

          {/* Center - Feed */}
          <main className="flex-1 flex flex-col min-h-0 min-w-0">
            <EventFeed events={allEvents} runActive={runStatus === "running" || runStatus === "paused" || runStatus === "rate_limited"} runPaused={runStatus === "paused"} pendingPrompt={pendingPrompt} />
            <CommandInput
              runId={selectedRunId}
              status={runStatus}
              run={selectedRun}
              connected={connected}
              events={allEvents}
              busy={busy}
              onPause={() => controlAction("Pause", pauseAgent)}
              onResume={() => controlAction("Resume", resumeAgent)}
              onInject={handleInject}
              onRestart={handleRestart}
            />
          </main>

          {/* Right sidebar - Changes / Logs */}
          {selectedRunId && (
            <RightPanel
              runId={selectedRunId}
              events={allEvents}
              activeTab={rightPanel}
              onTabChange={setRightPanel}
            />
          )}
        </div>
      )}

      {/* Mobile content */}
      {isMobile && (
        <div className="flex-1 flex flex-col min-h-0 pb-14">
          {mobilePanel === "runs" && (
            <RunList
              runs={runs}
              activeId={selectedRunId}
              onSelect={(id) => { handleSelectRun(id); setMobilePanel("feed"); }}
              loading={runsLoading}
            />
          )}
          {mobilePanel === "feed" && (
            <>
              <EventFeed events={allEvents} runActive={runStatus === "running" || runStatus === "paused" || runStatus === "rate_limited"} runPaused={runStatus === "paused"} pendingPrompt={pendingPrompt} />
              <CommandInput
                runId={selectedRunId}
                status={runStatus}
                run={selectedRun}
                connected={connected}
                events={allEvents}
                busy={busy}
                onPause={() => controlAction("Pause", pauseAgent)}
                onResume={() => controlAction("Resume", resumeAgent)}
                onInject={handleInject}
                onRestart={handleRestart}
              />
            </>
          )}
          {mobilePanel === "changes" && (
            <WorkTree events={allEvents} runId={selectedRunId} mobile />
          )}
          {mobilePanel === "logs" && (
            <ContainerLogs runId={selectedRunId} />
          )}
        </div>
      )}

      {/* Mobile bottom tab bar */}
      <nav className="mobile-bottom-bar">
        <MobileTab
          icon={<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M4 6h16M4 12h16M4 18h10" /></svg>}
          label="Runs"
          active={mobilePanel === "runs"}
          onClick={() => setMobilePanel("runs")}
          badge={runs.length > 0 ? runs.length : null}
        />
        <MobileTab
          icon={<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M12 20V10M18 20V4M6 20v-4" /></svg>}
          label="Feed"
          active={mobilePanel === "feed"}
          onClick={() => setMobilePanel("feed")}
          badge={allEvents.length > 0 ? allEvents.length : null}
        />
        <MobileTab
          icon={<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6" /></svg>}
          label="Changes"
          active={mobilePanel === "changes"}
          onClick={() => setMobilePanel("changes")}
        />
        <MobileTab
          icon={<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="3" y="3" width="18" height="18" rx="2" /><path d="M7 8l3 3-3 3" /><line x1="11" y1="16" x2="17" y2="16" /></svg>}
          label="Logs"
          active={mobilePanel === "logs"}
          onClick={() => setMobilePanel("logs")}
        />
        <MobileTab
          icon={<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" /></svg>}
          label="Controls"
          active={controlsOpen}
          onClick={() => setControlsOpen(true)}
        />
      </nav>

      {/* Mobile Control Sheet */}
      <MobileControlSheet
        open={controlsOpen}
        onClose={() => setControlsOpen(false)}
        status={runStatus}
        onPause={() => selectedRunId && pauseAgent(selectedRunId)}
        onResume={() => selectedRunId && resumeAgent(selectedRunId)}
        onStop={() => selectedRunId && stopAgentInstant(selectedRunId)}
        onKill={() => selectedRunId && killAgent(selectedRunId)}
        onUnlock={() => selectedRunId && unlockAgent(selectedRunId)}
        onToggleInject={() => setMobilePanel("feed")}
        busy={busy}
        repos={repos}
        activeRepo={activeRepoFilter}
        onRepoSelect={handleRepoSwitch}
        onNewRun={() => { fetchBranches(activeRepoFilter || undefined).then(setBranches); setStartModalOpen(true); }}
        isConfigured={isConfigured}
      />
    </div>
  );
}
