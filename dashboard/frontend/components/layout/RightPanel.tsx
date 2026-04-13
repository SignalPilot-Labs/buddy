"use client";

import { AnimatePresence, motion } from "framer-motion";
import type { FeedEvent } from "@/lib/types";
import { WorkTree } from "@/components/worktree/WorkTree";
import { ContainerLogs } from "@/components/logs/ContainerLogs";

const TAB_FADE_DURATION = 0.15;

export interface RightPanelProps {
  runId: string | null;
  events: FeedEvent[];
  activeTab: "changes" | "logs";
  onTabChange: (tab: "changes" | "logs") => void;
}

function GitBranchIcon() {
  return (
    <svg width="10" height="10" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="4" cy="3" r="1.5" />
      <circle cx="4" cy="13" r="1.5" />
      <circle cx="12" cy="6" r="1.5" />
      <line x1="4" y1="4.5" x2="4" y2="11.5" />
      <path d="M4 6c0-1.5 8-1.5 8-4.5" />
    </svg>
  );
}

function TerminalIcon() {
  return (
    <svg width="10" height="10" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="2" width="12" height="12" rx="1.5" />
      <polyline points="5 6 8 9 5 12" />
      <line x1="9" y1="12" x2="13" y2="12" />
    </svg>
  );
}

export function RightPanel({ runId, events, activeTab, onTabChange }: RightPanelProps) {
  return (
    <div className="flex flex-col border-l border-border w-[280px] flex-shrink-0 min-h-0">
      {/* Segmented tab bar */}
      <div className="bg-bg-card p-2 shrink-0">
        <div className="bg-bg-hover rounded-lg p-0.5 flex" role="tablist">
          <button
            role="tab"
            aria-selected={activeTab === "changes"}
            onClick={() => onTabChange("changes")}
            className={`flex-1 flex items-center justify-center gap-1.5 rounded-md px-3 py-1 text-meta font-medium transition-all focus-visible:ring-1 focus-visible:ring-[#00ff88]/40 ${
              activeTab === "changes"
                ? "bg-border text-text shadow-sm"
                : "text-text-secondary hover:text-accent-hover"
            }`}
          >
            <GitBranchIcon />
            Changes
          </button>
          <button
            role="tab"
            aria-selected={activeTab === "logs"}
            onClick={() => onTabChange("logs")}
            className={`flex-1 flex items-center justify-center gap-1.5 rounded-md px-3 py-1 text-meta font-medium transition-all focus-visible:ring-1 focus-visible:ring-[#00ff88]/40 ${
              activeTab === "logs"
                ? "bg-border text-text shadow-sm"
                : "text-text-secondary hover:text-accent-hover"
            }`}
          >
            <TerminalIcon />
            Logs
          </button>
        </div>
      </div>

      {/* Panel content */}
      <AnimatePresence mode="wait">
        <motion.div
          key={activeTab}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: TAB_FADE_DURATION }}
          className="flex-1 min-h-0 overflow-hidden"
        >
          {activeTab === "changes" ? (
            <WorkTree events={events} runId={runId} />
          ) : (
            <ContainerLogs runId={runId} />
          )}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
