"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { clsx } from "clsx";
import { MarkdownContent } from "@/components/ui/MarkdownContent";
import { fmtTime } from "@/components/feed/eventCardHelpers";

/* ── Base Message Card ── */
function MessageCard({
  color,
  icon,
  title,
  ts,
  actions,
  children,
}: {
  color: string;
  icon: React.ReactNode;
  title: string;
  ts: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className="rounded-lg p-4 border-l-2 transition-all duration-150 hover:border-l-[3px]"
      style={{
        background: `${color}0a`,
        borderColor: `${color}1a`,
        borderLeftColor: color,
      }}
    >
      <div className="flex items-center gap-2 mb-2.5">
        <div
          className="flex items-center justify-center h-6 w-6 rounded-md"
          style={{ background: `${color}1a` }}
        >
          {icon}
        </div>
        <span className="text-title font-semibold" style={{ color }}>
          {title}
        </span>
        <span className="text-caption text-text-dim tabular-nums">
          {fmtTime(ts)}
        </span>
        {actions}
      </div>
      {children}
    </motion.div>
  );
}

const ICON_AUTOFYN = (
  <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="#00ff88" strokeWidth="1.5" aria-hidden="true">
    <path d="M6 1l1 3h3l-2.5 2 1 3L6 7.5 3.5 9l1-3L2 4h3L6 1z" />
  </svg>
);

const ICON_PLANNER = (
  <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="#ff8844" strokeWidth="1.5" aria-hidden="true">
    <path d="M2 9l2-4 2 2.5 2-3.5 2 5" />
    <rect x="1" y="9" width="10" height="1.5" rx="0.5" />
  </svg>
);

const ICON_ERROR = (
  <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="#ff4444" strokeWidth="1.5" strokeLinecap="round" aria-hidden="true">
    <circle cx="6" cy="6" r="5" />
    <line x1="6" y1="3.5" x2="6" y2="6.5" />
    <circle cx="6" cy="8.5" r="0.5" fill="#ff4444" stroke="none" />
  </svg>
);

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
  const color = isPlanner ? "#ff8844" : "#00ff88";

  return (
    <MessageCard
      color={color}
      icon={isPlanner ? ICON_PLANNER : ICON_AUTOFYN}
      title={isPlanner ? "Planner" : "AutoFyn"}
      ts={ts}
      actions={thinking ? (
        <button
          onClick={() => setShowThinking(!showThinking)}
          className="ml-auto text-caption text-text-secondary hover:text-accent-hover transition-colors flex items-center gap-1"
        >
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
            <circle cx="5" cy="5" r="3.5" />
            <circle cx="5" cy="5" r="1" />
          </svg>
          {showThinking ? "hide reasoning" : "show reasoning"}
        </button>
      ) : undefined}
    >
      {showThinking && thinking && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: "auto", opacity: 1 }}
          transition={{ duration: 0.25, ease: "easeOut" }}
          className="mb-3 px-3 py-2 bg-black/20 rounded border border-white/[0.03] overflow-hidden"
        >
          <div className="text-content text-text-secondary uppercase tracking-wider font-semibold mb-1">
            Reasoning
          </div>
          <div className="text-meta text-text-secondary italic leading-relaxed whitespace-pre-wrap break-words max-h-[300px] overflow-y-auto">
            {thinking}
          </div>
        </motion.div>
      )}
      {text && (
        <div>
          <MarkdownContent
            content={text}
            className={clsx("text-body", isPlanner ? "text-[#cc9966]" : "text-accent-hover")}
          />
          {isLast && (
            <span
              className="inline-block w-[5px] h-[13px] ml-0.5 rounded-[1px]"
              style={{ background: `${color}40`, animation: "blink 1s step-end infinite" }}
            />
          )}
        </div>
      )}
    </MessageCard>
  );
}

/* ── Control / Error ── */
export function ControlMessage({ text, ts, retryAction }: { text: string; ts: string; retryAction?: () => void }) {
  return (
    <MessageCard
      color="#ff4444"
      icon={ICON_ERROR}
      title="Error"
      ts={ts}
      actions={retryAction ? (
        <button onClick={retryAction} className="ml-auto text-caption text-[#ff4444] hover:underline">
          Retry
        </button>
      ) : undefined}
    >
      <div className="text-body text-[#ff8888] whitespace-pre-wrap break-words">{text}</div>
    </MessageCard>
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
      exit={{ opacity: 0, x: 10 }}
      className="flex justify-end px-4 py-1.5"
    >
      <div className={`max-w-[75%] min-w-0 rounded-2xl rounded-tr-sm ${bgColor} border ${borderColor} px-4 py-2.5 overflow-hidden`}>
        <div className="flex items-center justify-between gap-4 mb-1">
          <span className="text-content font-semibold uppercase tracking-wider text-[#88ccff]">
            You
          </span>
          <span className="text-caption text-text-dim tabular-nums flex items-center gap-1.5">
            {pending && (
              <span className={`inline-block h-1.5 w-1.5 rounded-full ${dotColor} animate-pulse`} />
            )}
            {failed && !pending && (
              <span className="text-[#ff4444] text-caption">not delivered</span>
            )}
            {fmtTime(ts)}
          </span>
        </div>
        <div className="max-h-[300px] overflow-y-auto text-body text-[#cce8ff] whitespace-pre-wrap break-words leading-relaxed">
          {prompt}
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
        <span className="text-content font-semibold" style={{ color }}>
          {label}
        </span>
        {detail &&
          (detail.startsWith("http") ? (
            <a
              href={detail}
              target="_blank"
              rel="noopener noreferrer"
              className="text-caption text-text-secondary max-w-[300px] truncate hover:text-accent-hover underline underline-offset-2"
            >
              {detail}
            </a>
          ) : (
            <span className="text-caption text-text-secondary max-w-[300px] truncate">
              {detail}
            </span>
          ))}
        <span className="text-caption text-text-dim tabular-nums">
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
      <span className="text-content text-text-dim uppercase tracking-wider">
        {label}
      </span>
      <div className="flex-1 terminal-hr" />
    </div>
  );
}
