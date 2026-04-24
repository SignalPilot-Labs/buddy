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

export function deduplicateToolEvents(
  history: FeedEvent[],
  live: FeedEvent[],
  prebuiltMap?: Map<string, number>,
): { patchedHistory: FeedEvent[]; filteredLive: FeedEvent[] } {
  let historyToolIdxMap: Map<string, number>;
  if (prebuiltMap) {
    historyToolIdxMap = prebuiltMap;
  } else {
    historyToolIdxMap = new Map<string, number>();
    for (let i = 0; i < history.length; i++) {
      const ev = history[i];
      if (ev._kind === "tool" && ev.data.tool_use_id !== null) {
        historyToolIdxMap.set(ev.data.tool_use_id, i);
      }
    }
  }

  let patchedHistory = history;
  const filteredLive: FeedEvent[] = [];
  for (const ev of live) {
    if (
      ev._kind === "tool" &&
      ev.data.phase === "post" &&
      ev.data.tool_use_id !== null &&
      historyToolIdxMap.has(ev.data.tool_use_id)
    ) {
      const idx = historyToolIdxMap.get(ev.data.tool_use_id)!;
      if (patchedHistory === history) {
        patchedHistory = [...history];
      }
      const orig = patchedHistory[idx];
      if (orig._kind === "tool") {
        patchedHistory[idx] = {
          _kind: "tool",
          data: {
            ...orig.data,
            output_data: ev.data.output_data,
            duration_ms: ev.data.duration_ms,
            phase: ev.data.phase,
          },
        };
      }
    } else {
      filteredLive.push(ev);
    }
  }

  return { patchedHistory, filteredLive };
}

export function useEventState(liveEvents: FeedEvent[]): EventState {
  const [historyEvents, setHistoryEvents] = useState<FeedEvent[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyTruncated, setHistoryTruncated] = useState(false);

  const historyToolIdxMap = useMemo(() => {
    const map = new Map<string, number>();
    for (let i = 0; i < historyEvents.length; i++) {
      const ev = historyEvents[i];
      if (ev._kind === "tool" && ev.data.tool_use_id !== null) {
        map.set(ev.data.tool_use_id, i);
      }
    }
    return map;
  }, [historyEvents]);

  const allEvents = useMemo(() => {
    if (liveEvents.length === 0) return historyEvents;
    if (historyEvents.length === 0) return liveEvents;

    const { patchedHistory, filteredLive } = deduplicateToolEvents(historyEvents, liveEvents, historyToolIdxMap);

    const lastHistoryTs = getEventTs(patchedHistory[patchedHistory.length - 1]);
    const firstLiveTs = filteredLive.length > 0 ? getEventTs(filteredLive[0]) : lastHistoryTs;
    if (firstLiveTs >= lastHistoryTs) {
      return [...patchedHistory, ...filteredLive];
    }
    return [...patchedHistory, ...filteredLive].sort((a, b) => {
      const tsA = getEventTs(a);
      const tsB = getEventTs(b);
      if (tsA < tsB) return -1;
      if (tsA > tsB) return 1;
      return getEventPriority(a) - getEventPriority(b) || getEventId(a) - getEventId(b);
    });
  }, [historyEvents, liveEvents, historyToolIdxMap]);

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
