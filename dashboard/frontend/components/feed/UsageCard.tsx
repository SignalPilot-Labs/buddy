"use client";

import { motion } from "framer-motion";
import type { UsageEvent } from "@/lib/types";
import { fmtTime } from "@/components/feed/eventCardHelpers";
import { CARD_FADE_DURATION, CARD_FADE_EASE } from "@/lib/constants";

/* ── Usage Card ── */

export function UsageCard({ usage }: { usage: UsageEvent }) {
  const fmt = (n: number) => {
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
    if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
    return n.toLocaleString();
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: CARD_FADE_DURATION, ease: CARD_FADE_EASE }}
      className="border-l-[3px] border-l-[#44ccdd]/30 bg-[#44ccdd]/[0.015] rounded-r px-3 py-1"
    >
      <div className="flex items-center gap-3 flex-wrap">
        <span className="text-[9px] text-[#888] tabular-nums shrink-0 w-[52px]">
          {fmtTime(usage.ts)}
        </span>
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="#44ccdd" strokeWidth="1" opacity="0.5">
          <rect x="1" y="6" width="2" height="5" rx="0.5" />
          <rect x="5" y="3" width="2" height="8" rx="0.5" />
          <rect x="9" y="1" width="2" height="10" rx="0.5" />
        </svg>
        <span className="text-[9px] font-medium text-[#44ccdd]/60 tracking-wider">USAGE</span>
        <span className="text-[9px] text-[#666] tabular-nums">
          in:{fmt(usage.input_tokens)} out:{fmt(usage.output_tokens)}
        </span>
        <span className="text-[9px] text-[#999] tabular-nums">
          total: {fmt(usage.total_input_tokens)}↓ {fmt(usage.total_output_tokens)}↑
        </span>
        {usage.cache_read_input_tokens > 0 && (
          <span className="text-[9px] text-[#999] tabular-nums">
            cache:{fmt(usage.cache_read_input_tokens)}
          </span>
        )}
      </div>
    </motion.div>
  );
}
