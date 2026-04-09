"use client";

import { clsx } from "clsx";
import { motion } from "framer-motion";
import type { Run, RunStatus } from "@/lib/types";
import { STATUS_META } from "@/lib/types";
import { StatusBadge } from "@/components/ui/Badge";
import { timeAgo, formatCost, formatTokens } from "@/lib/format";
import { PROMPT_LABEL_MAX_LEN } from "@/lib/constants";

export function RunItem({
  run,
  active,
  onClick,
  collapsed,
}: {
  run: Run;
  active: boolean;
  onClick: () => void;
  collapsed?: boolean;
}) {
  const label = run.custom_prompt
    ? run.custom_prompt.slice(0, PROMPT_LABEL_MAX_LEN)
    : run.branch_name.replace("autofyn/", "").slice(0, 20);

  const statusMeta = STATUS_META[run.status as RunStatus] || STATUS_META.error;

  if (collapsed) {
    return (
      <motion.button
        layout
        onClick={onClick}
        title={label}
        className={clsx(
          "group relative w-full flex items-center justify-center py-3 border-b border-[#1a1a1a]/60 transition-colors focus-visible:outline-1 focus-visible:outline-[#00ff88]",
          active ? "bg-white/[0.03]" : "hover:bg-white/[0.04]"
        )}
      >
        {active && (
          <motion.div
            layoutId="sidebar-indicator"
            className="absolute left-0 top-0 bottom-0 w-[2px] bg-[#00ff88]"
            transition={{ type: "spring", stiffness: 400, damping: 30 }}
          />
        )}
        <span
          className={clsx(
            "h-2 w-2 rounded-full",
            statusMeta.dot,
            statusMeta.pulse && "animate-pulse"
          )}
        />
      </motion.button>
    );
  }

  return (
    <motion.button
      layout
      onClick={onClick}
      className={clsx(
        "group relative w-full text-left px-4 py-3 border-b border-[#1a1a1a]/60 transition-colors focus-visible:outline-1 focus-visible:outline-[#00ff88]",
        active
          ? "bg-white/[0.03]"
          : "hover:bg-white/[0.04]"
      )}
    >
      {active && (
        <motion.div
          layoutId="sidebar-indicator"
          className="absolute left-0 top-0 bottom-0 w-[2px] bg-[#00ff88]"
          transition={{ type: "spring", stiffness: 400, damping: 30 }}
        />
      )}

      {/* Line 1: label + time ago */}
      <div className="flex items-center gap-2 mb-1">
        <span className={clsx(
          "text-[12px] font-medium truncate flex-1",
          active ? "text-[#e8e8e8]" : "text-[#ccc]"
        )}>
          {label}
        </span>
        <span className="text-[10px] text-[#666] tabular-nums shrink-0">
          {timeAgo(run.started_at)}
        </span>
      </div>

      {/* Line 2: StatusBadge + tool count + cost */}
      <div className="flex items-center gap-2 mb-0.5">
        <StatusBadge status={run.status as RunStatus} />
        {run.total_tool_calls > 0 && (
          <span className="flex items-center gap-0.5 text-[10px] text-[#888]">
            <svg width="8" height="8" viewBox="0 0 8 8" fill="none" stroke="currentColor" strokeWidth="1">
              <path d="M5.5 1L7 2.5 2.5 7H1V5.5L5.5 1z" />
            </svg>
            {run.total_tool_calls}
          </span>
        )}
        {formatCost(run.total_cost_usd) && (
          <span className="text-[10px] text-[#00ff88]/70 tabular-nums">
            {formatCost(run.total_cost_usd)}
          </span>
        )}
        {(run.total_input_tokens || 0) > 0 && (
          <span className="text-[10px] text-[#666] tabular-nums">
            {formatTokens(run.total_input_tokens)}↓
          </span>
        )}
      </div>

      {/* Line 3: Error preview */}
      {run.error_message && (
        <div className="mt-1 text-[10px] text-[#ff4444]/80 truncate">
          {run.error_message.slice(0, 80)}
        </div>
      )}
    </motion.button>
  );
}
