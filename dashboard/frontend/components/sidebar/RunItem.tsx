"use client";

import { clsx } from "clsx";
import { motion } from "framer-motion";
import type { Run, RunStatus } from "@/lib/types";
import { STATUS_META } from "@/lib/types";
import { StatusBadge } from "@/components/ui/Badge";
import { timeAgo, formatCost } from "@/lib/format";
import { PROMPT_LABEL_MAX_LEN } from "@/lib/constants";
import { ModelBadge } from "@/components/ui/ModelBadge";

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

  const durationLabel =
    run.duration_minutes > 0 ? `${run.duration_minutes}m` : null;

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
          role="status"
          aria-label={`Run status: ${statusMeta.label}`}
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
      <div className="flex items-center gap-2 mb-1.5">
        <span className={clsx(
          "text-[13px] font-semibold truncate flex-1",
          active ? "text-[#f0f0f0]" : "text-[#e0e0e0]"
        )}>
          {label}
        </span>
        <span className="text-[11px] text-[#888] tabular-nums shrink-0">
          {timeAgo(run.started_at)}
        </span>
      </div>

      {/* Line 2: StatusBadge + model badge + cost */}
      <div className="flex items-center gap-2 mb-0.5 flex-wrap">
        <StatusBadge status={run.status as RunStatus} />
        <ModelBadge modelName={run.model_name} />
        {formatCost(run.total_cost_usd) && (
          <span className="text-[11px] text-[#00ff88]/80 tabular-nums">
            {formatCost(run.total_cost_usd)}
          </span>
        )}
        {durationLabel && (
          <span className="text-[11px] text-[#888] tabular-nums ml-auto">
            {durationLabel}
          </span>
        )}
      </div>

      {/* Line 3: Error preview */}
      {run.error_message && (
        <div className="mt-1.5 text-[11px] text-[#ff4444]/90 truncate">
          {run.error_message.slice(0, 80)}
        </div>
      )}
    </motion.button>
  );
}
