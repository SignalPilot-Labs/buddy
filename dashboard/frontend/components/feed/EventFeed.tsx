"use client";

import { useRef, useEffect, useState, useCallback, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { clsx } from "clsx";
import type { FeedEvent } from "@/lib/types";
import { groupEvents } from "@/lib/groupEvents";
import { GroupedEventCard } from "./GroupedEventCard";
import { EmptyEvents } from "@/components/ui/EmptyStates";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";
import { MarkdownContent } from "@/components/ui/MarkdownContent";

const FAB_INITIAL = { opacity: 0, y: 8 };
const FAB_ANIMATE = { opacity: 1, y: 0 };
const FAB_EXIT = { opacity: 0, y: 8 };
const FAB_TRANSITION = { duration: 0.15 };

function PendingInjectBubble({ prompt, ts, status }: { prompt: string; ts: string; status: "delivering" | "failed" }) {
  const time = new Date(ts).toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" });
  const failed = status === "failed";
  const dotColor = failed ? "bg-[#ff4444]" : "bg-[#88ccff]";
  const borderColor = failed ? "border-[#ff4444]/20" : "border-[#88ccff]/20";
  const bgColor = failed ? "bg-[#ff4444]/10" : "bg-[#88ccff]/10";
  return (
    <motion.div initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} className="flex justify-end px-4 py-1.5">
      <div className={`max-w-[75%] rounded-2xl rounded-tr-sm ${bgColor} border ${borderColor} px-4 py-2.5`}>
        <div className="flex items-center justify-between gap-4 mb-1">
          <span className="text-[9px] font-semibold uppercase tracking-wider text-[#88ccff]">You</span>
          <span className="text-[9px] text-[#777] tabular-nums flex items-center gap-1.5">
            <span className={`inline-block h-1.5 w-1.5 rounded-full ${dotColor} ${failed ? "" : "animate-pulse"}`} />
            {failed ? "not delivered" : "delivering"}
            <span>{time}</span>
          </span>
        </div>
        <div className="max-h-[300px] overflow-y-auto">
          <MarkdownContent content={prompt} className="text-[12px] text-[#cce8ff]" />
        </div>
      </div>
    </motion.div>
  );
}

export function EventFeed({
  events,
  runActive = false,
  runPaused = false,
  pendingPrompt = null,
}: {
  events: FeedEvent[];
  runActive?: boolean;
  runPaused?: boolean;
  pendingPrompt?: { prompt: string; ts: string; status: "delivering" | "failed" } | null;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const [userScrolled, setUserScrolled] = useState(false);
  const [seenCount, setSeenCount] = useState(0);

  const grouped = useMemo(() => groupEvents(events), [events]);

  const lastInterruptionTs = useMemo(() => {
    const interruptLabels = new Set(["Pause Requested", "Stop Requested", "Resumed"]);
    for (let i = grouped.length - 1; i >= 0; i--) {
      const gev = grouped[i];
      if (gev.type === "milestone" && interruptLabels.has(gev.label)) {
        return gev.ts;
      }
    }
    return null;
  }, [grouped]);

  // Track how many events were seen when user scrolled away
  useEffect(() => {
    if (!userScrolled) {
      setSeenCount(events.length);
    }
  }, [userScrolled, events.length]);

  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [grouped, autoScroll, pendingPrompt]);

  const handleScroll = useCallback(() => {
    if (!containerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 60;
    setAutoScroll(isAtBottom);
    setUserScrolled(!isAtBottom);
  }, []);

  const scrollToBottom = useCallback(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
      setAutoScroll(true);
      setUserScrolled(false);
      setSeenCount(events.length);
    }
  }, [events.length]);

  const newEventCount = Math.max(0, events.length - seenCount);

  return (
    <div className="flex-1 flex flex-col min-h-0 relative">
      {/* Event list */}
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto px-3 py-2 space-y-2"
      >
        {events.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <EmptyEvents />
          </div>
        ) : (
          grouped.map((gev, i) => (
            <ErrorBoundary
              key={`g-${i}`}
              fallback={<div className="text-[10px] text-[#555] px-2 py-1">Event render error</div>}
            >
              <GroupedEventCard
                event={gev}
                isLast={i === grouped.length - 1 && !pendingPrompt}
                runActive={runActive && (!lastInterruptionTs || gev.ts > lastInterruptionTs)}
                runPaused={runPaused}
              />
            </ErrorBoundary>
          ))
        )}
        {pendingPrompt && (
          <PendingInjectBubble
            prompt={pendingPrompt.prompt}
            ts={pendingPrompt.ts}
            status={pendingPrompt.status}
          />
        )}
      </div>

      {/* Scroll-to-bottom FAB — centered, animated */}
      <AnimatePresence>
        {userScrolled && (
          <motion.button
            initial={FAB_INITIAL}
            animate={FAB_ANIMATE}
            exit={FAB_EXIT}
            transition={FAB_TRANSITION}
            onClick={scrollToBottom}
            className={clsx(
              "absolute bottom-4 left-1/2 -translate-x-1/2 z-10",
              "flex items-center gap-1.5 px-3 py-1.5 rounded",
              "bg-[#00ff88]/10 text-[#00ff88] text-[9px] font-medium",
              "border border-[#00ff88]/20 frosted-glass",
              "hover:bg-[#00ff88]/20 transition-colors"
            )}
          >
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
              <line x1="5" y1="2" x2="5" y2="8" />
              <polyline points="3 6 5 8 7 6" />
            </svg>
            {newEventCount > 0 ? `${newEventCount} new event${newEventCount === 1 ? "" : "s"}` : "New events"}
          </motion.button>
        )}
      </AnimatePresence>
    </div>
  );
}
