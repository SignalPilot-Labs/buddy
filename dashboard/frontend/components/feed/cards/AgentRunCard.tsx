"use client";

import type { ReactElement } from "react";
import { useState, useMemo, useEffect } from "react";
import { motion } from "framer-motion";
import { clsx } from "clsx";
import { useTranslation } from "@/hooks/useTranslation";
import { getToolIcon } from "@/components/ui/ToolIcons";
import type { ToolCall, ToolCategory } from "@/lib/types";
import { getToolCategory, TOOL_COLORS } from "@/lib/types";
import { fmtTime, fmtDuration, shortPath } from "@/components/feed/card-helpers";
import { Chevron } from "@/components/feed/Chevron";
export const IDLE_WARN_MS = 60_000;
const FINALIZING_THRESHOLD_MS = 3_000;

export function AgentRunCard({
  tool,
  childTools,
  finalText,
  agentType,
  ts,
}: {
  tool: ToolCall;
  childTools: ToolCall[];
  finalText: string;
  agentType: string;
  ts: string;
}): ReactElement {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);
  const [showPrompt, setShowPrompt] = useState(false);
  const [showFinalText, setShowFinalText] = useState(false);
  const [now, setNow] = useState(Date.now());
  const input = tool.input_data || {};
  const description = (input.description as string) || t.groupedEventCard.subAgentTask;
  const prompt = (input.prompt as string) || "";
  const subType = agentType || (input.subagent_type as string) || "general";
  const isPending = tool.phase === "pre" && !tool.output_data;

  const lastActivityTs =
    childTools.length > 0
      ? new Date(childTools[childTools.length - 1].ts).getTime()
      : new Date(ts).getTime();
  const idleMs = isPending ? now - lastActivityTs : 0;
  const isIdle = idleMs > IDLE_WARN_MS;
  const idleSec = Math.floor(idleMs / 1000);
  const isFinalizing = isPending && childTools.length > 0 && idleMs > FINALIZING_THRESHOLD_MS && !isIdle;

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

  const lastChild = childTools.length > 0 ? childTools[childTools.length - 1] : null;
  const totalChildDuration = childTools.reduce((sum, ct) => sum + (ct.duration_ms || 0), 0);

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
            : "border-[#ff8844]/10 bg-[#ff8844]/[0.02]",
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
              animation: isIdle ? "agent-shimmer 1s linear infinite" : "agent-shimmer 2s linear infinite",
            }}
          />
        </div>
      )}
      <style>{`@keyframes agent-shimmer { 0% { transform: translateX(-50%); } 100% { transform: translateX(0); } } @keyframes agent-ring { 0% { opacity: 0.6; transform: scale(1); } 100% { opacity: 0; transform: scale(1.4); } }`}</style>

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
              <span
                className="absolute inset-0 rounded-md border border-[#ff8844]/20"
                style={{ animation: "agent-ring 2s ease-out infinite" }}
              />
              <span
                className="absolute -top-0.5 -right-0.5 h-2.5 w-2.5 rounded-full bg-[#ffaa00]"
                style={{ boxShadow: "0 0 6px rgba(255, 170, 0, 0.6)" }}
              >
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
              <span className="text-[9px] text-[#888] tabular-nums">
                {childTools.length} {t.groupedEventCard.tools}
              </span>
            )}
          </div>
          {!expanded && childTools.length > 0 && (
            <div className="flex items-center gap-2 mt-0.5">
              {isPending && !isFinalizing && lastChild && (
                <motion.span
                  key={lastChild.id}
                  initial={{ opacity: 0, x: -4 }}
                  animate={{ opacity: 1, x: 0 }}
                  className="flex items-center gap-1 text-[9px] text-[#ccc]"
                >
                  <span className="opacity-60 shrink-0">
                    {getToolIcon(getToolCategory(lastChild.tool_name), "#ffaa44")}
                  </span>
                  <span className="truncate max-w-[220px]">
                    {lastChild.tool_name}
                    {lastChild.input_data?.file_path ? (
                      <span className="text-[#888] ml-1">
                        {shortPath(String(lastChild.input_data.file_path))}
                      </span>
                    ) : null}
                    {lastChild.input_data?.command ? (
                      <span className="text-[#888] ml-1">
                        {String(lastChild.input_data.command).slice(0, 40)}
                      </span>
                    ) : null}
                  </span>
                </motion.span>
              )}
              {isFinalizing && (
                <motion.span
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="flex items-center gap-1.5 text-[9px] text-[#cc88ff]"
                >
                  <svg width="10" height="10" viewBox="0 0 10 10" fill="none" className="animate-spin">
                    <circle cx="5" cy="5" r="4" stroke="#cc88ff" strokeWidth="1" strokeDasharray="12 8" />
                  </svg>
                  {t.groupedEventCard.writingResponse}
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
          {!!tool.duration_ms && (
            <span className="text-[9px] text-[#888] tabular-nums">{fmtDuration(tool.duration_ms)}</span>
          )}
          {isPending && !isIdle && (
            <span
              className={clsx(
                "flex items-center gap-1.5 text-[9px] font-semibold",
                isFinalizing ? "text-[#cc88ff]" : "text-[#ffaa00]",
              )}
            >
              <span className="relative flex h-1.5 w-1.5">
                <span
                  className={clsx(
                    "absolute inline-flex h-full w-full rounded-full animate-ping opacity-50",
                    isFinalizing ? "bg-[#cc88ff]" : "bg-[#ffaa00]",
                  )}
                />
                <span
                  className={clsx(
                    "relative inline-flex h-1.5 w-1.5 rounded-full",
                    isFinalizing ? "bg-[#cc88ff]" : "bg-[#ffaa00]",
                  )}
                  style={{
                    boxShadow: isFinalizing
                      ? "0 0 4px rgba(204, 136, 255, 0.5)"
                      : "0 0 4px rgba(255, 170, 0, 0.5)",
                  }}
                />
              </span>
              {isFinalizing ? t.groupedEventCard.finalizing : t.groupedEventCard.running}
            </span>
          )}
          {isIdle && (
            <span className="flex items-center gap-1.5 text-[9px] font-semibold text-[#ff4444]">
              <span className="relative flex h-1.5 w-1.5">
                <span className="absolute inline-flex h-full w-full rounded-full bg-[#ff4444] animate-ping opacity-50" />
                <span
                  className="relative inline-flex h-1.5 w-1.5 rounded-full bg-[#ff4444]"
                  style={{ boxShadow: "0 0 4px rgba(255, 68, 68, 0.5)" }}
                />
              </span>
              {t.groupedEventCard.stuck}
            </span>
          )}
          <Chevron open={expanded} size={10} />
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
              {t.groupedEventCard.agentIdle}{" "}
              <span className="font-semibold tabular-nums">
                {idleSec >= 60 ? `${Math.floor(idleSec / 60)}m ${idleSec % 60}s` : `${idleSec}s`}
              </span>{" "}
              &mdash; {t.groupedEventCard.autoRecovery}
            </span>
          </div>
        </div>
      )}

      {expanded && (
        <motion.div
          initial={{ height: 0 }}
          animate={{ height: "auto" }}
          className="border-t border-white/[0.04] overflow-hidden"
        >
          {childTools.length > 0 && (
            <div className="flex items-center gap-3 px-4 py-2 border-b border-white/[0.03] bg-black/10">
              <span className="text-[9px] text-[#888] uppercase tracking-wider">
                {childTools.length} {t.groupedEventCard.toolCalls}
              </span>
              {totalChildDuration > 0 && (
                <span className="text-[9px] text-[#666] tabular-nums">{fmtDuration(totalChildDuration)}</span>
              )}
              <div className="flex items-center gap-2 ml-auto">
                {childSummary.map(({ cat, count }) => (
                  <span key={cat} className="flex items-center gap-1 text-[9px] text-[#777]">
                    <span className="opacity-50">{getToolIcon(cat, "#888")}</span>
                    <span className="tabular-nums">{count}</span>
                  </span>
                ))}
              </div>
            </div>
          )}

          {childTools.length > 0 && (
            <div className="max-h-[400px] overflow-y-auto">
              {childTools.map((ct, idx) => {
                const cat = getToolCategory(ct.tool_name);
                const colors = TOOL_COLORS[cat];
                const inp = ct.input_data || {};
                const fp = (inp.file_path as string) || "";
                const cmd = (inp.command as string) || "";
                const desc = (inp.description as string) || "";
                const detail = fp
                  ? shortPath(fp)
                  : cmd
                    ? cmd.slice(0, 60)
                    : desc
                      ? desc.slice(0, 60)
                      : "";
                return (
                  <div
                    key={idx}
                    className={clsx(
                      "flex items-center gap-2 px-4 py-1.5 text-[10px] transition-colors hover:bg-white/[0.02]",
                      idx < childTools.length - 1 && "border-b border-white/[0.02]",
                    )}
                  >
                    <span className="opacity-50 shrink-0">
                      {getToolIcon(cat, colors?.iconColor || "#888")}
                    </span>
                    <span className={clsx("shrink-0 font-medium", colors?.text || "text-[#888]")}>
                      {ct.tool_name}
                    </span>
                    {detail && <span className="text-[#666] truncate flex-1 min-w-0">{detail}</span>}
                    {!detail && <span className="flex-1" />}
                    {!!ct.duration_ms && (
                      <span className="text-[9px] text-[#666] tabular-nums shrink-0">
                        {fmtDuration(ct.duration_ms)}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {prompt && (
            <div className="border-t border-white/[0.03]">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setShowPrompt(!showPrompt);
                }}
                className="w-full flex items-center gap-2 px-4 py-2 text-[9px] text-[#888] hover:bg-white/[0.02] transition-colors text-left uppercase tracking-wider"
              >
                <Chevron open={showPrompt} size={8} />
                {t.groupedEventCard.prompt}
              </button>
              {showPrompt && (
                <div className="px-4 pb-3">
                  <div className="text-[10px] text-[#aaa] whitespace-pre-wrap break-words leading-relaxed bg-black/20 rounded-lg p-3 border border-white/[0.03] max-h-[200px] overflow-y-auto">
                    {prompt}
                  </div>
                </div>
              )}
            </div>
          )}

          {finalText && (
            <div className="border-t border-white/[0.03]">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setShowFinalText(!showFinalText);
                }}
                className="w-full flex items-center gap-2 px-4 py-2 text-[9px] text-[#cc88ff]/70 hover:bg-white/[0.02] transition-colors text-left uppercase tracking-wider"
              >
                <Chevron open={showFinalText} size={8} />
                {t.groupedEventCard.agentSummary}
              </button>
              {showFinalText && (
                <div className="px-4 pb-3">
                  <div className="text-[10px] text-[#bbb] whitespace-pre-wrap break-words leading-relaxed bg-black/20 rounded-lg p-3 border border-[#cc88ff]/10 max-h-[300px] overflow-y-auto">
                    {finalText}
                  </div>
                </div>
              )}
            </div>
          )}

          {isFinalizing && (
            <div className="border-t border-white/[0.03] px-4 py-3 flex items-center gap-2">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" className="animate-spin shrink-0">
                <circle cx="6" cy="6" r="5" stroke="#cc88ff" strokeWidth="1" strokeDasharray="16 10" />
              </svg>
              <span className="text-[10px] text-[#cc88ff]/70">{t.llmOutput.agentFinalizing}</span>
            </div>
          )}

          {tool.output_data && !finalText && (
            <div className="border-t border-white/[0.03] px-4 py-3">
              <div className="text-[9px] uppercase tracking-[0.15em] text-[#00ff88]/50 mb-1.5">
                {t.llmOutput.result}
              </div>
              <div className="text-[10px] text-[#888] whitespace-pre-wrap break-words bg-black/20 rounded-lg p-3 border border-white/[0.03] max-h-[200px] overflow-y-auto leading-relaxed">
                {typeof tool.output_data === "object" && "result" in tool.output_data
                  ? String(tool.output_data.result).slice(0, 2000)
                  : JSON.stringify(tool.output_data, null, 2).slice(0, 2000)}
              </div>
            </div>
          )}
        </motion.div>
      )}
    </motion.div>
  );
}
