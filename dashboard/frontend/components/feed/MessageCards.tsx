"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { clsx } from "clsx";
import { MarkdownContent } from "@/components/ui/MarkdownContent";
import { fmtTime } from "@/components/feed/eventCardHelpers";

/* ── LLM Message ── */
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
}) {
  const [showThinking, setShowThinking] = useState(false);
  const isPlanner = role === "planner";

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className={clsx(
        "rounded-lg p-4",
        isPlanner
          ? "bg-[#ff8844]/[0.04] border border-[#ff8844]/10"
          : "bg-white/[0.02] border border-white/[0.04]"
      )}
    >
      <div className="flex items-center gap-2 mb-2.5">
        <div
          className={clsx(
            "flex items-center justify-center h-6 w-6 rounded-md",
            isPlanner ? "bg-[#ff8844]/10" : "bg-[#00ff88]/8"
          )}
        >
          {isPlanner ? (
            <svg
              width="12"
              height="12"
              viewBox="0 0 12 12"
              fill="none"
              stroke="#ff8844"
              strokeWidth="1.5"
            >
              <path d="M2 9l2-4 2 2.5 2-3.5 2 5" />
              <rect x="1" y="9" width="10" height="1.5" rx="0.5" />
            </svg>
          ) : (
            <svg
              width="12"
              height="12"
              viewBox="0 0 12 12"
              fill="none"
              stroke="#00ff88"
              strokeWidth="1.5"
            >
              <path d="M6 1l1 3h3l-2.5 2 1 3L6 7.5 3.5 9l1-3L2 4h3L6 1z" />
            </svg>
          )}
        </div>
        <span
          className={clsx(
            "text-[11px] font-semibold",
            isPlanner ? "text-[#ff8844]" : "text-[#ccc]"
          )}
        >
          {isPlanner ? "Planner" : "AutoFyn"}
        </span>
        <span className="text-[9px] text-[#777] tabular-nums">
          {fmtTime(ts)}
        </span>
        {thinking && (
          <button
            onClick={() => setShowThinking(!showThinking)}
            className="ml-auto text-[10px] text-[#888] hover:text-[#ccc] transition-colors flex items-center gap-1"
          >
            <svg
              width="10"
              height="10"
              viewBox="0 0 10 10"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
            >
              <circle cx="5" cy="5" r="3.5" />
              <circle cx="5" cy="5" r="1" />
            </svg>
            {showThinking ? "hide reasoning" : "show reasoning"}
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
            Reasoning
          </div>
          <div className="text-[10px] text-[#666] italic leading-relaxed whitespace-pre-wrap break-words max-h-[300px] overflow-y-auto">
            {thinking}
          </div>
        </motion.div>
      )}

      {text && (
        <div>
          <MarkdownContent
            content={text}
            className={clsx(
              "text-[11px]",
              isPlanner ? "text-[#cc9966]" : "text-[#bbb]"
            )}
          />
          {isLast && (
            <span
              className={clsx(
                "inline-block w-[5px] h-[13px] ml-0.5 rounded-[1px]",
                isPlanner ? "bg-[#ff8844]/30" : "bg-[#00ff88]/25"
              )}
              style={{ animation: "blink 1s step-end infinite" }}
            />
          )}
        </div>
      )}
    </motion.div>
  );
}

/* ── Control ── */
export function ControlMessage({ text, ts, retryAction }: { text: string; ts: string; retryAction?: () => void }) {
  return (
    <div className="flex items-center gap-2 px-4 py-2">
      <div className="flex-1 h-px bg-[#ffaa00]/10" />
      <div className="flex items-center gap-1.5 text-[10px] text-[#ffaa00]/70">
        <svg
          width="10"
          height="10"
          viewBox="0 0 10 10"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
        >
          <polyline points="2 4 5 7 2 10" />
          <line x1="6" y1="10" x2="9" y2="10" />
        </svg>
        {text}
        {retryAction && (
          <button
            onClick={retryAction}
            className="text-[#ffaa00] hover:underline ml-1"
          >
            Retry
          </button>
        )}
        <span className="text-[#777] tabular-nums">{fmtTime(ts)}</span>
      </div>
      <div className="flex-1 h-px bg-[#ffaa00]/10" />
    </div>
  );
}

/* ── User Prompt Chat Bubble ── */
export function UserPromptCard({ prompt, ts, pending, failed }: { prompt: string; ts: string; pending?: boolean; failed?: boolean }) {
  const dotColor = failed ? "bg-[#ff4444]" : "bg-[#88ccff]";
  const borderColor = failed ? "border-[#ff4444]/20" : "border-[#88ccff]/20";
  const bgColor = failed ? "bg-[#ff4444]/10" : "bg-[#88ccff]/10";
  return (
    <motion.div
      initial={{ opacity: 0, x: 10 }}
      animate={{ opacity: 1, x: 0 }}
      className="flex justify-end px-4 py-1.5"
    >
      <div className={`max-w-[75%] rounded-2xl rounded-tr-sm ${bgColor} border ${borderColor} px-4 py-2.5`}>
        <div className="flex items-center justify-between gap-4 mb-1">
          <span className="text-[9px] font-semibold uppercase tracking-wider text-[#88ccff]">
            You
          </span>
          <span className="text-[9px] text-[#777] tabular-nums flex items-center gap-1.5">
            {pending && (
              <span className={`inline-block h-1.5 w-1.5 rounded-full ${dotColor} animate-pulse`} />
            )}
            {failed && !pending && (
              <span className="text-[#ff4444] text-[8px]">not delivered</span>
            )}
            {fmtTime(ts)}
          </span>
        </div>
        <div className="max-h-[300px] overflow-y-auto">
          <MarkdownContent content={prompt} className="text-[12px] text-[#cce8ff]" />
        </div>
      </div>
    </motion.div>
  );
}

/* ── Milestone ── */
export function MilestoneCard({
  label,
  detail,
  color,
  ts,
}: {
  label: string;
  detail: string;
  color: string;
  ts: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className="flex items-center gap-2 px-4 py-2"
    >
      <div className="flex-1 h-px" style={{ background: `${color}15` }} />
      <div
        className="flex items-center gap-2 px-3 py-1.5 rounded-full border"
        style={{ borderColor: `${color}20`, background: `${color}06` }}
      >
        <span
          className="h-1.5 w-1.5 rounded-full"
          style={{ background: color }}
        />
        <span className="text-[10px] font-semibold" style={{ color }}>
          {label}
        </span>
        {detail &&
          (detail.startsWith("http") ? (
            <a
              href={detail}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[9px] text-[#666] max-w-[300px] truncate hover:text-[#aaa] underline underline-offset-2"
            >
              {detail}
            </a>
          ) : (
            <span className="text-[9px] text-[#666] max-w-[300px] truncate">
              {detail}
            </span>
          ))}
        <span className="text-[9px] text-[#777] tabular-nums">
          {fmtTime(ts)}
        </span>
      </div>
      <div className="flex-1 h-px" style={{ background: `${color}15` }} />
    </motion.div>
  );
}

/* ── Divider ── */
export function DividerCard({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-3 px-4 py-1.5">
      <div className="flex-1 terminal-hr" />
      <span className="text-[10px] text-[#777] uppercase tracking-wider">
        {label}
      </span>
      <div className="flex-1 terminal-hr" />
    </div>
  );
}
