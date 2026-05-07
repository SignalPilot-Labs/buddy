"use client";

import { motion, AnimatePresence } from "framer-motion";
import type { Run, FeedEvent, RunStatus, ConnectionState } from "@/lib/types";
import { RunList } from "@/components/sidebar/RunList";
import { EventFeed } from "@/components/feed/EventFeed";
import { CommandInput } from "@/components/controls/CommandInput";
import { WorkTree } from "@/components/worktree/WorkTree";
import { ContainerLogs } from "@/components/logs/ContainerLogs";
import { MobileTab } from "@/components/mobile/MobileTab";
import { ConnectionBanner } from "@/components/ui/ConnectionBanner";
import type { ToastVariant } from "@/components/ui/Toast";

export interface MobileLayoutProps {
  mobilePanel: "feed" | "runs" | "changes" | "logs";
  setMobilePanel: (v: "feed" | "runs" | "changes" | "logs") => void;
  runs: Run[];
  selectedRunId: string | null;
  runsLoading: boolean;
  allEvents: FeedEvent[];
  runStatus: RunStatus | null;
  selectedRun: Run | null;
  connected: boolean;
  connectionState: ConnectionState;
  historyTruncated: boolean;
  busy: boolean;
  historyLoading: boolean;
  controlsOpen: boolean;
  setControlsOpen: (v: boolean) => void;
  onSelectRun: (id: string) => void;
  onPause: () => void;
  onResume: () => void;
  onInject: (prompt: string) => void;
  onRestart: (prompt: string) => void;
  showToast: (message: string, variant: ToastVariant) => void;
}

function RunsIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M4 6h16M4 12h16M4 18h10" />
    </svg>
  );
}

function FeedIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M12 20V10M18 20V4M6 20v-4" />
    </svg>
  );
}

function ChangesIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6" />
    </svg>
  );
}

function LogsIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <path d="M7 8l3 3-3 3" />
      <line x1="11" y1="16" x2="17" y2="16" />
    </svg>
  );
}

function ControlsIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  );
}

const runActive = (status: RunStatus | null): boolean =>
  status === "starting" || status === "running" || status === "paused" || status === "rate_limited";

export function MobileLayout({
  mobilePanel,
  setMobilePanel,
  runs,
  selectedRunId,
  runsLoading,
  allEvents,
  runStatus,
  selectedRun,
  connected,
  connectionState,
  historyTruncated,
  busy,
  historyLoading,
  controlsOpen,
  setControlsOpen,
  onSelectRun,
  onPause,
  onResume,
  onInject,
  onRestart,
  showToast,
}: MobileLayoutProps) {
  return (
    <>
      {/* Mobile panel content */}
      <div className="flex-1 flex flex-col min-h-0 pb-14">
        <AnimatePresence mode="wait">
          {mobilePanel === "runs" && (
            <motion.div key="runs" className="flex-1 flex flex-col min-h-0" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }}>
              <RunList
                runs={runs}
                activeId={selectedRunId}
                onSelect={(id) => { onSelectRun(id); setMobilePanel("feed"); }}
                loading={runsLoading}
                mobile
              />
            </motion.div>
          )}
          {mobilePanel === "feed" && (
            <motion.div key="feed" className="relative flex-1 flex flex-col min-h-0" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }}>
              <ConnectionBanner
                connectionState={connectionState}
                runStatus={runStatus}
                showToast={showToast}
                selectedRunId={selectedRunId}
              />
              <EventFeed
                events={allEvents}
                runActive={runActive(runStatus)}
                runPaused={runStatus === "paused"}
                isLoading={historyLoading}
                historyTruncated={historyTruncated}
                hasSelectedRun={selectedRunId !== null}
              />
              <CommandInput
                runId={selectedRunId}
                status={runStatus}
                run={selectedRun}
                connected={connected}
                events={allEvents}
                busy={busy}
                onPause={onPause}
                onResume={onResume}
                onInject={onInject}
                onRestart={onRestart}
              />
            </motion.div>
          )}
          {mobilePanel === "changes" && (
            <motion.div key="changes" className="flex-1 flex flex-col min-h-0" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }}>
              <WorkTree events={allEvents} runId={selectedRunId} runStatus={runStatus} />
            </motion.div>
          )}
          {mobilePanel === "logs" && (
            <motion.div key="logs" className="flex-1 flex flex-col min-h-0" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }}>
              <ContainerLogs runId={selectedRunId} />
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Mobile bottom tab bar */}
      <nav className="mobile-bottom-bar">
        <MobileTab
          icon={<RunsIcon />}
          label="Runs"
          active={mobilePanel === "runs"}
          onClick={() => setMobilePanel("runs")}
          badge={runs.length > 0 ? runs.length : null}
        />
        <MobileTab
          icon={<FeedIcon />}
          label="Feed"
          active={mobilePanel === "feed"}
          onClick={() => setMobilePanel("feed")}
          badge={allEvents.length > 0 ? allEvents.length : null}
        />
        <MobileTab
          icon={<ChangesIcon />}
          label="Changes"
          active={mobilePanel === "changes"}
          onClick={() => setMobilePanel("changes")}
        />
        <MobileTab
          icon={<LogsIcon />}
          label="Logs"
          active={mobilePanel === "logs"}
          onClick={() => setMobilePanel("logs")}
        />
        <MobileTab
          icon={<ControlsIcon />}
          label="Controls"
          active={controlsOpen}
          onClick={() => setControlsOpen(true)}
        />
      </nav>
    </>
  );
}
