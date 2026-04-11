"use client";

import { useState, useMemo } from "react";
import { motion } from "framer-motion";
import { clsx } from "clsx";
import type { ToolCall } from "@/lib/types";
import { getToolCategory, TOOL_COLORS } from "@/lib/types";
import { getToolIcon } from "@/components/ui/ToolIcons";
import {
  fmtTime,
  fmtDuration,
  extractToolSummary,
  extractOutputSummary,
} from "@/lib/eventCardHelpers";
import { CARD_FADE_DURATION, CARD_FADE_EASE } from "@/lib/constants";

/* ── Tool Call Parts ── */

function DiffViewer({ patch }: { patch: Array<Record<string, unknown>> }) {
  return (
    <div className="font-mono text-[10px] leading-relaxed">
      {patch.map((hunk, hi) => {
        const lines = (hunk.lines as string[]) || [];
        const oldStart = (hunk.oldStart as number) || 0;
        const newStart = (hunk.newStart as number) || 0;
        return (
          <div key={hi} className="mb-2">
            <div className="text-[9px] text-[#999] px-2 py-1 bg-[#0a0a0a] border-b border-[#1a1a1a]">
              @@ -{oldStart},{(hunk.oldLines as number) || 0} +{newStart},{(hunk.newLines as number) || 0} @@
            </div>
            {lines.map((line, li) => {
              const isAdd = line.startsWith("+") && !line.startsWith("+++");
              const isDel = line.startsWith("-") && !line.startsWith("---");
              return (
                <div
                  key={li}
                  className={clsx(
                    "px-2 whitespace-pre-wrap break-all",
                    isAdd && "bg-[#00ff88]/[0.05] text-[#88ffbb]",
                    isDel && "bg-[#ff4444]/[0.05] text-[#ff8888]",
                    !isAdd && !isDel && "text-[#666]"
                  )}
                >
                  {line}
                </div>
              );
            })}
          </div>
        );
      })}
    </div>
  );
}

function BashOutput({ output }: { output: Record<string, unknown> }) {
  const stdout = (output.stdout as string) || "";
  const stderr = (output.stderr as string) || "";
  const text = stdout || stderr;
  if (!text) return <span className="text-[10px] text-[#888] italic">(no output)</span>;

  return (
    <pre className="text-[10px] text-[#aaa] whitespace-pre-wrap break-all leading-relaxed">
      {stderr && <span className="text-[#ff6666]">{stderr}</span>}
      {stdout}
    </pre>
  );
}

function TodoDisplay({ todos }: { todos: Array<{ status: string; content: string; activeForm?: string }> }) {
  return (
    <div className="space-y-1">
      {todos.map((t, i) => (
        <div key={i} className="flex items-start gap-2 text-[10px]">
          {t.status === "completed" ? (
            <span className="text-[#00ff88] mt-px shrink-0">
              <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5">
                <polyline points="2 5 4 7 8 3" />
              </svg>
            </span>
          ) : t.status === "in_progress" ? (
            <span className="text-[#ffaa00] mt-px shrink-0 animate-pulse">
              <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5">
                <circle cx="5" cy="5" r="3" />
              </svg>
            </span>
          ) : (
            <span className="text-[#888] mt-px shrink-0">
              <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5">
                <rect x="2" y="2" width="6" height="6" rx="1" />
              </svg>
            </span>
          )}
          <span className={clsx(
            t.status === "completed" && "text-[#666] line-through",
            t.status === "in_progress" && "text-[#ccc]",
            t.status === "pending" && "text-[#888]"
          )}>
            {t.content}
          </span>
        </div>
      ))}
    </div>
  );
}

/* ── Tool Call Card ── */

