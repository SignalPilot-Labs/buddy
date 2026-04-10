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

const SCROLL_BEHAVIOR = "smooth" as const;
const CARD_ENTER_DURATION = 0.2;
const CARD_ENTER_Y = 6;
const CARD_ENTER_EASE = "easeOut";
const SKELETON_COUNT = 3;
const SKELETON_HEIGHT = "h-12";
const LOADING_OPACITY = 0.4;
const LOADING_OPACITY_TRANSITION = "opacity 0.2s";

export function EventFeed({
  events,
  pendingMessages = [],
  runActive = false,
  runPaused = false,
  isLoading = false,
}: {
  events: FeedEvent[];
  pendingMessages?: PendingMessage[];
  runActive?: boolean;
  runPaused?: boolean;
  isLoading?: boolean;
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
    if (autoScroll && containerRef.current?.scrollTo) {
      containerRef.current.scrollTo({ top: containerRef.current.scrollHeight, behavior: SCROLL_BEHAVIOR });
    }
  }, [grouped, pendingMessages, autoScroll]);

  const handleScroll = useCallback(() => {
    if (!containerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 20;
    setAutoScroll((prev) => (prev === isAtBottom ? prev : isAtBottom));
    setUserScrolled((prev) => (prev === !isAtBottom ? prev : !isAtBottom));
  }, []);

  const scrollToBottom = useCallback(() => {
    if (containerRef.current?.scrollTo) {
      containerRef.current.scrollTo({ top: containerRef.current.scrollHeight, behavior: SCROLL_BEHAVIOR });
      setAutoScroll(true);
      setUserScrolled(false);
      setSeenCount(events.length);
    }
  }, [events.length]);

  const newEventCount = Math.max(0, events.length - seenCount);

  const hasContent = events.length > 0 || pendingMessages.length > 0;
  const showSkeleton = isLoading && !hasContent;
  const containerOpacity = isLoading && hasContent ? LOADING_OPACITY : 1;

  return (
    <div className="flex-1 flex flex-col min-h-0 relative">
      {/* Event list */}
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto px-3 py-2 space-y-2"
        style={{ opacity: containerOpacity, transition: LOADING_OPACITY_TRANSITION }}
      >
        {showSkeleton ? (
          <div className="space-y-3 py-4">
            {Array.from({ length: SKELETON_COUNT }, (_, i) => (
              <div key={i} className={`${SKELETON_HEIGHT} rounded bg-white/[0.03] animate-pulse`} />
            ))}
          </div>
        ) : !hasContent ? (
          <div className="flex items-center justify-center h-full">
            <EmptyEvents />
          </div>
        ) : (
          <>
            <AnimatePresence mode="popLayout">
              {grouped.map((gev, i) => (
                <motion.div
                  key={gev.id}
                  initial={{ opacity: 0, y: CARD_ENTER_Y }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: CARD_ENTER_DURATION, ease: CARD_ENTER_EASE }}
                >
                  <ErrorBoundary
                    fallback={<div className="text-[10px] text-[#555] px-2 py-1">Event render error</div>}
                  >
                    <GroupedEventCard
                      event={gev}
                      isLast={i === grouped.length - 1 && pendingMessages.length === 0}
                      runActive={runActive && (!lastInterruptionTs || gev.ts > lastInterruptionTs)}
                      runPaused={runPaused}
                    />
                  </ErrorBoundary>
                </motion.div>
              ))}
            </AnimatePresence>
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
            {newEventCount > 0 ? `${newEventCount} new event${newEventCount === 1 ? "" : "s"}` : "Jump to latest"}
          </motion.button>
        )}
      </AnimatePresence>
    </div>
  );
}
