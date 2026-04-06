"use client";

import { useState, useCallback, useEffect, useRef, useMemo } from "react";
import { motion } from "framer-motion";
import Image from "next/image";
import Link from "next/link";
import type { Run, FeedEvent, RunStatus, ToolCall, SettingsStatus, RepoInfo } from "@/lib/types";
import { fetchToolCalls, fetchAuditLog, fetchAgentHealth, fetchBranches, fetchRepos, setActiveRepo, fetchRuns } from "@/lib/api";
import { AGENT_HEALTH_POLL_MS } from "@/lib/constants";
import { mergeHistoryWithLive } from "@/lib/eventMerge";
import type { AgentHealth } from "@/lib/api";
import { fetchSettingsStatus } from "@/lib/settings-api";
import { useRuns } from "@/hooks/useRuns";
import { useSSE } from "@/hooks/useSSE";
import { useParallelRuns } from "@/hooks/useParallelRuns";
import { useMobile } from "@/hooks/useMobile";
import { RunList } from "@/components/sidebar/RunList";
import { EventFeed } from "@/components/feed/EventFeed";
import { ControlBar } from "@/components/controls/ControlBar";
import { InjectPanel } from "@/components/controls/InjectPanel";
import { StartRunModal } from "@/components/controls/StartRunModal";
import { StatsBar } from "@/components/stats/StatsBar";
import { RateLimitBanner } from "@/components/controls/RateLimitBanner";
import { WorkTree } from "@/components/worktree/WorkTree";
import { StatusBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { RepoSelector } from "@/components/ui/RepoSelector";
import { OnboardingModal } from "@/components/onboarding/OnboardingModal";
import { ParallelRunsView } from "@/components/parallel/ParallelRunsView";
import { MobileTab } from "@/components/mobile/MobileTab";
import { MobileControlSheet } from "@/components/mobile/MobileControlSheet";
import { TunnelPopover } from "@/components/ui/TunnelPopover";

export default function MonitorPage() {
  const [activeRepoFilter, setActiveRepoFilter] = useState<string | null>(() => {
    try { return localStorage.getItem("sp_improve_active_repo") || null; } catch { return null; }
  });
  const [repos, setRepos] = useState<RepoInfo[]>([]);
  const { runs, loading: runsLoading, refresh: refreshRuns } = useRuns(activeRepoFilter);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [selectedRun, setSelectedRun] = useState<Run | null>(null);
  const [historyEvents, setHistoryEvents] = useState<FeedEvent[]>([]);
  const [injectOpen, setInjectOpen] = useState(false);
  const [startModalOpen, setStartModalOpen] = useState(false);
  const [agentHealth, setAgentHealth] = useState<AgentHealth | null>(null);
  const [branches, setBranches] = useState<string[]>(["main"]);
  const [settingsStatus, setSettingsStatus] = useState<SettingsStatus | null>(null);
  const [onboardingOpen, setOnboardingOpen] = useState(false);
  const selectGenRef = useRef(0);
  const [activeView, setActiveView] = useState<"feed" | "bots">("bots");
  const skipLastRunRestoreRef = useRef(false);
  const isMobile = useMobile();
  const [mobilePanel, setMobilePanel] = useState<"feed" | "runs" | "changes" | "bots">("bots");
  const [controlsOpen, setControlsOpen] = useState(false);

  const { events: liveEvents, connected, clearEvents } = useSSE(selectedRunId);

  // Merge live events into history — SSE post events need to find their pre in history
  const allEvents = useMemo(
    () => mergeHistoryWithLive(historyEvents, liveEvents),
    [historyEvents, liveEvents],
  );

  const addEvent = useCallback((event: FeedEvent) => {
    setHistoryEvents((prev) => [...prev, event]);
  }, []);

  const {
    status: parallelStatus,
    loading: parallelBusy,
    startRun: startParallelRun,
    stopRun: parallelStop,
    killRun: parallelKill,
    pauseRun: parallelPause,
    resumeRun: parallelResume,
    unlockRun: parallelUnlock,
    injectPrompt: parallelInject,
    dismissRun: parallelDismiss,
  } = useParallelRuns();

  const parallelActive = parallelStatus?.active ?? 0;

  // Poll agent health — auto-select new runs when they appear
  useEffect(() => {
    const check = async () => {
      const h = await fetchAgentHealth();
      setAgentHealth((prev) => {
        if (h.current_run_id && h.current_run_id !== prev?.current_run_id) {
          refreshRuns();
          setSelectedRunId(h.current_run_id);
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
      await setActiveRepo(repo);
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
          fetchToolCalls(id),
          fetchAuditLog(id),
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
      const existingIds = new Set(runs.map((r) => r.id));

      startParallelRun(prompt, budget, durationMinutes, baseBranch, extendedContext).catch(
        (err) => {
          addEvent({
            _kind: "control",
            text: `Failed to launch bot: ${err}`,
            ts: new Date().toISOString(),
          });
        },
      );

      addEvent({
        _kind: "control",
        text: `Bot launching${prompt ? " with custom prompt" : ""}...`,
        ts: new Date().toISOString(),
      });

      // Poll for the new run to appear in the DB
      for (let i = 0; i < 60; i++) {
        await new Promise((r) => setTimeout(r, 3000));
        try {
          const freshRuns = await fetchRuns(activeRepoFilter || undefined);
          const newRun = freshRuns.find((r) => !existingIds.has(r.id));
          if (newRun) {
            refreshRuns();
            setSuppressAutoSelect(false);
            handleSelectRun(newRun.id);
            setActiveView("feed");
            return;
          }
        } catch {}
      }
    },
    [startParallelRun, addEvent, runs, activeRepoFilter, handleSelectRun, refreshRuns],
  );

  const runStatus: RunStatus | null =
    (selectedRun?.status as RunStatus) || null;
  const agentReachable = agentHealth != null && agentHealth.status !== "unreachable";
  const agentIdle = agentHealth?.status === "idle";
  const agentBootstrapping = agentHealth?.status === "bootstrapping";
  const isConfigured = settingsStatus?.configured ?? false;

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
      <header className="desktop-header relative z-10 flex items-center gap-3 px-4 py-2.5 border-b border-[#1a1a1a] bg-[#0a0a0a] header-glow">
        {/* Logo */}
        <div className="flex items-center gap-2">
          <div className="relative flex items-center justify-center h-7 w-7">
            <svg width="28" height="28" viewBox="0 0 28 28" className="absolute">
              <circle
                cx="14" cy="14" r="12"
                fill="none"
                stroke={runStatus === "running" ? "rgba(0,255,136,0.2)" : "rgba(255,255,255,0.06)"}
                strokeWidth="1"
                strokeDasharray="4 3"
                style={runStatus === "running" ? { animation: "spin 8s linear infinite" } : undefined}
              />
            </svg>
            <Image src="/logo.svg" alt="AutoFyn" width={18} height={18} className="relative z-[1]" />
          </div>
          <div>
            <h1 className="text-[12px] font-bold text-[#e8e8e8] tracking-tight">
              AutoFyn
            </h1>
            <p className="text-[9px] text-[#777] tracking-[0.1em] uppercase -mt-0.5">
              Monitor
            </p>
          </div>
        </div>

        {/* Repo Selector */}
        <div className="w-px h-4 bg-[#1a1a1a]" />
        <RepoSelector
          repos={repos}
          activeRepo={activeRepoFilter}
          onSelect={handleRepoSwitch}
        />

        {selectedRun && (
          <motion.div
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            className="flex items-center gap-2.5 ml-1"
          >
            <div className="w-px h-4 bg-[#1a1a1a]" />
            <StatusBadge
              status={selectedRun.status as RunStatus}
              size="md"
            />
            <span className="text-[10px] text-[#888] font-medium">
              {selectedRun.branch_name.replace("autofyn/", "")}
            </span>
          </motion.div>
        )}

        <div className="flex-1" />

        <div className="w-px h-4 bg-[#1a1a1a]" />

        {/* Agent health indicator */}
        <div className="flex items-center gap-1.5 mr-2">
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              agentReachable
                ? agentBootstrapping
                  ? "bg-[#ffaa00] animate-pulse"
                  : agentIdle
                    ? "bg-[#00ff88]/60"
                    : "bg-[#00ff88]"
                : "bg-[#ff4444]/60"
            }`}
            style={!agentIdle && !agentBootstrapping && agentReachable ? { boxShadow: "0 0 4px rgba(0,255,136,0.3)" } : undefined}
          />
          <span className="text-[10px] text-[#888]">
            {!agentReachable
              ? "Offline"
              : agentBootstrapping
                ? "Starting..."
                : agentIdle
                  ? "Idle"
                  : agentHealth?.elapsed_minutes != null
                    ? `Active · ${Math.round(agentHealth.elapsed_minutes)}m`
                    : "Active"}
          </span>
        </div>

        <TunnelPopover />
        <div className="w-px h-4 bg-[#1a1a1a]" />

        {/* Settings link */}
        <Link
          href="/settings"
          className="p-1.5 rounded hover:bg-white/[0.04] text-[#888] hover:text-[#ccc] transition-colors"
          title="Settings"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
          </svg>
        </Link>

        {/* Start Run button */}
        <Button
          variant="success"
          size="md"
          onClick={() => { fetchBranches(activeRepoFilter || undefined).then(setBranches); setStartModalOpen(true); }}
          disabled={!agentReachable || !isConfigured}
          title={!isConfigured ? "Configure credentials in Settings first" : undefined}
          icon={
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5">
              <polygon points="3 2 8 5 3 8" />
            </svg>
          }
        >
          {!isConfigured
            ? "Setup Required"
            : !agentReachable
              ? "Offline"
              : "+ New Bot"}
        </Button>

        <div className="w-px h-4 bg-[#1a1a1a]" />

        <ControlBar
          status={runStatus}
          onPause={() => selectedRunId && parallelPause(selectedRunId)}
          onResume={() => selectedRunId && parallelResume(selectedRunId)}
          onStop={() => selectedRunId && parallelStop(selectedRunId)}
          onKill={() => selectedRunId && (["running", "paused"].includes(runStatus || "") ? parallelKill(selectedRunId) : parallelDismiss(selectedRunId))}
          onUnlock={() => selectedRunId && parallelUnlock(selectedRunId)}
          onToggleInject={() => setInjectOpen(!injectOpen)}
          busy={parallelBusy}
          sessionLocked={agentHealth?.session_unlocked === false}
          timeRemaining={agentHealth?.time_remaining || null}
        />
      </header>

      {/* Mobile Top Bar */}
      <header className="mobile-top-bar items-center justify-between px-3 py-2 border-b border-[#1a1a1a] bg-[#0a0a0a]">
        <div className="flex items-center gap-2">
          <Image src="/logo.svg" alt="Buddy" width={16} height={16} />
          <span className="text-[11px] font-bold text-[#e8e8e8]">Buddy</span>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              agentReachable
                ? agentIdle ? "bg-[#00ff88]/60" : "bg-[#00ff88]"
                : "bg-[#ff4444]/60"
            }`}
          />
          <TunnelPopover />
          <Link href="/settings" className="p-1.5 rounded hover:bg-white/[0.04] text-[#888]">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="3" />
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
            </svg>
          </Link>
        </div>
      </header>

      {/* Inject Panel */}
      <InjectPanel
        open={injectOpen}
        onClose={() => setInjectOpen(false)}
        onSend={(prompt: string) => {
          if (selectedRunId) {
            parallelInject(selectedRunId, prompt);
            addEvent({
              _kind: "control",
              text: `Prompt injected (${prompt.length} chars)`,
              ts: new Date().toISOString(),
            });
          } else {
            addEvent({
              _kind: "control",
              text: "No run selected",
              ts: new Date().toISOString(),
            });
          }
        }}
        busy={parallelBusy}
      />

      {/* Start Run Modal */}
      <StartRunModal
        open={startModalOpen}
        onClose={() => setStartModalOpen(false)}
        onStart={handleStartRun}
        busy={parallelBusy}
        branches={branches}
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
          busy={parallelBusy}
        />
      )}

      {/* Main Content */}
      {!isMobile && (
        <div className="flex flex-1 min-h-0">
          {/* Left sidebar - Run list */}
          <div className="desktop-sidebar">
            <RunList
              runs={runs}
              activeId={selectedRunId}
              onSelect={(id) => { handleSelectRun(id); setActiveView("feed"); }}
              loading={runsLoading}
            />
          </div>

          {/* Center - view switcher */}
          <main className="flex-1 flex flex-col min-h-0 min-w-0">
            {/* View tabs */}
            <div className="flex items-center gap-0 border-b border-[#1a1a1a] bg-[#0a0a0a] px-4">
              <button
                onClick={() => setActiveView("bots")}
                className={`px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.1em] border-b-2 transition-colors ${
                  activeView === "bots"
                    ? "border-[#00ff88] text-[#00ff88]"
                    : "border-transparent text-[#666] hover:text-[#999]"
                }`}
              >
                Bots{parallelStatus ? ` (${parallelStatus.active})` : ""}
              </button>
              <button
                onClick={() => setActiveView("feed")}
                className={`px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.1em] border-b-2 transition-colors ${
                  activeView === "feed"
                    ? "border-[#00ff88] text-[#00ff88]"
                    : "border-transparent text-[#666] hover:text-[#999]"
                }`}
              >
                Feed
              </button>
            </div>

            {activeView === "bots" ? (
              <ParallelRunsView
                onStartNew={() => { fetchBranches(activeRepoFilter || undefined).then(setBranches); setStartModalOpen(true); }}
              />
            ) : (
              <>
                <EventFeed events={allEvents} />
                <StatsBar run={selectedRun} connected={connected} />
              </>
            )}
          </main>

          {/* Right sidebar - WorkTree (only show in feed view) */}
          {activeView === "feed" && (
            <div className="desktop-worktree">
              <WorkTree events={allEvents} runId={selectedRunId} />
            </div>
          )}
        </div>
      )}

      {/* Mobile content */}
      {isMobile && (
        <div className="flex-1 flex flex-col min-h-0 pb-14">
          {mobilePanel === "bots" && (
            <ParallelRunsView
              onStartNew={() => { fetchBranches(activeRepoFilter || undefined).then(setBranches); setStartModalOpen(true); }}
            />
          )}
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
              <EventFeed events={allEvents} />
              <StatsBar run={selectedRun} connected={connected} />
            </>
          )}
          {mobilePanel === "changes" && (
            <WorkTree events={allEvents} runId={selectedRunId} />
          )}
        </div>
      )}

      {/* Mobile bottom tab bar */}
      <nav className="mobile-bottom-bar">
        <MobileTab
          icon={<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></svg>}
          label="Bots"
          active={mobilePanel === "bots"}
          onClick={() => setMobilePanel("bots")}
          badge={parallelActive > 0 ? parallelActive : null}
        />
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
        onPause={() => selectedRunId && parallelPause(selectedRunId)}
        onResume={() => selectedRunId && parallelResume(selectedRunId)}
        onStop={() => selectedRunId && parallelStop(selectedRunId)}
        onKill={() => selectedRunId && (["running", "paused"].includes(runStatus || "") ? parallelKill(selectedRunId) : parallelDismiss(selectedRunId))}
        onUnlock={() => selectedRunId && parallelUnlock(selectedRunId)}
        onToggleInject={() => setInjectOpen(!injectOpen)}
        busy={parallelBusy}
        repos={repos}
        activeRepo={activeRepoFilter}
        onRepoSelect={handleRepoSwitch}
        onNewRun={() => { fetchBranches(activeRepoFilter || undefined).then(setBranches); setStartModalOpen(true); }}
        isConfigured={isConfigured}
      />
    </div>
  );
}
