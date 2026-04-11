"use client";

import { motion } from "framer-motion";
import type { FeedEvent } from "@/lib/types";
import { fmtTime } from "@/components/feed/eventCardHelpers";
import { ToolCallCard } from "@/components/feed/ToolCallCard";
import { AuditCard } from "@/components/feed/AuditCard";
import { UsageCard } from "@/components/feed/UsageCard";
import { CARD_FADE_DURATION, CARD_FADE_EASE } from "@/lib/constants";

/* ── Control Card ── */

function ControlCard({ text, ts }: { text: string; ts: string }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: CARD_FADE_DURATION, ease: CARD_FADE_EASE }}
      className="border-l-[3px] border-l-[#ffaa00] bg-[#ffaa00]/[0.03] rounded-r px-3 py-1.5"
    >
      <div className="flex items-center gap-2">
        <span className="text-[9px] text-[#888] tabular-nums w-[52px]">
          {fmtTime(ts)}
        </span>
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="#ffaa00" strokeWidth="1.5" strokeLinecap="round">
          <polyline points="2 4 5 7 2 10" />
          <line x1="7" y1="10" x2="10" y2="10" />
        </svg>
        <span className="text-[9px] font-bold text-[#ffaa00] tracking-wider uppercase">
          Control
        </span>
        <span className="text-[10px] text-[#888]">{text}</span>
      </div>
    </motion.div>
  );
}

/* ── Main Event Card Dispatcher ── */

export function EventCard({ event }: { event: FeedEvent }) {
  switch (event._kind) {
    case "tool":
      return <ToolCallCard tc={event.data} />;
    case "audit":
      return <AuditCard event={event.data} />;
    case "control":
      return <ControlCard text={event.text} ts={event.ts} />;
    case "usage":
      return <UsageCard usage={event.data} />;
    case "llm_text":
    case "llm_thinking":
      return null; // Grouped into llm_message by groupEvents
    default:
      return null;
  }
}

