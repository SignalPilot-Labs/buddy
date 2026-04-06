"use client";

import { useState, useCallback, useEffect, useRef, useMemo } from "react";
import type {
  Run,
  FeedEvent,
  RunStatus,
  SettingsStatus,
  RepoInfo,
} from "@/lib/types";
import {
  fetchToolCalls,
  fetchAuditLog,
  startRun,
  fetchAgentHealth,
  fetchBranches,
  fetchRepos,
  setActiveRepo,
} from "@/lib/api";
import { AGENT_HEALTH_POLL_MS } from "@/lib/constants";
import { mergeHistoryWithLive } from "@/lib/eventMerge";
import { buildHistoryEvents } from "@/lib/mergeToolCalls";
import type { AgentHealth } from "@/lib/api";
import { fetchSettingsStatus } from "@/lib/settings-api";
import { useRuns } from "@/hooks/useRuns";
import { useSSE } from "@/hooks/useSSE";
import { useControl } from "@/hooks/useControl";
import { useMobile } from "@/hooks/useMobile";
import { RunList } from "@/components/sidebar/RunList";
import { InjectPanel } from "@/components/controls/InjectPanel";
import { StartRunModal } from "@/components/controls/StartRunModal";
import { RateLimitBanner } from "@/components/controls/RateLimitBanner";
import { OnboardingModal } from "@/components/onboarding/OnboardingModal";
import { MobileControlSheet } from "@/components/mobile/MobileControlSheet";
import { MobileHeader } from "@/components/layout/MobileHeader";
import { DesktopHeader } from "@/components/layout/DesktopHeader";
import { MobileTabBar } from "@/components/layout/MobileTabBar";
import { MobileContent } from "@/components/layout/MobileContent";
import { DesktopContent } from "@/components/layout/DesktopContent";
import { useTranslation } from "@/hooks/useTranslation";

