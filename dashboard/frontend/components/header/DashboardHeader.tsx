"use client";

import { useState, useCallback } from "react";
import { motion } from "framer-motion";
import Image from "next/image";
import Link from "next/link";
import type { Run, RunStatus, RepoInfo } from "@/lib/types";
import type { AgentHealth, HealthRunEntry } from "@/lib/api";
import { ACTIVE_STATUSES, RUN_ID_DISPLAY_LENGTH, COPY_FEEDBACK_MS, REPO_DROPDOWN_MAX_HEIGHT } from "@/lib/constants";
import { StatusBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { RepoSelector } from "@/components/ui/RepoSelector";
import { MobileAccessPopover } from "@/components/ui/MobileAccessPopover";
import { RunControls } from "@/components/controls/RunControls";

export interface DashboardHeaderProps {
  repos: RepoInfo[];
  activeRepo: string | null;
  onRepoSwitch: (repo: string) => void;
  selectedRun: Run | null;
  runStatus: RunStatus | null;
  agentHealth: AgentHealth | null;
  activeRunHealth: HealthRunEntry | undefined;
  isConfigured: boolean;
  atCapacity: boolean;
  busy: boolean;
  onStop: () => void;
  onCancel: (runId: string) => void;
  onNewRun: () => void;
  sidebarCollapsed: boolean;
  onToggleSidebar: () => void;
  onUnlock: () => void;
  sessionLocked: boolean;
}

export function DashboardHeader({
  repos,
  activeRepo,
  onRepoSwitch,
  selectedRun,
  runStatus,
  agentHealth,
  activeRunHealth,
  isConfigured,
  atCapacity,
  busy,
  onStop,
  onCancel,
  onNewRun,
  sidebarCollapsed,
  onToggleSidebar,
  onUnlock,
  sessionLocked,
}: DashboardHeaderProps) {
  const [copied, setCopied] = useState(false);

  const handleCopyRunId = useCallback(() => {
    if (!selectedRun) return;
    navigator.clipboard.writeText(selectedRun.id).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), COPY_FEEDBACK_MS);
    });
  }, [selectedRun]);

  const agentReachable = agentHealth != null && agentHealth.status !== "unreachable";
  const agentIdle = agentHealth?.status === "idle";
  const agentBootstrapping = agentHealth?.status === "bootstrapping";

  const healthLabel = !agentReachable
    ? "Offline"
    : agentBootstrapping
      ? "Starting..."
      : agentIdle
        ? "Idle"
        : agentHealth?.active_runs && agentHealth.active_runs > 1
          ? `${agentHealth.active_runs} runs active${atCapacity ? " (full)" : ""}`
          : activeRunHealth?.elapsed_minutes != null
            ? `Active · ${Math.round(activeRunHealth.elapsed_minutes)}m${atCapacity ? " (full)" : ""}`
            : `Active${atCapacity ? " (full)" : ""}`;

  const newRunTitle = !isConfigured
    ? "Configure credentials in Settings first"
    : !agentReachable
      ? "Agent is offline"
      : atCapacity
        ? "Agent is at maximum capacity"
        : undefined;

  const canControl = runStatus !== null && (ACTIVE_STATUSES as readonly RunStatus[]).includes(runStatus) && !busy;

  return (
    <header className="desktop-header relative z-10 flex items-center gap-3 px-4 py-2.5 border-b border-border bg-bg-card header-glow">
      {/* Sidebar toggle */}
      <button
        onClick={onToggleSidebar}
        title={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
        aria-label={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
        className="p-2 rounded hover:bg-white/[0.04] text-text-secondary hover:text-accent-hover transition-colors flex-shrink-0"
      >
        {sidebarCollapsed ? (
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
            <rect x="1" y="2" width="12" height="10" rx="1.5" />
            <line x1="5" y1="2" x2="5" y2="12" />
            <polyline points="7 6 9 7 7 8" />
          </svg>
        ) : (
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
            <rect x="1" y="2" width="12" height="10" rx="1.5" />
            <line x1="5" y1="2" x2="5" y2="12" />
            <polyline points="9 6 7 7 9 8" />
          </svg>
        )}
      </button>

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
        <h1 className="text-title font-bold text-text tracking-tight">AutoFyn</h1>
      </div>

      {/* Repo Selector */}
      <div className="w-px h-4 bg-border" />
      <RepoSelector
        repos={repos}
        activeRepo={activeRepo}
        onSelect={onRepoSwitch}
        dropdownMaxHeight={REPO_DROPDOWN_MAX_HEIGHT}
      />

      {/* Selected run status + run ID */}
      {selectedRun && (
        <motion.div
          initial={{ opacity: 0, x: -8 }}
          animate={{ opacity: 1, x: 0 }}
          className="flex items-center gap-2.5 ml-1"
        >
          <div className="w-px h-4 bg-border" />
          <StatusBadge status={selectedRun.status as RunStatus} size="md" />
          <span className="text-meta text-text-secondary font-medium font-mono hidden sm:inline">
            {selectedRun.id}
          </span>
          <span className="text-meta text-text-secondary font-medium font-mono sm:hidden">
            {selectedRun.id.slice(0, RUN_ID_DISPLAY_LENGTH)}
          </span>
          <button
            onClick={handleCopyRunId}
            title="Copy run ID"
            aria-label="Copy run ID"
            className="p-1 rounded hover:bg-white/[0.04] text-text-secondary hover:text-accent-hover transition-colors"
          >
            {copied ? (
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <polyline points="2 6 5 9 10 3" />
              </svg>
            ) : (
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <rect x="4" y="4" width="7" height="7" rx="1" />
                <path d="M2 8H1.5A1.5 1.5 0 0 1 0 6.5V1.5A1.5 1.5 0 0 1 1.5 0H6.5A1.5 1.5 0 0 1 8 1.5V2" />
              </svg>
            )}
          </button>
        </motion.div>
      )}

      <div className="flex-1" />

      <div className="w-px h-4 bg-border" />

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
        <span className="text-meta text-text-secondary">{healthLabel}</span>
      </div>

      {/* Mobile Access QR */}
      <MobileAccessPopover />

      {/* Settings link */}
      <Link
        href="/settings"
        className="p-2 rounded hover:bg-white/[0.04] text-text-secondary hover:text-accent-hover transition-colors"
        title="Settings"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="3" />
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
        </svg>
      </Link>

      {/* New Run button */}
      <Button
        variant="success"
        size="md"
        onClick={onNewRun}
        disabled={!agentReachable || !isConfigured || atCapacity}
        title={newRunTitle}
        icon={
          <svg width="10" height="10" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
            <line x1="6" y1="2" x2="6" y2="10" />
            <line x1="2" y1="6" x2="10" y2="6" />
          </svg>
        }
      >
        New Run
      </Button>

      {/* Cancel button (sandbox creation phase) */}
      {runStatus === "starting" && selectedRun?.id && (
        <>
          <div className="w-px h-4 bg-border" />
          <RunControls
            runId={selectedRun.id}
            status={runStatus}
            busy={busy}
            onCancel={onCancel}
          />
        </>
      )}

      {/* Stop button */}
      <div className="flex items-center gap-1">
        {sessionLocked && canControl && (
          <Button
            variant="warning"
            size="sm"
            onClick={onUnlock}
            title="Unlock session"
            icon={
              <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                <rect x="1.5" y="4.5" width="7" height="4.5" rx="0.75" />
                <path d="M3 4.5V3a2 2 0 014 0" />
              </svg>
            }
          >
            Unlock
          </Button>
        )}
        {sessionLocked && activeRunHealth?.time_remaining && (
          <span className="text-meta text-[#ffaa00]/80 tabular-nums mr-1 flex items-center gap-1">
            <svg width="8" height="8" viewBox="0 0 8 8" fill="none" stroke="#ffaa00" strokeWidth="1" opacity="0.5">
              <rect x="1.5" y="4" width="5" height="3" rx="0.5" />
              <path d="M2.5 4V3a1.5 1.5 0 013 0v1" />
            </svg>
            {activeRunHealth.time_remaining}
          </span>
        )}
        <Button
          variant="ghost"
          size="sm"
          disabled={!canControl}
          onClick={onStop}
          title="Stop run"
          icon={
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5">
              <rect x="2" y="2" width="6" height="6" rx="0.5" />
            </svg>
          }
        >
          Stop
        </Button>
      </div>
    </header>
  );
}
