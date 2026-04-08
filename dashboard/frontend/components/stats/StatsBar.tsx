"use client";

import { useMemo } from "react";
import { motion } from "framer-motion";
import type { Run, FeedEvent } from "@/lib/types";

const EMPTY_EVENTS: FeedEvent[] = [];

function computeLiveStats(events: FeedEvent[]) {
  let toolCount = 0;
  let contextTokens = 0;
  let costUsd = 0;

  for (const e of events) {
    if (e._kind === "tool" && e.data.phase === "pre") {
      toolCount++;
    } else if (e._kind === "usage") {
      contextTokens = e.data.context_tokens || 0;
      costUsd = e.data.total_cost_usd || 0;
    }
  }

  return { toolCount, contextTokens, costUsd };
}

function formatTokenCount(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

function Stat({
  icon,
  label,
  value,
  accent,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  accent?: string;
}) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-[#777]">{icon}</span>
      <span className="text-[10px] text-[#777]">{label}</span>
      <span className={`text-[10px] font-semibold tabular-nums ${accent || "text-[#e8e8e8]"}`}>
        {value}
      </span>
    </div>
  );
}

export function StatsBar({
  run,
  connected,
  events = EMPTY_EVENTS,
}: {
  run: Run | null;
  connected: boolean;
  events?: FeedEvent[];
}) {
  const live = useMemo(() => computeLiveStats(events), [events]);

  if (!run) {
    return (
      <div className="h-8 flex items-center px-4 border-t border-[#1a1a1a] bg-[#050505]">
        <span className="text-[10px] text-[#777]">No run selected</span>
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="min-h-[36px] sm:h-8 flex items-center gap-3 sm:gap-5 px-3 sm:px-4 border-t border-[#1a1a1a] bg-[#050505] overflow-x-auto"
    >
      <Stat
        icon={
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M6.5 1L9 3.5 3.5 9H1V6.5L6.5 1z" />
          </svg>
        }
        label="Tools"
        value={String(live.toolCount || run.total_tool_calls || 0)}
      />
      <Stat
        icon={
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5">
            <circle cx="5" cy="5" r="4" />
            <path d="M3.5 5h3M5 3.5v3" />
          </svg>
        }
        label="Cost"
        value={`$${(live.costUsd || run.total_cost_usd || 0).toFixed(2)}`}
        accent="text-[#00ff88]"
      />
      <Stat
        icon={
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5">
            <rect x="1" y="1" width="8" height="8" rx="1" />
            <path d="M1 1v8" />
          </svg>
        }
        label="Context"
        value={live.contextTokens > 0 ? formatTokenCount(live.contextTokens) : "—"}
        accent="text-[#88ccff]"
      />
      {run.pr_url && (
        <a
          href={run.pr_url}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1 text-[10px] text-[#88ccff] hover:text-[#aaddff] transition-colors"
        >
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5">
            <circle cx="3" cy="3" r="1.5" />
            <circle cx="7" cy="3" r="1.5" />
            <circle cx="3" cy="7" r="1.5" />
            <line x1="3" y1="4.5" x2="3" y2="5.5" />
            <path d="M7 4.5c0 1.5-1.5 2-4 3" />
          </svg>
          PR #{run.pr_url.split("/").pop()}
        </a>
      )}

      <div className="flex-1" />

      <div className="flex items-center gap-1.5">
        <span
          className={`h-1.5 w-1.5 rounded-full ${
            connected ? "bg-[#00ff88]" : "bg-[#444]"
          }`}
          style={connected ? { boxShadow: "0 0 4px rgba(0, 255, 136, 0.4)" } : undefined}
        />
        <span className="text-[10px] text-[#888]">
          {connected ? "Live" : "Disconnected"}
        </span>
      </div>
    </motion.div>
  );
}
