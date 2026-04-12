"use client";

import Image from "next/image";
import Link from "next/link";
import type { RunStatus } from "@/lib/types";
import { fetchBranches, pauseAgent, resumeAgent, stopAgentInstant, killAgent, unlockAgent } from "@/lib/api";
import { useDashboard } from "@/hooks/useDashboard";
import { useToast } from "@/hooks/useToast";
import { RunList } from "@/components/sidebar/RunList";
import { EventFeed } from "@/components/feed/EventFeed";
import { CommandInput } from "@/components/controls/CommandInput";
import { StartRunModal } from "@/components/controls/StartRunModal";
import { RateLimitBanner } from "@/components/controls/RateLimitBanner";
import { StatusBadge } from "@/components/ui/Badge";
import { OnboardingModal } from "@/components/onboarding/OnboardingModal";
import { MobileControlSheet } from "@/components/mobile/MobileControlSheet";
import { MobileAccessPopover } from "@/components/ui/MobileAccessPopover";
import { MobileLayout } from "@/components/mobile/MobileLayout";
import { DashboardHeader } from "@/components/header/DashboardHeader";
import { RightPanel } from "@/components/layout/RightPanel";
import { ConnectionBanner } from "@/components/ui/ConnectionBanner";
import { KeyboardShortcuts } from "@/components/ui/KeyboardShortcuts";
import { ToastProvider } from "@/components/ui/Toast";
import { fetchSettingsStatus } from "@/lib/settings-api";
import { fetchRepos } from "@/lib/api";

function MonitorPageInner() {
  const { showToast } = useToast();
  const dashboard = useDashboard();
  const {
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
  } = dashboard;

  const agentReachable = agentHealth != null && agentHealth.status !== "unreachable";
  const agentIdle = agentHealth?.status === "idle";

  // On success, show a toast. On failure, controlAction already emits a feed
  // event with a retry button — no second toast needed (avoids double feedback).
  const toastControlAction = (label: string, fn: (id: string) => Promise<unknown>): Promise<void> =>
    controlAction(label, fn).then(() => showToast(label, "success")).catch(() => undefined);

  return (
    <div className="h-screen flex flex-col bg-[var(--color-bg)]">
      {/* ── Mobile Top Bar ── */}
      <header className="mobile-top-bar items-center gap-2 px-3 py-2 border-b border-[#1a1a1a] bg-[#0a0a0a] header-glow safe-area-top">
        {/* Logo */}
        <div className="relative flex items-center justify-center h-7 w-7">
          <svg width="28" height="28" viewBox="0 0 28 28" className="absolute">
            <circle
              cx="14" cy="14" r="12" fill="none"
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
        onStop={() => { void toastControlAction("Stop", stopAgentInstant); }}
        onKill={handleHeaderKill}
        onNewRun={() => {
          if (!activeRepoFilter) {
            showToast("Select a repo first", "error");
            return;
          }
          fetchBranches(activeRepoFilter)
            .then(setBranches)
            .catch((err) => showToast(`Failed to load branches: ${err.message}`, "error"));
          setStartModalOpen(true);
        }}
        sidebarCollapsed={sidebarCollapsed}
        onToggleSidebar={handleToggleSidebar}
        onUnlock={() => { void toastControlAction("Unlock", unlockAgent); }}
        sessionLocked={activeRunHealth?.session_unlocked === false}
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
              if (r.length > 0) handleRepoSwitch(r[0].repo);
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
              selectedRun.model_name || undefined,
            );
          }}
          busy={busy}
        />
      )}

      {/* Main Content — Desktop */}
      {!isMobile && (
        <div className="flex flex-1 min-h-0">
          {/* Left sidebar */}
          <div className={`desktop-sidebar overflow-hidden transition-all duration-200 ${sidebarCollapsed ? "w-[48px]" : "w-[260px]"}`}>
            <RunList
              runs={runs}
              activeId={selectedRunId}
              onSelect={(id) => { handleSelectRun(id); }}
              loading={runsLoading}
              collapsed={sidebarCollapsed}
            />
          </div>

          {/* Center — Feed */}
          <main className="flex-1 flex flex-col min-h-0 min-w-0 relative">
            <ConnectionBanner
              connectionState={connectionState}
              runStatus={runStatus}
              showToast={showToast}
            />
            <EventFeed
              events={allEvents}
              pendingMessages={pendingMessages}
              runActive={runStatus === "running" || runStatus === "paused" || runStatus === "rate_limited"}
              runPaused={runStatus === "paused"}
              isLoading={historyLoading}
              historyTruncated={historyTruncated}
            />
            <CommandInput
              runId={selectedRunId}
              status={runStatus}
              run={selectedRun}
              connected={connected}
              events={allEvents}
              busy={busy}
              onPause={() => { void toastControlAction("Pause", pauseAgent); }}
              onResume={() => { void toastControlAction("Resume", resumeAgent); }}
              onInject={handleInject}
              onRestart={handleRestart}
            />
          </main>

          {/* Right sidebar */}
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

      {/* Main Content — Mobile */}
      {isMobile && (
        <MobileLayout
          mobilePanel={mobilePanel}
          setMobilePanel={setMobilePanel}
          runs={runs}
          selectedRunId={selectedRunId}
          runsLoading={runsLoading}
          allEvents={allEvents}
          pendingMessages={pendingMessages}
          runStatus={runStatus}
          selectedRun={selectedRun}
          connected={connected}
          connectionState={connectionState}
          historyTruncated={historyTruncated}
          busy={busy}
          historyLoading={historyLoading}
          controlsOpen={controlsOpen}
          setControlsOpen={setControlsOpen}
          onSelectRun={handleSelectRun}
          onPause={() => { void toastControlAction("Pause", pauseAgent); }}
          onResume={() => { void toastControlAction("Resume", resumeAgent); }}
          onInject={handleInject}
          onRestart={handleRestart}
        />
      )}

      {/* Mobile Control Sheet */}
      <MobileControlSheet
        open={controlsOpen}
        onClose={() => setControlsOpen(false)}
        status={runStatus}
        onPause={() => { void toastControlAction("Pause", pauseAgent); }}
        onResume={() => { void toastControlAction("Resume", resumeAgent); }}
        onStop={() => { void toastControlAction("Stop", stopAgentInstant); }}
        onKill={() => { void toastControlAction("Kill", killAgent); }}
        onUnlock={() => { void toastControlAction("Unlock", unlockAgent); }}
        onToggleInject={() => setMobilePanel("feed")}
        busy={busy}
        repos={repos}
        activeRepo={activeRepoFilter}
        onRepoSelect={handleRepoSwitch}
        onNewRun={() => {
          if (!activeRepoFilter) {
            showToast("Select a repo first", "error");
            return;
          }
          fetchBranches(activeRepoFilter)
            .then(setBranches)
            .catch((err) => showToast(`Failed to load branches: ${err.message}`, "error"));
          setStartModalOpen(true);
        }}
        isConfigured={isConfigured}
      />

      {/* Keyboard Shortcuts Panel */}
      <KeyboardShortcuts
        open={showShortcuts}
        onClose={() => setShowShortcuts(false)}
      />
    </div>
  );
}

export default function MonitorPage() {
  return (
    <ToastProvider>
      <MonitorPageInner />
    </ToastProvider>
  );
}
