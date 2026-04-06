"use client";

import { useState, useMemo } from "react";
import type { ReactElement } from "react";
import { motion } from "framer-motion";
import { clsx } from "clsx";
import type { ToolCall } from "@/lib/types";
import { getToolCategory, TOOL_COLORS } from "@/lib/types";
import { getToolIcon } from "@/components/ui/ToolIcons";
import { useTranslation } from "@/hooks/useTranslation";
import { fmtTime, fmtDuration } from "@/components/feed/card-helpers";
import { DiffBlock, TerminalOutput, TodoDisplay } from "@/components/feed/ToolOutputRenderers";
import { extractToolSummary, extractOutputSummary } from "@/components/feed/tool-call-helpers";

function ExpandedContent({ tc }: { tc: ToolCall }): ReactElement {
  const { t } = useTranslation();
  const category = getToolCategory(tc.tool_name);
  const hasDiff = !!(tc.output_data?.structuredPatch && (category === "edit" || category === "write"));
  const hasBashOutput = !!(category === "bash" && tc.output_data);
  const hasTodos = !!(category === "todo" && tc.input_data?.todos);

  return (
    <div className="mt-2 space-y-2 border-t border-white/[0.04] pt-2">
      {hasTodos && (
        <div>
          <div className="text-[9px] uppercase tracking-[0.15em] text-[#999] mb-1">{t.eventCard.tasks}</div>
          <TodoDisplay todos={tc.input_data!.todos as Array<{ status: string; content: string }>} />
        </div>
      )}
      {hasDiff && (
        <div>
          <div className="text-[9px] uppercase tracking-[0.15em] text-[#999] mb-1">{t.eventCard.diff}</div>
          <DiffBlock patch={tc.output_data!.structuredPatch as Array<Record<string, unknown>>} />
        </div>
      )}
      {hasBashOutput && (
        <div>
          <div className="text-[9px] uppercase tracking-[0.15em] text-[#999] mb-1">{t.eventCard.output}</div>
          <div className="bg-black/30 rounded border border-[#1a1a1a] p-2 max-h-[500px] overflow-y-auto">
            <TerminalOutput
              stdout={String(tc.output_data!.stdout || "")}
              stderr={String(tc.output_data!.stderr || "")}
            />
          </div>
        </div>
      )}
      {tc.input_data && !hasTodos && (
        <div>
          <div className="text-[9px] uppercase tracking-[0.15em] text-[#999] mb-1">{t.eventCard.input}</div>
          <pre className="text-[10px] text-[#777] bg-black/30 rounded border border-[#1a1a1a] p-2 overflow-x-auto max-h-[400px] overflow-y-auto whitespace-pre-wrap break-all">
            {JSON.stringify(tc.input_data, null, 2)}
          </pre>
        </div>
      )}
      {tc.output_data && !hasDiff && !hasBashOutput && (
        <div>
          <div className="text-[9px] uppercase tracking-[0.15em] text-[#00ff88]/50 mb-1">{t.eventCard.result}</div>
          <pre className="text-[10px] text-[#777] bg-black/30 rounded border border-[#1a1a1a] p-2 overflow-x-auto max-h-[400px] overflow-y-auto whitespace-pre-wrap break-all">
            {JSON.stringify(tc.output_data, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

export function ToolCallCard({ tc }: { tc: ToolCall }): ReactElement {
  const [expanded, setExpanded] = useState(false);
  const { t } = useTranslation();
  const denied = !tc.permitted;
  const isPlanner = tc.agent_role === "planner";
  const isPending = tc.phase === "pre" && !tc.output_data;

  const category = getToolCategory(tc.tool_name);
  const colors = TOOL_COLORS[category];
  const summary = useMemo(() => extractToolSummary(tc, t.eventCard), [tc, t]);
  const outputSummary = useMemo(() => extractOutputSummary(tc, t.eventCard), [tc, t]);

  const borderColor = denied ? "border-l-[#ff4444]" : isPlanner ? "border-l-[#ff8844]" : colors.border;
  const bgColor = denied ? "bg-[#ff4444]/[0.02]" : isPlanner ? "bg-[#ff8844]/[0.02]" : colors.bg;

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.15 }}
      className={clsx(
        "group border-l-[3px] rounded-r px-3 py-1.5 cursor-pointer transition-colors",
        borderColor,
        bgColor,
        "hover:bg-white/[0.025]",
      )}
      onClick={() => setExpanded(!expanded)}
    >
      <div className="flex items-center gap-2 min-w-0">
        <span className="text-[9px] text-[#888] tabular-nums shrink-0 w-[52px]">{fmtTime(tc.ts)}</span>
        <span className="shrink-0 opacity-70">
          {getToolIcon(category, denied ? "#ff4444" : isPlanner ? "#ff8844" : colors.iconColor)}
        </span>
        <span
          className={clsx(
            "text-[9px] font-bold uppercase tracking-[0.12em] rounded px-1 py-0.5 shrink-0",
            isPlanner ? "text-[#ff8844] bg-[#ff8844]/12" : "text-[#999] bg-white/[0.03]",
          )}
        >
          {isPlanner ? t.eventCard.planner : t.eventCard.worker}
        </span>
        <span className={clsx("text-[10px] font-semibold shrink-0", denied ? "text-[#ff4444]" : colors.text)}>
          {tc.tool_name}
        </span>
        {isPending && (
          <span className="text-[9px] text-[#ffaa00]/70 shrink-0 animate-pulse flex items-center gap-1">
            <svg width="8" height="8" viewBox="0 0 8 8" fill="none">
              <circle cx="4" cy="4" r="3" stroke="#ffaa00" strokeWidth="1" strokeDasharray="2 2" style={{ animation: "spin 2s linear infinite" }} />
            </svg>
            {t.eventCard.running}
          </span>
        )}
        {denied && (
          <span className="inline-flex items-center gap-0.5 text-[9px] font-bold text-[#ff4444] bg-[#ff4444]/8 rounded px-1.5 py-0.5 shrink-0 tracking-wider">
            {t.eventCard.denied}
          </span>
        )}
        {tc.duration_ms != null && (
          <span className="text-[9px] text-[#999] shrink-0 tabular-nums">{fmtDuration(tc.duration_ms)}</span>
        )}
        {outputSummary && (
          <span className={clsx("text-[9px] shrink-0 tabular-nums", colors.text, "opacity-50")}>{outputSummary}</span>
        )}
        <span className="text-[10px] text-[#999] truncate min-w-0 flex-1">
          {denied ? tc.deny_reason : summary}
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
          transition={{ duration: 0.2 }}
          className="overflow-hidden"
        >
          <ExpandedContent tc={tc} />
        </motion.div>
      )}
    </motion.div>
  );
}
