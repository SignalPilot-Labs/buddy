"use client";

import { useState, useCallback, useEffect, useRef, useMemo } from "react";
import { motion } from "framer-motion";
import Image from "next/image";
import Link from "next/link";
import type { Run, FeedEvent, RunStatus, ToolCall, SettingsStatus, RepoInfo } from "@/lib/types";
import { fetchToolCalls, fetchAuditLog, startRun, fetchAgentHealth, fetchBranches, fetchRepos, setActiveRepo } from "@/lib/api";
import { AGENT_HEALTH_POLL_MS } from "@/lib/constants";
import { mergeHistoryWithLive } from "@/lib/eventMerge";
import type { AgentHealth } from "@/lib/api";
import { fetchSettingsStatus } from "@/lib/settings-api";
import { useRuns } from "@/hooks/useRuns";
import { useSSE } from "@/hooks/useSSE";
import { useControl } from "@/hooks/useControl";
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
import { MobileAccessPopover } from "@/components/ui/MobileAccessPopover";
import { MobileTab } from "@/components/mobile/MobileTab";
import { MobileControlSheet } from "@/components/mobile/MobileControlSheet";

export default function MonitorPage() {
  const [activeRepoFilter, setActiveRepoFilter] = useState<string | null>(null);
  const [repos, setRepos] = useState<RepoInfo[]>([]);
  const { runs, loading: runsLoading, refresh: refreshRuns } = useRuns(activeRepoFilter);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [selectedRun, setSelectedRun] = useState<Run | null>(null);
  const [historyEvents, setHistoryEvents] = useState<FeedEvent[]>([]);
  const [injectOpen, setInjectOpen] = useState(false);
  const [startModalOpen, setStartModalOpen] = useState(false);
  const [startBusy, setStartBusy] = useState(false);
  const [agentHealth, setAgentHealth] = useState<AgentHealth | null>(null);
  const [branches, setBranches] = useState<string[]>(["main"]);
  const [settingsStatus, setSettingsStatus] = useState<SettingsStatus | null>(null);
  const [onboardingOpen, setOnboardingOpen] = useState(false);
  const selectGenRef = useRef(0);
  const isMobile = useMobile();
  const [mobilePanel, setMobilePanel] = useState<"feed" | "runs" | "changes">("feed");
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

  const { pause, resume, stop, inject, resumeSession, busy } = useControl(
    selectedRunId,
    addEvent
  );

  // Poll agent health
  useEffect(() => {
    const check = async () => {
      const h = await fetchAgentHealth();
      setAgentHealth(h);
    };
    check();
    const id = setInterval(check, AGENT_HEALTH_POLL_MS);
    return () => clearInterval(id);
  }, []);

  // Check settings status on mount and load repos
  useEffect(() => {
    fetchSettingsStatus().then((s) => {
      setSettingsStatus(s);
      if (!s.configured) setOnboardingOpen(true);
    });
    fetchRepos().then((r) => {
      setRepos(r);
      if (r.length > 0 && !activeRepoFilter) {
        const withRuns = r.find((repo) => repo.run_count > 0);
        setActiveRepoFilter(withRuns?.repo || r[0].repo);
      }
    });
  }, []);

  // Handle repo switch
  const handleRepoSwitch = useCallback(async (repo: string) => {
    setActiveRepoFilter(repo || null);
    setSelectedRunId(null);
    setSelectedRun(null);
    setHistoryEvents([]);
    clearEvents();
    if (repo) {
      await setActiveRepo(repo);
    }
    fetchRepos().then(setRepos);
  }, [clearEvents]);

  // Auto-select first active run or latest run
  useEffect(() => {
    if (!selectedRunId && runs.length > 0) {
      const active = runs.find((r) => ["running", "paused", "rate_limited"].includes(r.status));
      setSelectedRunId(active?.id || runs[0].id);
    }
  }, [runs, selectedRunId]);

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

        const auditEvents: FeedEvent[] = audits
          .filter(
            (a) => !["llm_text", "llm_thinking"].includes(a.event_type)
          )
          .map((a) => ({
            _kind: "audit" as const,
            data: a,
          }));

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

  // Start a new run
  const handleStartRun = useCallback(
    async (prompt: string | undefined, budget: number, durationMinutes: number, baseBranch: string) => {
      setStartBusy(true);
      try {
        const result = await startRun(prompt, budget, durationMinutes, baseBranch);
        setStartModalOpen(false);
        addEvent({
          _kind: "control",
          text: `New run started${prompt ? ` with custom prompt` : ""}`,
          ts: new Date().toISOString(),
        });
        setTimeout(async () => {
          await refreshRuns();
          if (result.run_id) {
            setSelectedRunId(result.run_id);
            handleSelectRun(result.run_id);
          }
        }, 2000);
      } catch (err) {
        addEvent({
          _kind: "control",
          text: `Failed to start run: ${err}`,
          ts: new Date().toISOString(),
        });
      } finally {
        setStartBusy(false);
      }
    },
    [addEvent, refreshRuns, handleSelectRun]
  );

  const runStatus: RunStatus | null =
    (selectedRun?.status as RunStatus) || null;
  const agentIdle = agentHealth?.status === "idle";
  const agentReachable = agentHealth != null && agentHealth.status !== "unreachable";
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
          <Image src="/logo.svg" alt="Buddy" width={18} height={18} className="relative z-[1]" />
        </div>

        <div>
          <h1 className="text-[12px] font-bold text-[#e8e8e8] tracking-tight">Buddy</h1>
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
            <Image src="/logo.svg" alt="Buddy" width={18} height={18} className="relative z-[1]" />
          </div>
          <div>
            <h1 className="text-[12px] font-bold text-[#e8e8e8] tracking-tight">
              Buddy
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
              {selectedRun.branch_name.replace("buddy/", "")}
            </span>
          </motion.div>
        )}

        <div className="flex-1" />

        {/* Mobile access QR */}
        <MobileAccessPopover />

        <div className="w-px h-4 bg-[#1a1a1a]" />

        {/* Agent health indicator */}
        <div className="flex items-center gap-1.5 mr-2">
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              agentReachable
                ? agentIdle
                  ? "bg-[#00ff88]/60"
                  : "bg-[#00ff88]"
                : "bg-[#ff4444]/60"
            }`}
            style={!agentIdle && agentReachable ? { boxShadow: "0 0 4px rgba(0,255,136,0.3)" } : undefined}
          />
          <span className="text-[10px] text-[#888]">
            {!agentReachable
              ? "Offline"
              : agentIdle
                ? "Idle"
                : agentHealth?.elapsed_minutes != null
                  ? `Active · ${Math.round(agentHealth.elapsed_minutes)}m`
                  : "Active"}
          </span>
        </div>

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
          onClick={() => { fetchBranches().then(setBranches); setStartModalOpen(true); }}
          disabled={!agentIdle || !agentReachable || !isConfigured}
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
              : !agentIdle
                ? "Running"
                : "New Run"}
        </Button>

        <div className="w-px h-4 bg-[#1a1a1a]" />

        <ControlBar
          status={runStatus}
          onPause={pause}
          onOpenInject={() => setInjectOpen(!injectOpen)}
          busy={busy}
        />
      </header>

      {/* Inject Panel */}
      <InjectPanel
        open={injectOpen}
        onClose={() => setInjectOpen(false)}
        onSend={inject}
        onResumePlain={resume}
        onStop={stop}
        busy={busy}
        status={runStatus}
        sessionLocked={agentHealth?.session_unlocked === false}
        timeRemaining={agentHealth?.time_remaining || null}
      />

      {/* Start Run Modal */}
      <StartRunModal
        open={startModalOpen}
        onClose={() => setStartModalOpen(false)}
        onStart={handleStartRun}
        busy={startBusy}
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
          onResume={resumeSession}
          busy={busy}
        />
      )}

      {/* Main Content */}
      <div className="flex flex-1 min-h-0">
        {/* ── Desktop Layout ── */}
        <div className="desktop-sidebar">
          <RunList
            runs={runs}
            activeId={selectedRunId}
            onSelect={handleSelectRun}
            loading={runsLoading}
          />
        </div>

        {!isMobile && (
          <>
            <main className="flex-1 flex flex-col min-h-0 min-w-0">
              <EventFeed events={allEvents} />
              <StatsBar run={selectedRun} connected={connected} events={allEvents} />
            </main>
            <div className="desktop-worktree">
              <WorkTree events={allEvents} runId={selectedRunId} />
            </div>
          </>
        )}

        {/* ── Mobile Layout ── */}
        {isMobile && (
          <div className="flex-1 flex flex-col min-h-0 min-w-0" style={{ paddingBottom: "calc(56px + env(safe-area-inset-bottom, 0px))" }}>
            {mobilePanel === "runs" && (
              <RunList
                runs={runs}
                activeId={selectedRunId}
                onSelect={(id: string) => {
                  handleSelectRun(id);
                  setMobilePanel("feed");
                }}
                loading={runsLoading}
                mobile
              />
            )}

            {mobilePanel === "feed" && (
              <main className="flex-1 flex flex-col min-h-0 min-w-0">
                <EventFeed events={allEvents} />
                <StatsBar run={selectedRun} connected={connected} events={allEvents} />
              </main>
            )}

            {mobilePanel === "changes" && (
              <WorkTree events={allEvents} runId={selectedRunId} mobile />
            )}
          </div>
        )}
      </div>

      {/* ── Mobile Bottom Tab Bar ── */}
      <nav className="mobile-bottom-bar">
        <MobileTab
          icon={<svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><rect x="2" y="2" width="14" height="14" rx="2" /><line x1="2" y1="6" x2="16" y2="6" /><line x1="2" y1="10" x2="16" y2="10" /></svg>}
          label="Runs"
          active={mobilePanel === "runs"}
          onClick={() => setMobilePanel("runs")}
          badge={runs.length || null}
        />
        <MobileTab
          icon={<svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><path d="M3 9h12" /><path d="M3 5h8" /><path d="M3 13h10" /></svg>}
          label="Feed"
          active={mobilePanel === "feed"}
          onClick={() => setMobilePanel("feed")}
          badge={allEvents.length || null}
        />
        <MobileTab
          icon={<svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><path d="M9 2v14M9 2L5 6M9 2l4 4" /><circle cx="5" cy="10" r="1.5" /><circle cx="13" cy="12" r="1.5" /><line x1="5" y1="10" x2="9" y2="10" /><line x1="13" y1="12" x2="9" y2="12" /></svg>}
          label="Changes"
          active={mobilePanel === "changes"}
          onClick={() => setMobilePanel("changes")}
        />
        <MobileTab
          icon={<svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><circle cx="9" cy="6" r="2" /><path d="M5 14h8" /><path d="M4 10h10" /></svg>}
          label="Controls"
          active={controlsOpen}
          onClick={() => setControlsOpen(!controlsOpen)}
        />
      </nav>

      {/* ── Mobile Control Sheet ── */}
      <MobileControlSheet
        open={controlsOpen}
        onClose={() => setControlsOpen(false)}
        status={runStatus}
        onPause={pause}
        onOpenInject={() => { setInjectOpen(!injectOpen); }}
        busy={busy}
        repos={repos}
        activeRepo={activeRepoFilter}
        onRepoSelect={handleRepoSwitch}
        onNewRun={() => {
          fetchBranches().then(setBranches);
          setStartModalOpen(true);
        }}
        isConfigured={isConfigured}
      />
    </div>
  );
}
