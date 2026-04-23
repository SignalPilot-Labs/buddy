"use client";

import { useState, useCallback, useMemo } from "react";
import type { FeedEvent } from "@/lib/types";

function getEventTs(e: FeedEvent): string {
  if (e._kind === "tool") return e.data.ts;
  if (e._kind === "audit") return e.data.ts;
  if (e._kind === "usage") return e.data.ts;
  return e.ts;
}

function getEventPriority(e: FeedEvent): number {
  // Audit/llm events sort before tool events at same timestamp (matches backend TYPE_PRIORITY)
  return e._kind === "tool" ? 1 : 0;
}

function getEventId(e: FeedEvent): number {
  if (e._kind === "tool") return e.data.id;
  if (e._kind === "audit") return e.data.id;
  return 0;
}

export interface EventState {
  historyEvents: FeedEvent[];
  liveEvents: FeedEvent[];
  allEvents: FeedEvent[];
  historyLoading: boolean;
  historyTruncated: boolean;
  setHistoryEvents: (events: FeedEvent[]) => void;
  setHistoryLoading: (loading: boolean) => void;
  setHistoryTruncated: (truncated: boolean) => void;
  addEvent: (event: FeedEvent) => void;
}

export function useEventState(liveEvents: FeedEvent[]): EventState {
  const [historyEvents, setHistoryEvents] = useState<FeedEvent[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyTruncated, setHistoryTruncated] = useState(false);

  const allEvents = useMemo(() => {
    if (liveEvents.length === 0) return historyEvents;
    if (historyEvents.length === 0) return liveEvents;
    // Common path: history is already sorted and live events follow chronologically.
    // Only sort if timestamps overlap (reconnect scenario).
    const lastHistoryTs = getEventTs(historyEvents[historyEvents.length - 1]);
    const firstLiveTs = getEventTs(liveEvents[0]);
    if (firstLiveTs >= lastHistoryTs) {
      return [...historyEvents, ...liveEvents];
    }
    return [...historyEvents, ...liveEvents].sort((a, b) => {
      const tsA = getEventTs(a);
      const tsB = getEventTs(b);
      if (tsA < tsB) return -1;
      if (tsA > tsB) return 1;
      return getEventPriority(a) - getEventPriority(b) || getEventId(a) - getEventId(b);
    });
  }, [historyEvents, liveEvents]);

  const addEvent = useCallback((event: FeedEvent) => {
    setHistoryEvents((prev) => [...prev, event]);
  }, []);

  return {
    historyEvents,
    liveEvents,
    allEvents,
    historyLoading,
    historyTruncated,
    setHistoryEvents,
    setHistoryLoading,
    setHistoryTruncated,
    addEvent,
  };
}
