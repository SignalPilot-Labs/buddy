"use client";

import { useState, useMemo, useEffect, memo } from "react";
import { motion } from "framer-motion";
import type { ToolCall } from "@/lib/types";
import { getToolCategory, type ToolCategory } from "@/lib/types";
import { getToolIcon } from "@/components/ui/ToolIcons";
import { getPhaseIcon } from "@/components/ui/PhaseIcon";
import { Chevron } from "@/components/feed/ToolDisplayCards";
import { AgentRunExpanded } from "@/components/feed/AgentRunExpanded";
import {
  fmtTime,
  fmtDuration,
  shortPath,
  IDLE_WARN_MS,
} from "@/components/feed/eventCardHelpers";
import { AGENT_IDLE_TIMER_INTERVAL_MS } from "@/lib/constants";
import { resolvePhase, hexToRgba } from "@/lib/phaseColors";
import {
  AgentRunStatusBadge,
  IdleWarningBanner,
} from "@/components/feed/AgentRunStatusBadge";
import { SpinnerIcon } from "@/components/ui/StatusIcons";

function AgentRunCardInner({
  tool,
  childTools,
  finalText,
  agentType,
  ts,
  runActive,
  runPaused,
}: {
  tool: ToolCall;
  childTools: ToolCall[];
  finalText: string;
  agentType: string;
  ts: string;
  runActive: boolean;
  runPaused: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const [showPrompt, setShowPrompt] = useState(false);
  const [showFinalText, setShowFinalText] = useState(false);
  const [now, setNow] = useState(Date.now());
  // description and subagent_type come from the Task tool input_data;
  // agentType comes from the subagent_start audit event. They should
  // always be populated for a well-formed Agent card. If any is missing,
  // render an em-dash so the regression is visible rather than silently
  // masked with a "general" / "Sub-agent task" placeholder.
  const input = tool.input_data || {};
  const description = (input.description as string) || "—";
  const prompt = (input.prompt as string) || "";
  const subType = agentType || (input.subagent_type as string) || "—";
  const isPending =
    runActive && !runPaused && tool.phase === "pre" && !tool.output_data;
  const isPaused = runActive && runPaused && tool.phase === "pre" && !tool.output_data;
  const isCompleted = !isPending && !!tool.output_data;
  const isFailed = !runActive && !isPending && !isPaused && tool.phase === "pre" && !tool.output_data;

  const { phase, meta: phaseMeta } = resolvePhase(subType);

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
    const id = setInterval(() => setNow(Date.now()), AGENT_IDLE_TIMER_INTERVAL_MS);
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

  const phaseColor = phaseMeta.color;

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-lg border overflow-hidden relative transition-all duration-150 hover:!border-l-[3px] focus-within:!border-l-[3px] focus-within:outline focus-within:outline-1 focus-within:outline-white/20 focus-within:outline-offset-[-1px]"
      style={
        isIdle
          ? {
              borderColor: "rgba(255, 68, 68, 0.30)",
              borderLeftWidth: "2px",
              borderLeftColor: "#ff4444",
              background:
                "linear-gradient(to right, rgba(255,68,68,0.05), rgba(255,68,68,0.02), rgba(255,68,68,0.05))",
            }
          : isPending
          ? {
              borderColor: hexToRgba(phaseColor, 0.25),
              borderLeftWidth: "2px",
              borderLeftColor: phaseColor,
              background: `linear-gradient(to right, ${hexToRgba(phaseColor, 0.04)}, ${hexToRgba(phaseColor, 0.02)}, ${hexToRgba(phaseColor, 0.04)})`,
            }
          : isPaused
          ? {
              borderColor: "rgba(255, 170, 0, 0.15)",
              borderLeftWidth: "2px",
              borderLeftColor: "#ffaa00",
              background: "rgba(255, 170, 0, 0.03)",
            }
          : {
              borderColor: hexToRgba(phaseColor, 0.10),
              borderLeftWidth: "2px",
              borderLeftColor: phaseColor,
              background: hexToRgba(phaseColor, 0.02),
            }
      }
    >
      {isPending && (
        <div className="absolute top-0 left-0 right-0 h-[2px] overflow-hidden">
          <div
            className="h-full w-[200%]"
            style={{
              background: isIdle
                ? "linear-gradient(90deg, transparent 0%, #ff4444 25%, #ff6644 50%, #ff4444 75%, transparent 100%)"
                : `linear-gradient(90deg, transparent 0%, ${phaseColor} 25%, ${hexToRgba(phaseColor, 0.8)} 50%, ${phaseColor} 75%, transparent 100%)`,
              animation: isIdle
                ? "agent-shimmer 1s linear infinite"
                : "agent-shimmer 2s linear infinite",
            }}
          />
        </div>
      )}

      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-white/[0.02] transition-colors text-left focus-visible:outline focus-visible:outline-1 focus-visible:outline-offset-[-2px] focus-visible:outline-[#00ff88]"
      >
        <div
          className="relative flex items-center justify-center h-8 w-8 rounded-md shrink-0"
          style={
            isPending
              ? {
                  background: hexToRgba(phaseColor, 0.12),
                  boxShadow: `0 0 12px ${hexToRgba(phaseColor, 0.15)}`,
                }
              : { background: hexToRgba(phaseColor, 0.08) }
          }
        >
          {getPhaseIcon(phase, isPending ? hexToRgba(phaseColor, 0.8) : phaseColor)}
          {isPending && (
            <>
              <span
                className="absolute inset-0 rounded-md border"
                style={{
                  borderColor: hexToRgba(phaseColor, 0.20),
                  animation: "agent-ring 2s ease-out infinite",
                }}
              />
              <span
                className="absolute -top-0.5 -right-0.5 h-2.5 w-2.5 rounded-full"
                style={{ backgroundColor: phaseColor, boxShadow: `0 0 6px ${hexToRgba(phaseColor, 0.6)}` }}
              >
                <span className="absolute inset-0 rounded-full animate-ping opacity-40" style={{ backgroundColor: phaseColor }} />
              </span>
            </>
          )}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span
              className="text-[11px] font-medium"
              style={{ color: isPending ? hexToRgba(phaseColor, 0.8) : phaseColor }}
            >
              {description}
            </span>
            <span
              className="text-[10px] rounded px-1 py-0.5 uppercase tracking-wider"
              style={{
                color: hexToRgba(phaseColor, 0.75),
                background: hexToRgba(phaseColor, 0.08),
              }}
            >
              {subType}
            </span>
            {childTools.length > 0 && (
              <span className="text-[10px] text-text-secondary tabular-nums">
                {childTools.length} tools
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
                  className="flex items-center gap-1 text-[10px] text-accent-hover"
                >
                  <span className="opacity-60 shrink-0">
                    {getToolIcon(
                      getToolCategory(lastChild.tool_name),
                      hexToRgba(phaseColor, 0.7)
                    )}
                  </span>
                  <span className="truncate max-w-[220px]">
                    {lastChild.tool_name}
                    {lastChild.input_data?.file_path ? (
                      <span className="text-text-secondary ml-1">
                        {shortPath(String(lastChild.input_data.file_path))}
                      </span>
                    ) : null}
                    {lastChild.input_data?.command ? (
                      <span className="text-text-secondary ml-1">
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
                  className="flex items-center gap-1.5 text-[10px] text-[#cc88ff]"
                >
                  <SpinnerIcon color="#cc88ff" />
                  writing response...
                </motion.span>
              )}
              {!isPending && (
                <span className="flex items-center gap-1.5 text-[10px] text-text-dim">
                  {childSummary.slice(0, 4).map(({ cat, count }) => (
                    <span key={cat} className="flex items-center gap-0.5">
                      <span className="opacity-40">
                        {getToolIcon(cat, "#888")}
                      </span>
                      <span className="tabular-nums">{count}</span>
                    </span>
                  ))}
                </span>
              )}
            </div>
          )}
          {!expanded && childTools.length === 0 && prompt && (
            <div className="text-[10px] text-text-secondary mt-0.5 truncate">
              {prompt.slice(0, 100)}
            </div>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-[10px] text-text-dim tabular-nums">
            {fmtTime(ts)}
          </span>
          {!!tool.duration_ms && (
            <span className="text-[10px] text-text-dim tabular-nums">
              {fmtDuration(tool.duration_ms)}
            </span>
          )}
          <AgentRunStatusBadge
            isPending={isPending}
            isPaused={isPaused}
            isIdle={isIdle}
            isFinalizing={isFinalizing}
            isCompleted={isCompleted}
            isFailed={isFailed}
            idleSec={idleSec}
            phaseColor={phaseColor}
          />
          <Chevron open={expanded} />
        </div>
      </button>

      {isIdle && <IdleWarningBanner idleSec={idleSec} />}

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

export const AgentRunCard = memo(AgentRunCardInner);
