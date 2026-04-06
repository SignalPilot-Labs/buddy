"use client";

import type { ReactElement } from "react";
import { useState } from "react";
import { motion } from "framer-motion";
import { clsx } from "clsx";
import { useTranslation } from "@/hooks/useTranslation";
import { fmtTime } from "@/components/feed/card-helpers";

export function LLMMessageCard({
  role,
  text,
  thinking,
  ts,
  isLast,
}: {
  role: string;
  text: string;
  thinking: string;
  ts: string;
  isLast: boolean;
}): ReactElement {
  const { t } = useTranslation();
  const [showThinking, setShowThinking] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const isPlanner = role === "planner";
  const isLong = text.length > 3000;

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className={clsx(
        "rounded-lg p-4",
        isPlanner
          ? "bg-[#ff8844]/[0.04] border border-[#ff8844]/10"
          : "bg-white/[0.02] border border-white/[0.04]",
      )}
    >
      <div className="flex items-center gap-2 mb-2.5">
        <div
          className={clsx(
            "flex items-center justify-center h-6 w-6 rounded-md",
            isPlanner ? "bg-[#ff8844]/10" : "bg-[#00ff88]/8",
          )}
        >
          {isPlanner ? (
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="#ff8844" strokeWidth="1.5">
              <path d="M2 9l2-4 2 2.5 2-3.5 2 5" />
              <rect x="1" y="9" width="10" height="1.5" rx="0.5" />
            </svg>
          ) : (
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="#00ff88" strokeWidth="1.5">
              <path d="M6 1l1 3h3l-2.5 2 1 3L6 7.5 3.5 9l1-3L2 4h3L6 1z" />
            </svg>
          )}
        </div>
        <span className={clsx("text-[11px] font-semibold", isPlanner ? "text-[#ff8844]" : "text-[#ccc]")}>
          {isPlanner ? t.groupedEventCard.planner : t.groupedEventCard.workerAgent}
        </span>
        <span className="text-[9px] text-[#777] tabular-nums">{fmtTime(ts)}</span>
        {thinking && (
          <button
            onClick={() => setShowThinking(!showThinking)}
            className="ml-auto text-[9px] text-[#888] hover:text-[#ccc] transition-colors flex items-center gap-1"
          >
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5">
              <circle cx="5" cy="5" r="3.5" />
              <circle cx="5" cy="5" r="1" />
            </svg>
            {showThinking ? t.llmOutput.hideReasoning : t.llmOutput.showReasoning}
          </button>
        )}
      </div>

      {showThinking && thinking && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: "auto", opacity: 1 }}
          className="mb-3 px-3 py-2 bg-black/20 rounded border border-white/[0.03] overflow-hidden"
        >
          <div className="text-[9px] text-[#888] uppercase tracking-wider font-semibold mb-1">
            {t.llmOutput.reasoning}
          </div>
          <div className="text-[10px] text-[#666] italic leading-relaxed whitespace-pre-wrap break-words max-h-[300px] overflow-y-auto">
            {thinking}
          </div>
        </motion.div>
      )}

      {text && (
        <div className="relative">
          {isLong && (
            <button
              onClick={() => setCollapsed(!collapsed)}
              className="absolute top-0 right-0 text-[9px] text-[#888] hover:text-[#ccc] transition-colors"
            >
              [{collapsed ? t.llmOutput.expand : t.llmOutput.collapse}]
            </button>
          )}
          <div
            className={clsx(
              "text-[11px] leading-[1.7] whitespace-pre-wrap break-words",
              isPlanner ? "text-[#cc9966]" : "text-[#bbb]",
              collapsed && "max-h-[100px] overflow-hidden",
            )}
          >
            {collapsed ? text.slice(0, 500) + "…" : text}
          </div>
          {collapsed && (
            <div className="absolute bottom-0 left-0 right-0 h-8 bg-gradient-to-t from-[#050505] to-transparent" />
          )}
          {isLast && (
            <span
              className={clsx(
                "inline-block w-[5px] h-[13px] ml-0.5 rounded-[1px]",
                isPlanner ? "bg-[#ff8844]/30" : "bg-[#00ff88]/25",
              )}
              style={{ animation: "blink 1s step-end infinite" }}
            />
          )}
        </div>
      )}
    </motion.div>
  );
}