export function ToolCallCard({ tc }: { tc: ToolCall }) {
  const [expanded, setExpanded] = useState(false);
  const denied = !tc.permitted;
  const isPlanner = tc.agent_role === "planner";
  const isPending = tc.phase === "pre" && !tc.output_data;

  const category = getToolCategory(tc.tool_name);
  const colors = TOOL_COLORS[category];
  const summary = useMemo(() => extractToolSummary(tc), [tc]);
  const outputSummary = useMemo(() => extractOutputSummary(tc), [tc]);

  const borderColor = denied
    ? "border-l-[#ff4444]"
    : isPlanner
      ? "border-l-[#ff8844]"
      : colors.border;

  const bgColor = denied
    ? "bg-[#ff4444]/[0.02]"
    : isPlanner
      ? "bg-[#ff8844]/[0.02]"
      : colors.bg;

  const hasDiff = !!(tc.output_data?.structuredPatch && (category === "edit" || category === "write"));
  const hasBashOutput = !!(category === "bash" && tc.output_data);
  const hasTodos = !!(category === "todo" && tc.input_data?.todos);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: CARD_FADE_DURATION, ease: CARD_FADE_EASE }}
      className={clsx(
        "group border-l-[3px] rounded-r px-3 py-1.5 cursor-pointer transition-colors",
        borderColor,
        bgColor,
        "hover:bg-white/[0.025]"
      )}
      onClick={() => setExpanded(!expanded)}
    >
      {/* Header row */}
      <div className="flex items-center gap-2 min-w-0">
        <span className="text-[9px] text-[#888] tabular-nums shrink-0 w-[52px]">
          {fmtTime(tc.ts)}
        </span>

        {/* Tool icon */}
        <span className="shrink-0 opacity-70">
          {getToolIcon(category, denied ? "#ff4444" : isPlanner ? "#ff8844" : colors.iconColor)}
        </span>

        {/* Agent role badge */}
        <span
          className={clsx(
            "text-[9px] font-bold uppercase tracking-[0.12em] rounded px-1 py-0.5 shrink-0",
            isPlanner
              ? "text-[#ff8844] bg-[#ff8844]/12"
              : "text-[#999] bg-white/[0.03]"
          )}
        >
          {isPlanner ? "PLN" : "WRK"}
        </span>

        {/* Tool name */}
        <span className={clsx("text-[10px] font-semibold shrink-0", denied ? "text-[#ff4444]" : colors.text)}>
          {tc.tool_name}
        </span>

        {/* Status indicators */}
        {isPending && (
          <span className="text-[9px] text-[#ffaa00]/70 shrink-0 animate-pulse flex items-center gap-1">
            <svg width="8" height="8" viewBox="0 0 8 8" fill="none">
              <circle cx="4" cy="4" r="3" stroke="#ffaa00" strokeWidth="1" strokeDasharray="2 2" style={{ animation: "spin 2s linear infinite" }} />
            </svg>
            running
          </span>
        )}

        {denied && (
          <span className="inline-flex items-center gap-0.5 text-[9px] font-bold text-[#ff4444] bg-[#ff4444]/8 rounded px-1.5 py-0.5 shrink-0 tracking-wider">
            DENIED
          </span>
        )}

        {tc.duration_ms != null && (
          <span className="text-[9px] text-[#999] shrink-0 tabular-nums">
            {fmtDuration(tc.duration_ms)}
          </span>
        )}

        {outputSummary && (
          <span className={clsx("text-[9px] shrink-0 tabular-nums", colors.text, "opacity-50")}>
            {outputSummary}
          </span>
        )}

        {/* Summary */}
        <span className="text-[10px] text-[#999] truncate min-w-0 flex-1">
          {denied ? tc.deny_reason : summary}
        </span>

        {/* Expand chevron */}
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

      {/* Expanded content */}
      {expanded && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: "auto", opacity: 1 }}
          transition={{ duration: CARD_FADE_DURATION, ease: CARD_FADE_EASE }}
          className="overflow-hidden"
        >
          <div className="mt-2 space-y-2 border-t border-white/[0.04] pt-2">
            {hasTodos && (
              <div>
                <div className="text-[9px] uppercase tracking-[0.15em] text-[#999] mb-1">Tasks</div>
                <TodoDisplay todos={tc.input_data!.todos as Array<{ status: string; content: string; activeForm?: string }>} />
              </div>
            )}

            {hasDiff && (
              <div>
                <div className="text-[9px] uppercase tracking-[0.15em] text-[#999] mb-1">Diff</div>
                <div className="bg-black/30 rounded border border-[#1a1a1a] overflow-hidden max-h-[500px] overflow-y-auto">
                  <DiffViewer patch={tc.output_data!.structuredPatch as Array<Record<string, unknown>>} />
                </div>
              </div>
            )}

            {hasBashOutput && (
              <div>
                <div className="text-[9px] uppercase tracking-[0.15em] text-[#999] mb-1">Output</div>
                <div className="bg-black/30 rounded border border-[#1a1a1a] p-2 max-h-[500px] overflow-y-auto">
                  <BashOutput output={tc.output_data!} />
                </div>
              </div>
            )}

            {/* Raw Input - always available */}
            {tc.input_data && !hasTodos && (
              <div>
                <div className="text-[9px] uppercase tracking-[0.15em] text-[#999] mb-1">Input</div>
                <pre className="text-[10px] text-[#777] bg-black/30 rounded border border-[#1a1a1a] p-2 overflow-x-auto max-h-[400px] overflow-y-auto whitespace-pre-wrap break-all">
                  {JSON.stringify(tc.input_data, null, 2)}
                </pre>
              </div>
            )}

            {/* Raw Output - show when no specialized renderer */}
            {tc.output_data && !hasDiff && !hasBashOutput && (
              <div>
                <div className="text-[9px] uppercase tracking-[0.15em] text-[#00ff88]/50 mb-1">Result</div>
                <pre className="text-[10px] text-[#777] bg-black/30 rounded border border-[#1a1a1a] p-2 overflow-x-auto max-h-[400px] overflow-y-auto whitespace-pre-wrap break-all">
                  {JSON.stringify(tc.output_data, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </motion.div>
      )}
    </motion.div>
  );
}
