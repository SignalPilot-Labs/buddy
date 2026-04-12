"use client";

import { useState, useCallback, useEffect, useRef, useMemo } from "react";
import type { FeedEvent, PendingMessage } from "@/lib/types";

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
  pendingMessages: PendingMessage[];
  setHistoryEvents: (events: FeedEvent[]) => void;
  setHistoryLoading: (loading: boolean) => void;
  setHistoryTruncated: (truncated: boolean) => void;
  setPendingMessages: React.Dispatch<React.SetStateAction<PendingMessage[]>>;
  addEvent: (event: FeedEvent) => void;
  addPendingMessage: (prompt: string) => number;
  markPendingFailed: (id: number) => void;
  failAllPending: () => void;
}

export function useEventState(liveEvents: FeedEvent[]): EventState {
  const [historyEvents, setHistoryEvents] = useState<FeedEvent[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyTruncated, setHistoryTruncated] = useState(false);
  const [pendingMessages, setPendingMessages] = useState<PendingMessage[]>([]);

  // Clear pending messages by prompt text matching when prompt events arrive via SSE
  const confirmedPromptsRef = useRef<Set<string>>(new Set());
  useEffect(() => {
    // Reset when liveEvents is cleared (run switch, session resumed, etc.)
    if (liveEvents.length === 0) {
      confirmedPromptsRef.current = new Set();
      return;
    }
    const confirmedTexts = liveEvents
      .filter((e) => e._kind === "audit" && (e.data.event_type === "prompt_injected" || e.data.event_type === "prompt_submitted"))
      .map((e) => {
        if (e._kind !== "audit") return "";
        return String(e.data.details.prompt || "");
      })
      .filter((t) => t.length > 0);
    const newConfirmed = confirmedTexts.filter((t) => !confirmedPromptsRef.current.has(t));
    if (newConfirmed.length === 0) return;
    for (const t of newConfirmed) confirmedPromptsRef.current.add(t);
    const confirmedSet = new Set(newConfirmed);
    setPendingMessages((prev) =>
      prev.filter((m) => m.status !== "pending" || !confirmedSet.has(m.prompt)),
    );
  }, [liveEvents]);

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

  const addPendingMessage = useCallback((prompt: string): number => {
    const id = -Date.now();
    setPendingMessages((prev) => [...prev, { id, prompt, ts: new Date().toISOString(), status: "pending" }]);
    return id;
  }, []);

  const markPendingFailed = useCallback((id: number) => {
    setPendingMessages((prev) => prev.map((m) => m.id === id ? { ...m, status: "failed" } : m));
  }, []);

  const failAllPending = useCallback(() => {
    setPendingMessages((prev) => {
      if (prev.length === 0) return prev;
      return prev.map((m) => m.status === "pending" ? { ...m, status: "failed" } : m);
    });
  }, []);

  return {
    historyEvents,
    liveEvents,
    allEvents,
    historyLoading,
    historyTruncated,
    pendingMessages,
    setHistoryEvents,
    setHistoryLoading,
    setHistoryTruncated,
    setPendingMessages,
    addEvent,
    addPendingMessage,
    markPendingFailed,
    failAllPending,
  };
}
