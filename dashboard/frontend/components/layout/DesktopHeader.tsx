"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import type { RunStatus, Run, RepoInfo } from "@/lib/types";
import type { AgentHealth } from "@/lib/api";
import type { LocaleDict } from "@/lib/i18n/types";
import { LogoMark } from "@/components/ui/LogoMark";
import { StatusBadge } from "@/components/ui/Badge";
import { MobileAccessPopover } from "@/components/ui/MobileAccessPopover";
import { LocaleToggle } from "@/components/ui/LocaleToggle";
import { RepoSelector } from "@/components/ui/RepoSelector";
import { Button } from "@/components/ui/Button";
import { ControlBar } from "@/components/controls/ControlBar";

interface DesktopHeaderProps {
  runStatus: RunStatus | null;
  agentReachable: boolean;
  agentIdle: boolean;
  agentBootstrapping: boolean;
  agentHealth: AgentHealth | null;
  selectedRun: Run | null;
  repos: RepoInfo[];
  activeRepoFilter: string | null;
  isConfigured: boolean;
  busy: boolean;
  sessionLocked: boolean;
  timeRemaining: string | null;
  injectOpen: boolean;
  onRepoSwitch: (repo: string) => Promise<void>;
  onStartRunClick: () => void;
  onPause: () => void;
  onResume: () => void;
  onStop: () => void;
  onKill: () => void;
  onUnlock: () => void;
  onToggleInject: () => void;
  onResumeRun: () => void;
  t: LocaleDict;
}

export function DesktopHeader({
  runStatus,
  agentReachable,
  agentIdle,
  agentBootstrapping,
  agentHealth,
  selectedRun,
  repos,
  activeRepoFilter,
  isConfigured,
  busy,
  sessionLocked,
  timeRemaining,
  onRepoSwitch,
  onStartRunClick,
  onPause,
  onResume,
  onStop,
  onKill,
  onUnlock,
  onToggleInject,
  onResumeRun,
  t,
}: DesktopHeaderProps): React.ReactElement {
  const healthDotClass = agentReachable
    ? agentBootstrapping
      ? "bg-[#ffaa00] animate-pulse"
      : agentIdle
        ? "bg-[#00ff88]/60"
        : "bg-[#00ff88]"
    : "bg-[#ff4444]/60";
  const healthDotStyle: React.CSSProperties | undefined =
    !agentIdle && !agentBootstrapping && agentReachable
      ? { boxShadow: "0 0 4px rgba(0,255,136,0.3)" }
      : undefined;

  const healthLabel = !agentReachable
    ? t.agentStatus.offline
    : agentBootstrapping
      ? t.agentStatus.starting
      : agentIdle
        ? t.agentStatus.idle
        : agentHealth?.elapsed_minutes != null
          ? `${t.agentStatus.active} · ${Math.round(agentHealth.elapsed_minutes)}m`
          : t.agentStatus.active;

  const startButtonLabel = !isConfigured
    ? t.run.setupRequired
    : !agentReachable
      ? t.run.offline
      : !agentIdle
        ? t.run.running
        : t.run.newRun;

  return (
    <header className="desktop-header relative z-10 flex items-center gap-3 px-4 py-2.5 border-b border-[#1a1a1a] bg-[#0a0a0a] header-glow">
      <div className="flex items-center gap-2">
        <LogoMark runStatus={runStatus} />
        <div>
          <h1 className="text-[12px] font-bold text-[#e8e8e8] tracking-tight">
            AutoFyn
          </h1>
          <p className="text-[9px] text-[#777] tracking-[0.1em] uppercase -mt-0.5">
            {t.monitor}
          </p>
        </div>
      </div>

      <div className="w-px h-4 bg-[#1a1a1a]" />
      <RepoSelector
        repos={repos}
        activeRepo={activeRepoFilter}
        onSelect={onRepoSwitch}
      />

      {selectedRun && (
        <motion.div
          initial={{ opacity: 0, x: -8 }}
          animate={{ opacity: 1, x: 0 }}
          className="flex items-center gap-2.5 ml-1"
        >
          <div className="w-px h-4 bg-[#1a1a1a]" />
          <StatusBadge status={selectedRun.status as RunStatus} size="md" />
          <span className="text-[10px] text-[#888] font-medium">
            {selectedRun.branch_name.replace("autofyn/", "")}
          </span>
        </motion.div>
      )}

      <div className="flex-1" />

      <MobileAccessPopover />

      <div className="w-px h-4 bg-[#1a1a1a]" />

      <div className="flex items-center gap-1.5 mr-2">
        <span
          className={`h-1.5 w-1.5 rounded-full ${healthDotClass}`}
          style={healthDotStyle}
        />
        <span className="text-[10px] text-[#888]">{healthLabel}</span>
      </div>

      <LocaleToggle />

      <Link
        href="/settings"
        className="p-1.5 rounded hover:bg-white/[0.04] text-[#888] hover:text-[#ccc] transition-colors"
        title={t.nav.settings}
      >
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <circle cx="12" cy="12" r="3" />
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
        </svg>
      </Link>

      <Button
        variant="success"
        size="md"
        onClick={onStartRunClick}
        disabled={!agentIdle || !agentReachable || !isConfigured}
        title={!isConfigured ? t.run.configureFirst : undefined}
        icon={
          <svg
            width="10"
            height="10"
            viewBox="0 0 10 10"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
          >
            <polygon points="3 2 8 5 3 8" />
          </svg>
        }
      >
        {startButtonLabel}
      </Button>

      <div className="w-px h-4 bg-[#1a1a1a]" />

      <ControlBar
        status={runStatus}
        onPause={onPause}
        onResume={onResume}
        onStop={onStop}
        onKill={onKill}
        onUnlock={onUnlock}
        onToggleInject={onToggleInject}
        onResumeRun={onResumeRun}
        busy={busy}
        sessionLocked={sessionLocked}
        timeRemaining={timeRemaining}
      />
    </header>
  );
}
