"use client";

import type { ReactElement } from "react";
import { motion } from "framer-motion";
import { useTranslation } from "@/hooks/useTranslation";
import { fmtTime } from "@/components/feed/card-helpers";
import type { UsageEvent } from "@/lib/types";

export function UsageTick({
  data,
  ts,
}: {
  data: {
    input_tokens: number;
    output_tokens: number;
    total_input: number;
    total_output: number;
    cache_read: number;
  };
  ts: string;
}): ReactElement {
  const fmt = (n: number): string =>
    n >= 1_000_000
      ? `${(n / 1_000_000).toFixed(1)}M`
      : n >= 1_000
        ? `${(n / 1_000).toFixed(1)}k`
        : String(n);
  return (
    <div className="flex items-center gap-2 px-4 py-1 text-[9px] text-[#777]">
      <svg width="8" height="8" viewBox="0 0 8 8" fill="none" stroke="#44ccdd" strokeWidth="1" opacity="0.3">
        <rect x="0.5" y="4" width="1.5" height="3.5" rx="0.3" />
        <rect x="3" y="2" width="1.5" height="5.5" rx="0.3" />
        <rect x="5.5" y="0.5" width="1.5" height="7" rx="0.3" />
      </svg>
      <span>
        {fmt(data.total_input)}↓ {fmt(data.total_output)}↑
      </span>
      {data.cache_read > 0 && <span>cache:{fmt(data.cache_read)}</span>}
      <span className="ml-auto tabular-nums">{fmtTime(ts)}</span>
    </div>
  );
}

export function ControlMessage({ text, ts }: { text: string; ts: string }): ReactElement {
  return (
    <div className="flex items-center gap-2 px-4 py-2">
      <div className="flex-1 h-px bg-[#ffaa00]/10" />
      <div className="flex items-center gap-1.5 text-[9px] text-[#ffaa00]/70">
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
        <span className="text-[#777] tabular-nums">{fmtTime(ts)}</span>
      </div>
      <div className="flex-1 h-px bg-[#ffaa00]/10" />
    </div>
  );
}

export function UserPromptCard({ prompt, ts }: { prompt: string; ts: string }): ReactElement {
  const { t } = useTranslation();
  return (
    <motion.div initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} className="flex justify-end px-4 py-1.5">
      <div className="max-w-[75%] rounded-2xl rounded-tr-sm bg-[#88ccff]/10 border border-[#88ccff]/20 px-4 py-2.5">
        <div className="flex items-center justify-between gap-4 mb-1">
          <span className="text-[9px] font-semibold uppercase tracking-wider text-[#88ccff]">
            {t.llmOutput.you}
          </span>
          <span className="text-[9px] text-[#777] tabular-nums">{fmtTime(ts)}</span>
        </div>
        <p className="text-[12px] text-[#cce8ff] leading-relaxed break-words whitespace-pre-wrap max-h-[300px] overflow-y-auto">
          {prompt}
        </p>
      </div>
    </motion.div>
  );
}

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
}): ReactElement {
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
        <span className="h-1.5 w-1.5 rounded-full" style={{ background: color }} />
        <span className="text-[10px] font-semibold" style={{ color }}>
          {label}
        </span>
        {detail && <span className="text-[9px] text-[#666] max-w-[300px] truncate">{detail}</span>}
        <span className="text-[9px] text-[#777] tabular-nums">{fmtTime(ts)}</span>
      </div>
      <div className="flex-1 h-px" style={{ background: `${color}15` }} />
    </motion.div>
  );
}

export function DividerCard({ label }: { label: string }): ReactElement {
  return (
    <div className="flex items-center gap-3 px-4 py-1.5">
      <div className="flex-1 terminal-hr" />
      <span className="text-[9px] text-[#777] uppercase tracking-wider">{label}</span>
      <div className="flex-1 terminal-hr" />
    </div>
  );
}

export function UsageCard({ usage }: { usage: UsageEvent }): ReactElement {
  const { t } = useTranslation();
  const fmt = (n: number): string => {
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
    if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
    return n.toLocaleString();
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 2 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.1 }}
      className="border-l-[3px] border-l-[#44ccdd]/30 bg-[#44ccdd]/[0.015] rounded-r px-3 py-1"
    >
      <div className="flex items-center gap-3 flex-wrap">
        <span className="text-[9px] text-[#888] tabular-nums shrink-0 w-[52px]">{fmtTime(usage.ts)}</span>
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="#44ccdd" strokeWidth="1" opacity="0.5">
          <rect x="1" y="6" width="2" height="5" rx="0.5" />
          <rect x="5" y="3" width="2" height="8" rx="0.5" />
          <rect x="9" y="1" width="2" height="10" rx="0.5" />
        </svg>
        <span className="text-[9px] font-medium text-[#44ccdd]/60 tracking-wider">{t.eventCard.usage}</span>
        <span className="text-[9px] text-[#666] tabular-nums">
          in:{fmt(usage.input_tokens)} out:{fmt(usage.output_tokens)}
        </span>
        <span className="text-[9px] text-[#999] tabular-nums">
          total: {fmt(usage.total_input_tokens)}↓ {fmt(usage.total_output_tokens)}↑
        </span>
        {usage.cache_read_input_tokens > 0 && (
          <span className="text-[9px] text-[#999] tabular-nums">cache:{fmt(usage.cache_read_input_tokens)}</span>
        )}
      </div>
    </motion.div>
  );
}

export function ControlCard({ text, ts }: { text: string; ts: string }): ReactElement {
  const { t } = useTranslation();
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.97 }}
      animate={{ opacity: 1, scale: 1 }}
      className="border-l-[3px] border-l-[#ffaa00] bg-[#ffaa00]/[0.03] rounded-r px-3 py-1.5"
    >
      <div className="flex items-center gap-2">
        <span className="text-[9px] text-[#888] tabular-nums w-[52px]">{fmtTime(ts)}</span>
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="#ffaa00" strokeWidth="1.5" strokeLinecap="round">
          <polyline points="2 4 5 7 2 10" />
          <line x1="7" y1="10" x2="10" y2="10" />
        </svg>
        <span className="text-[9px] font-bold text-[#ffaa00] tracking-wider uppercase">{t.eventCard.control}</span>
        <span className="text-[10px] text-[#888]">{text}</span>
      </div>
    </motion.div>
  );
}
