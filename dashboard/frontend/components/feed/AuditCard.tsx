"use client";

import { useState, useMemo } from "react";
import { motion } from "framer-motion";
import { clsx } from "clsx";
import type { AuditEvent } from "@/lib/types";
import { AUDIT_EVENT_META } from "@/lib/types";
import { getAuditIcon } from "@/components/ui/ToolIcons";
import { fmtTime, UNKNOWN_TIME_LABEL, formatHoursMinutes } from "@/lib/eventCardHelpers";
import { CARD_FADE_DURATION, CARD_FADE_EASE, MS_PER_SECOND } from "@/lib/constants";

/* ── Helpers ── */

function formatEpoch(epoch: number | null | undefined): string {
  if (!epoch) return UNKNOWN_TIME_LABEL;
  const d = new Date(epoch * MS_PER_SECOND);
  const now = Date.now();
  const diffMs = epoch * MS_PER_SECOND - now;
  const time = d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
  if (diffMs <= 0) return `${time} (ready)`;
  return `${time} (${formatHoursMinutes(diffMs)})`;
}

/* ── Audit Event Card ── */

export function AuditCard({ event }: { event: AuditEvent }) {
  const [expanded, setExpanded] = useState(false);
  const meta = AUDIT_EVENT_META[event.event_type] || { label: event.event_type, color: "text-[#777]", bg: "bg-[#777]/[0.03]", iconColor: "#777" };

  const preview = useMemo(() => {
    const d = event.details;
    switch (event.event_type) {
      case "round_complete":
        return `Round ${d.round} · ${d.turns} turns · $${(d.cost_usd as number)?.toFixed(3) || "?"} · ${(d.elapsed_minutes as number)?.toFixed(1)}min`;
      case "run_started":
        return `${d.model || "claude"} · ${d.branch || "?"}${d.has_custom_prompt ? " · custom prompt" : ""}`;
      case "pr_created":
        return (d.url as string) || "";
      case "pr_failed":
        return ((d.error as string) || "").slice(0, 100);
      case "session_ended":
        return `${d.changes_made || 0} changes · ${(d.elapsed_minutes as number)?.toFixed(1) || "?"}min`;
      case "planner_invoked":
        return `Round ${d.round} · ${d.tool_summary || ""}`;
      case "killed":
        return `${(d.elapsed_minutes as number)?.toFixed(1) || "?"}min elapsed`;
      case "fatal_error":
        return ((d.error as string) || "").slice(0, 100);
      case "rate_limit":
        return `${d.status || "?"} · resets ${formatEpoch(d.resets_at as number)}`;
      case "rate_limit_paused":
        return d.reason ? `${d.reason} · resets ${formatEpoch(d.resets_at as number)}` : `resets ${formatEpoch(d.resets_at as number)}`;
      case "end_session_denied":
        return `${d.remaining_minutes || "?"}m remaining`;
      case "sdk_config":
        return `${d.model || "?"} · effort:${d.effort || "?"} · ${(d.mcp_servers as string[])?.join(", ") || ""}`;
      case "stop_requested":
        return (d.reason as string) || "";
      default:
        return JSON.stringify(d).slice(0, 120);
    }
  }, [event]);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: CARD_FADE_DURATION, ease: CARD_FADE_EASE }}
      className={clsx(
        "group border-l-[3px] rounded-r px-3 py-1.5 cursor-pointer transition-colors",
        meta.bg,
        "hover:bg-white/[0.025]"
      )}
      // borderLeftColor must be set via inline style — Tailwind cannot statically
      // extract dynamic template-literal class names like `border-l-[${color}]`.
      style={{ borderLeftColor: meta.iconColor }}
      onClick={() => setExpanded(!expanded)}
    >
      <div className="flex items-center gap-2 min-w-0">
        <span className="text-[9px] text-[#888] tabular-nums shrink-0 w-[52px]">
          {fmtTime(event.ts)}
        </span>

        <span className="shrink-0 opacity-70">
          {getAuditIcon(event.event_type, meta.iconColor)}
        </span>

        <span className={clsx("text-[10px] font-semibold shrink-0", meta.color)}>
          {meta.label}
        </span>

        <span className="text-[10px] text-[#999] truncate min-w-0 flex-1">
          {preview}
        </span>

        <svg
          width="10"
          height="10"
          viewBox="0 0 10 10"
          fill="none"
          stroke="#888"
          strokeWidth="1.5"
          strokeLinecap="round"
          className={clsx("shrink-0 transition-transform duration-150", expanded && "rotate-90")}
        >
          <polyline points="3 2 7 5 3 8" />
        </svg>
      </div>

      {expanded && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: "auto", opacity: 1 }}
          transition={{ duration: CARD_FADE_DURATION, ease: CARD_FADE_EASE }}
          className="overflow-hidden"
        >
          <div className="mt-2 border-t border-white/[0.04] pt-2">
            {event.event_type === "session_ended" && !!event.details.summary && (
              <div className="text-[10px] text-[#aaa] whitespace-pre-wrap break-words leading-relaxed mb-2">
                {String(event.details.summary)}
              </div>
            )}
            {event.event_type === "planner_invoked" && !!event.details.round_summary && (
              <div className="text-[10px] text-[#aaa] whitespace-pre-wrap break-words leading-relaxed mb-2">
                {String(event.details.round_summary)}
              </div>
            )}
            {event.event_type === "end_session_denied" && !!event.details.summary && (
              <div className="text-[10px] text-[#aaa] whitespace-pre-wrap break-words leading-relaxed mb-2">
                {String(event.details.summary)}
              </div>
            )}
            {event.event_type === "pr_created" && !!event.details.url && (
              <a
                href={String(event.details.url)}
                target="_blank"
                rel="noopener noreferrer"
                className="text-[10px] text-[#88ccff] hover:text-[#aaddff] underline underline-offset-2"
                onClick={(e) => e.stopPropagation()}
              >
                {String(event.details.url)}
              </a>
            )}
            {/* Raw JSON fallback */}
            <pre className="text-[10px] text-[#666] bg-black/30 rounded border border-[#1a1a1a] p-2 overflow-x-auto max-h-[400px] overflow-y-auto whitespace-pre-wrap break-all">
              {JSON.stringify(event.details, null, 2)}
            </pre>
          </div>
        </motion.div>
      )}
    </motion.div>
  );
}