export default function MonitorPage(): React.ReactElement {
  const [activeRepoFilter, setActiveRepoFilter] = useState<string | null>(null);
  const [repos, setRepos] = useState<RepoInfo[]>([]);
  const {
    runs,
    loading: runsLoading,
    refresh: refreshRuns,
  } = useRuns(activeRepoFilter);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [selectedRun, setSelectedRun] = useState<Run | null>(null);
  const [historyEvents, setHistoryEvents] = useState<FeedEvent[]>([]);
  const [injectOpen, setInjectOpen] = useState(false);
  const [startModalOpen, setStartModalOpen] = useState(false);
  const [startBusy, setStartBusy] = useState(false);
  const [agentHealth, setAgentHealth] = useState<AgentHealth | null>(null);
  const [branches, setBranches] = useState<string[]>(["main"]);
  const [settingsStatus, setSettingsStatus] = useState<SettingsStatus | null>(
    null,
  );
  const [onboardingOpen, setOnboardingOpen] = useState(false);
  const selectGenRef = useRef(0);
  const skipLastRunRestoreRef = useRef(false);
  const isMobile = useMobile();
  const { t } = useTranslation();
  const [mobilePanel, setMobilePanel] = useState<"feed" | "runs" | "changes">(
    "feed",
  );
  const [controlsOpen, setControlsOpen] = useState(false);

  const { events: liveEvents, connected, clearEvents } = useSSE(selectedRunId);

  const allEvents = useMemo(
    () => mergeHistoryWithLive(historyEvents, liveEvents),
    [historyEvents, liveEvents],
  );

  const addEvent = useCallback((event: FeedEvent) => {
    setHistoryEvents((prev) => [...prev, event]);
  }, []);

  const { pause, resume, stop, kill, inject, unlock, resumeSession, busy } =
    useControl(selectedRunId, addEvent);

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
      if (r.length > 0 && !activeRepoFilter) {
        const withRuns = r.find((repo) => repo.run_count > 0);
        setActiveRepoFilter(withRuns?.repo || r[0].repo);
      }
    });
  }, []);

  const handleRepoSwitch = useCallback(
    async (repo: string) => {
      skipLastRunRestoreRef.current = true;
      setActiveRepoFilter(repo || null);
      setSelectedRunId(null);
      setSelectedRun(null);
      setHistoryEvents([]);
      clearEvents();
      if (repo) {
        await setActiveRepo(repo);
      }
      fetchRepos().then(setRepos);
    },
    [clearEvents],
  );

  // Keep selectedRun fresh
  useEffect(() => {
    if (selectedRunId) {
      const found = runs.find((r) => r.id === selectedRunId);
      if (found) setSelectedRun(found);
    }
  }, [runs, selectedRunId]);

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

        setHistoryEvents(buildHistoryEvents(tools, audits));
      } catch (err) {
        console.warn(
          "Failed to load historical events, SSE will provide live data:",
          err,
        );
      }

      refreshRuns();
    },
    [clearEvents, refreshRuns],
  );

  // Auto-select: restore last viewed run on initial load, most recent on repo switch
  useEffect(() => {
    if (!selectedRunId && runs.length > 0) {
      if (
        activeRepoFilter &&
        !runs.some((r) => r.github_repo === activeRepoFilter)
      ) {
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
      const active = runs.find((r) =>
        ["running", "paused", "rate_limited"].includes(r.status),
      );
      handleSelectRun(active?.id || runs[0].id);
    }
  }, [runs, selectedRunId, handleSelectRun, activeRepoFilter]);

  const handleStartRun = useCallback(
    async (
      prompt: string | undefined,
      budget: number,
      durationMinutes: number,
      baseBranch: string,
    ) => {
      setStartBusy(true);
      setStartModalOpen(false);
      setHistoryEvents([]);
      clearEvents();
      try {
        await startRun(prompt, budget, durationMinutes, baseBranch);
        addEvent({
          _kind: "control",
          text: `Starting run${prompt ? ` — ${prompt.slice(0, 80)}` : ""}`,
          ts: new Date().toISOString(),
        });
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
    [addEvent, clearEvents, refreshRuns, handleSelectRun],
  );

  const runStatus: RunStatus | null =
    (selectedRun?.status as RunStatus) || null;
  const agentIdle = agentHealth?.status === "idle";
  const agentBootstrapping = agentHealth?.status === "bootstrapping";
  const agentReachable =
    agentHealth != null && agentHealth.status !== "unreachable";
  const isConfigured = settingsStatus?.configured ?? false;
  const sessionLocked = agentHealth?.session_unlocked === false;
  const timeRemaining = agentHealth?.time_remaining || null;

  const handleStartRunClick = useCallback(() => {
    fetchBranches().then(setBranches);
    setStartModalOpen(true);
  }, []);

  const handleToggleInject = useCallback(() => {
    setInjectOpen((prev) => !prev);
  }, []);

  const handleOnboardingComplete = useCallback(() => {
    setOnboardingOpen(false);
    fetchSettingsStatus().then(setSettingsStatus);
    fetchRepos().then((r) => {
      setRepos(r);
      if (r.length > 0) setActiveRepoFilter(r[0].repo);
    });
  }, []);

  const handleNewRun = useCallback(() => {
    fetchBranches().then(setBranches);
    setStartModalOpen(true);
  }, []);

  const handleControlsToggle = useCallback(() => {
    setControlsOpen((prev) => !prev);
  }, []);

  const handleMobileSelectRun = useCallback(
    (id: string) => {
      handleSelectRun(id);
      setMobilePanel("feed");
    },
    [handleSelectRun],
  );

  return (
    <div className="h-screen flex flex-col bg-[var(--color-bg)]">
      <MobileHeader
        runStatus={runStatus}
        agentReachable={agentReachable}
        agentIdle={agentIdle}
        selectedRun={selectedRun}
        t={t}
      />

      <DesktopHeader
        runStatus={runStatus}
        agentReachable={agentReachable}
        agentIdle={agentIdle}
        agentBootstrapping={agentBootstrapping}
        agentHealth={agentHealth}
        selectedRun={selectedRun}
        repos={repos}
        activeRepoFilter={activeRepoFilter}
        isConfigured={isConfigured}
        busy={busy}
        sessionLocked={sessionLocked}
        timeRemaining={timeRemaining}
        injectOpen={injectOpen}
        onRepoSwitch={handleRepoSwitch}
        onStartRunClick={handleStartRunClick}
        onPause={pause}
        onResume={resume}
        onStop={stop}
        onKill={kill}
        onUnlock={unlock}
        onToggleInject={handleToggleInject}
        onResumeRun={resumeSession}
        t={t}
      />

      <InjectPanel
        open={injectOpen}
        onClose={() => setInjectOpen(false)}
        onSend={inject}
        busy={busy}
      />

      <StartRunModal
        open={startModalOpen}
        onClose={() => setStartModalOpen(false)}
        onStart={handleStartRun}
        busy={startBusy}
        branches={branches}
      />

      {settingsStatus && (
        <OnboardingModal
          open={onboardingOpen}
          onComplete={handleOnboardingComplete}
          initialStatus={settingsStatus}
        />
      )}

      {selectedRun?.status === "rate_limited" &&
        selectedRun.rate_limit_resets_at && (
          <RateLimitBanner
            resetsAt={selectedRun.rate_limit_resets_at}
            onResume={resumeSession}
            busy={busy}
          />
        )}

      <div className="flex flex-1 min-h-0">
        <div className="desktop-sidebar">
          <RunList
            runs={runs}
            activeId={selectedRunId}
            onSelect={handleSelectRun}
            loading={runsLoading}
          />
        </div>

        {!isMobile && (
          <DesktopContent
            selectedRun={selectedRun}
            selectedRunId={selectedRunId}
            allEvents={allEvents}
            connected={connected}
          />
        )}

        {isMobile && (
          <MobileContent
            mobilePanel={mobilePanel}
            runs={runs}
            selectedRunId={selectedRunId}
            selectedRun={selectedRun}
            runsLoading={runsLoading}
            allEvents={allEvents}
            connected={connected}
            onSelectRun={handleMobileSelectRun}
          />
        )}
      </div>

      <MobileTabBar
        mobilePanel={mobilePanel}
        controlsOpen={controlsOpen}
        runsCount={runs.length}
        eventsCount={allEvents.length}
        onPanelChange={setMobilePanel}
        onControlsToggle={handleControlsToggle}
        t={t}
      />

      <MobileControlSheet
        open={controlsOpen}
        onClose={() => setControlsOpen(false)}
        status={runStatus}
        onPause={pause}
        onResume={resume}
        onStop={stop}
        onKill={kill}
        onUnlock={unlock}
        onToggleInject={handleToggleInject}
        busy={busy}
        repos={repos}
        activeRepo={activeRepoFilter}
        onRepoSelect={handleRepoSwitch}
        onNewRun={handleNewRun}
        isConfigured={isConfigured}
      />
    </div>
  );
}
