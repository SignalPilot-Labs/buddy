"use client";

import { useState, useMemo, useEffect } from "react";
import { motion } from "framer-motion";
import { clsx } from "clsx";
import type { ToolCall } from "@/lib/types";
import { getToolCategory, type ToolCategory } from "@/lib/types";
import { getToolIcon } from "@/components/ui/ToolIcons";
import { Chevron } from "@/components/feed/ToolDisplayCards";
import { AgentRunExpanded } from "@/components/feed/AgentRunExpanded";
import {
  fmtTime,
  fmtDuration,
  shortPath,
  IDLE_WARN_MS,
} from "@/components/feed/eventCardHelpers";

export function AgentRunCard({
  tool,
  childTools,
  finalText,
  agentType,
  ts,
  runActive = false,
  runPaused = false,
}: {
  tool: ToolCall;
  childTools: ToolCall[];
  finalText: string;
  agentType: string;
  ts: string;
  runActive?: boolean;
  runPaused?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const [showPrompt, setShowPrompt] = useState(false);
  const [showFinalText, setShowFinalText] = useState(false);
  const [now, setNow] = useState(Date.now());
  // No fallbacks: description and subagent_type come from the Task tool
  // input; agentType comes from the subagent_start audit event. A missing
  // value here is a bug upstream (orphan post, missing audit), not something
  // to paper over with a "general" / "Sub-agent task" placeholder.
  const input = tool.input_data || {};
  const description = (input.description as string) || "";
  const prompt = (input.prompt as string) || "";
  const subType = agentType || (input.subagent_type as string) || "";
  const isPending =
    runActive && !runPaused && tool.phase === "pre" && !tool.output_data;

  const lastActivityTs =
    childTools.length > 0
      ? new Date(childTools[childTools.length - 1].ts).getTime()
      : new Date(ts).getTime();
  const idleMs = isPending ? now - lastActivityTs : 0;
  const isIdle = idleMs > IDLE_WARN_MS;
  const idleSec = Math.floor(idleMs / 1000);
  const isFinalizing =
    isPending && childTools.length > 0 && idleMs > 3000 && !isIdle;

  useEffect(() => {
    if (!isPending) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [isPending]);

  const childSummary = useMemo(() => {
    const counts = new Map<ToolCategory, number>();
    for (const ct of childTools) {
      const cat = getToolCategory(ct.tool_name);
      counts.set(cat, (counts.get(cat) || 0) + 1);
    }
    return Array.from(counts.entries())
      .sort((a, b) => b[1] - a[1])
      .map(([cat, count]) => ({ cat, count }));
  }, [childTools]);

  const lastChild =
    childTools.length > 0 ? childTools[childTools.length - 1] : null;
  const totalChildDuration = childTools.reduce(
    (sum, t) => sum + (t.duration_ms || 0),
    0
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      className={clsx(
        "rounded-lg border overflow-hidden relative",
        isIdle
          ? "border-[#ff4444]/30 bg-gradient-to-r from-[#ff4444]/[0.05] via-[#ff4444]/[0.02] to-[#ff4444]/[0.05]"
          : isPending
          ? "border-[#ff8844]/25 bg-gradient-to-r from-[#ff8844]/[0.04] via-[#ff8844]/[0.02] to-[#ff8844]/[0.04]"
          : "border-[#ff8844]/10 bg-[#ff8844]/[0.02]"
      )}
    >
      {isPending && (
        <div className="absolute top-0 left-0 right-0 h-[2px] overflow-hidden">
          <div
            className="h-full w-[200%]"
            style={{
              background: isIdle
                ? "linear-gradient(90deg, transparent 0%, #ff4444 25%, #ff6644 50%, #ff4444 75%, transparent 100%)"
                : "linear-gradient(90deg, transparent 0%, #ff8844 25%, #ffaa00 50%, #ff8844 75%, transparent 100%)",
              animation: isIdle
                ? "agent-shimmer 1s linear infinite"
                : "agent-shimmer 2s linear infinite",
            }}
          />
        </div>
      )}

      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-white/[0.02] transition-colors text-left"
      >
        <div
          className="relative flex items-center justify-center h-8 w-8 rounded-md shrink-0"
          style={
            isPending
              ? { background: "rgba(255, 136, 68, 0.12)", boxShadow: "0 0 12px rgba(255, 136, 68, 0.15)" }
              : { background: "rgba(255, 136, 68, 0.08)" }
          }
        >
          {getToolIcon("agent", isPending ? "#ffaa44" : "#ff8844")}
          {isPending && (
            <>
              <span className="absolute inset-0 rounded-md border border-[#ff8844]/20"
                style={{ animation: "agent-ring 2s ease-out infinite" }} />
              <span className="absolute -top-0.5 -right-0.5 h-2.5 w-2.5 rounded-full bg-[#ffaa00]"
                style={{ boxShadow: "0 0 6px rgba(255, 170, 0, 0.6)" }}>
                <span className="absolute inset-0 rounded-full bg-[#ffaa00] animate-ping opacity-40" />
              </span>
            </>
          )}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className={clsx("text-[11px] font-medium", isPending ? "text-[#ffaa44]" : "text-[#ff8844]")}>
              {description}
            </span>
            <span className="text-[9px] text-[#ff8844]/40 bg-[#ff8844]/8 rounded px-1 py-0.5 uppercase tracking-wider">
              {subType}
            </span>
            {childTools.length > 0 && (
              <span className="text-[9px] text-[#888] tabular-nums">{childTools.length} tools</span>
            )}
          </div>
          {!expanded && childTools.length > 0 && (
            <div className="flex items-center gap-2 mt-0.5">
              {isPending && !isFinalizing && lastChild && (
                <motion.span key={lastChild.id} initial={{ opacity: 0, x: -4 }} animate={{ opacity: 1, x: 0 }}
                  className="flex items-center gap-1 text-[9px] text-[#ccc]">
                  <span className="opacity-60 shrink-0">{getToolIcon(getToolCategory(lastChild.tool_name), "#ffaa44")}</span>
                  <span className="truncate max-w-[220px]">
                    {lastChild.tool_name}
                    {lastChild.input_data?.file_path ? <span className="text-[#888] ml-1">{shortPath(String(lastChild.input_data.file_path))}</span> : null}
                    {lastChild.input_data?.command ? <span className="text-[#888] ml-1">{String(lastChild.input_data.command).slice(0, 40)}</span> : null}
                  </span>
                </motion.span>
              )}
              {isFinalizing && (
                <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex items-center gap-1.5 text-[9px] text-[#cc88ff]">
                  <svg width="10" height="10" viewBox="0 0 10 10" fill="none" className="animate-spin">
                    <circle cx="5" cy="5" r="4" stroke="#cc88ff" strokeWidth="1" strokeDasharray="12 8" />
                  </svg>
                  writing response...
                </motion.span>
              )}
              {!isPending && (
                <span className="flex items-center gap-1.5 text-[9px] text-[#777]">
                  {childSummary.slice(0, 4).map(({ cat, count }) => (
                    <span key={cat} className="flex items-center gap-0.5">
                      <span className="opacity-40">{getToolIcon(cat, "#888")}</span>
                      <span className="tabular-nums">{count}</span>
                    </span>
                  ))}
                </span>
              )}
            </div>
          )}
          {!expanded && childTools.length === 0 && prompt && (
            <div className="text-[9px] text-[#888] mt-0.5 truncate">{prompt.slice(0, 100)}</div>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-[9px] text-[#777] tabular-nums">{fmtTime(ts)}</span>
          {!!tool.duration_ms && <span className="text-[9px] text-[#888] tabular-nums">{fmtDuration(tool.duration_ms)}</span>}
          {isPending && !isIdle && (
            <span className={clsx("flex items-center gap-1.5 text-[9px] font-semibold", isFinalizing ? "text-[#cc88ff]" : "text-[#ffaa00]")}>
              <span className="relative flex h-1.5 w-1.5">
                <span className={clsx("absolute inline-flex h-full w-full rounded-full animate-ping opacity-50", isFinalizing ? "bg-[#cc88ff]" : "bg-[#ffaa00]")} />
                <span className={clsx("relative inline-flex h-1.5 w-1.5 rounded-full", isFinalizing ? "bg-[#cc88ff]" : "bg-[#ffaa00]")}
                  style={{ boxShadow: isFinalizing ? "0 0 4px rgba(204, 136, 255, 0.5)" : "0 0 4px rgba(255, 170, 0, 0.5)" }} />
              </span>
              {isFinalizing ? "finalizing" : "running"}
            </span>
          )}
          {isIdle && (
            <span className="flex items-center gap-1.5 text-[9px] font-semibold text-[#ff4444]">
              <span className="relative flex h-1.5 w-1.5">
                <span className="absolute inline-flex h-full w-full rounded-full bg-[#ff4444] animate-ping opacity-50" />
                <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-[#ff4444]"
                  style={{ boxShadow: "0 0 4px rgba(255, 68, 68, 0.5)" }} />
              </span>
              stuck
            </span>
          )}
          <Chevron open={expanded} />
        </div>
      </button>

      {isIdle && (
        <div className="border-t border-[#ff4444]/20 bg-[#ff4444]/[0.06] px-4 py-2">
          <div className="flex items-center gap-2.5">
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" className="shrink-0">
              <path d="M6 1L11 10H1L6 1Z" stroke="#ff4444" strokeWidth="1" fill="none" />
              <line x1="6" y1="4.5" x2="6" y2="7" stroke="#ff4444" strokeWidth="1" strokeLinecap="round" />
              <circle cx="6" cy="8.5" r="0.5" fill="#ff4444" />
            </svg>
            <span className="text-[10px] text-[#ff4444]">
              Agent idle for{" "}
              <span className="font-semibold tabular-nums">
                {idleSec >= 60 ? `${Math.floor(idleSec / 60)}m ${idleSec % 60}s` : `${idleSec}s`}
              </span>{" "}
              &mdash; auto-recovery at 10m
            </span>
          </div>
        </div>
      )}

      {expanded && (
        <AgentRunExpanded
          tool={tool}
          childTools={childTools}
          childSummary={childSummary}
          totalChildDuration={totalChildDuration}
          prompt={prompt}
          showPrompt={showPrompt}
          setShowPrompt={setShowPrompt}
          finalText={finalText}
          showFinalText={showFinalText}
          setShowFinalText={setShowFinalText}
          isFinalizing={isFinalizing}
        />
      )}
    </motion.div>
  );
}
