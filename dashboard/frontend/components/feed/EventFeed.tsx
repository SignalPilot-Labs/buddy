"use client";

import { useRef, useEffect, useState, useCallback, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { clsx } from "clsx";
import type { FeedEvent, PendingMessage } from "@/lib/types";
import { groupEvents } from "@/lib/groupEvents";
import { GroupedEventCard } from "./GroupedEventCard";
import { UserPromptCard } from "./MessageCards";
import { EmptyEvents } from "@/components/ui/EmptyStates";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";

const FAB_INITIAL = { opacity: 0, y: 8 };
const FAB_ANIMATE = { opacity: 1, y: 0 };
const FAB_EXIT = { opacity: 0, y: 8 };
const FAB_TRANSITION = { duration: 0.15 };

export function EventFeed({
  events,
  pendingMessages = [],
  runActive = false,
  runPaused = false,
}: {
  events: FeedEvent[];
  pendingMessages?: PendingMessage[];
  runActive?: boolean;
  runPaused?: boolean;
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
      if (gev.type === "user_prompt") return gev.ts;
      if (gev.type === "milestone" && interruptLabels.has(gev.label)) return gev.ts;
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
  }, [grouped, pendingMessages, autoScroll]);

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
        {events.length === 0 && pendingMessages.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <EmptyEvents />
          </div>
        ) : (
          <>
            {grouped.map((gev, i) => (
              <ErrorBoundary
                key={`g-${i}`}
                fallback={<div className="text-[10px] text-[#555] px-2 py-1">Event render error</div>}
              >
                <GroupedEventCard
                  event={gev}
                  isLast={i === grouped.length - 1 && pendingMessages.length === 0}
                  runActive={runActive && (!lastInterruptionTs || gev.ts > lastInterruptionTs)}
                  runPaused={runPaused}
                />
              </ErrorBoundary>
            ))}
            {pendingMessages.map((msg) => (
              <UserPromptCard
                key={`pending-${msg.id}`}
                prompt={msg.prompt}
                ts={msg.ts}
                pending={msg.status === "pending"}
                failed={msg.status === "failed"}
              />
            ))}
          </>
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
