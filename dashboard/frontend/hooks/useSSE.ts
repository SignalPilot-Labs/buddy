"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import type { FeedEvent, ToolCall, AuditEvent, UsageEvent } from "@/lib/types";
import { createSSE, pollEvents } from "@/lib/api";
import { SSE_POLL_INTERVAL_MS, SSE_FALLBACK_TIMEOUT_MS } from "@/lib/constants";
import { mergeToolEvent, mergeToolEventMutable } from "@/lib/eventMerge";

export interface SSECursor {
  afterTool: number;
  afterAudit: number;
}

type PendingItem =
  | { type: "tool"; data: ToolCall }
  | { type: "audit"; data: AuditEvent };

function processAuditInto(events: FeedEvent[], raw: AuditEvent): void {
  const details =
    typeof raw.details === "string"
      ? JSON.parse(raw.details)
      : raw.details || {};

  if (raw.event_type === "usage") {
    events.push({ _kind: "usage", data: { ...details, ts: raw.ts } as UsageEvent });
    return;
  }
  if (raw.event_type === "llm_text") {
    const role = details.agent_role || "worker";
    const last = events[events.length - 1];
    if (last && last._kind === "llm_text" && last.agent_role === role) {
      events[events.length - 1] = { ...last, text: last.text + (details.text || "") };
      return;
    }
    events.push({ _kind: "llm_text", text: details.text || "", ts: raw.ts, agent_role: role });
    return;
  }
  if (raw.event_type === "llm_thinking") {
    const role = details.agent_role || "worker";
    const last = events[events.length - 1];
    if (last && last._kind === "llm_thinking" && last.agent_role === role) {
      events[events.length - 1] = { ...last, text: last.text + (details.text || "") };
      return;
    }
    events.push({ _kind: "llm_thinking", text: details.text || "", ts: raw.ts, agent_role: role });
    return;
  }
  events.push({ _kind: "audit", data: { ...raw, details } });
}

function applyBatch(prev: FeedEvent[], batch: PendingItem[]): FeedEvent[] {
  const next = [...prev];
  for (const item of batch) {
    if (item.type === "tool") {
      mergeToolEventMutable(next, item.data);
    } else {
      processAuditInto(next, item.data);
    }
  }
  return next;
}

const POLL_INTERVAL = SSE_POLL_INTERVAL_MS;

export function useSSE(onRunEnded?: () => void, onSessionResumed?: () => void) {
  const [events, setEvents] = useState<FeedEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const esRef = useRef<EventSource | null>(null);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const runIdRef = useRef<string | null>(null);
  const genRef = useRef(0);
  const onRunEndedRef = useRef(onRunEnded);
  const onSessionResumedRef = useRef(onSessionResumed);
  onRunEndedRef.current = onRunEnded;
  onSessionResumedRef.current = onSessionResumed;

  // rAF batching refs
  const pendingRef = useRef<PendingItem[]>([]);
  const rafRef = useRef<number>(0);

  const scheduleFlush = useCallback(() => {
    if (rafRef.current !== 0) return;
    rafRef.current = requestAnimationFrame(() => {
      rafRef.current = 0;
      const batch = pendingRef.current;
      if (batch.length === 0) return;
      pendingRef.current = [];
      setEvents((prev) => applyBatch(prev, batch));
    });
  }, []);

  const clearEvents = useCallback(() => {
    if (rafRef.current !== 0) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = 0;
    }
    pendingRef.current = [];
    setEvents([]);
  }, []);

  const disconnect = useCallback(() => {
    genRef.current++;
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
    setConnected(false);
    runIdRef.current = null;
  }, []);

  const connect = useCallback((runId: string, cursor: SSECursor) => {
    // Clean up any existing connection
    if (timeoutRef.current) { clearTimeout(timeoutRef.current); timeoutRef.current = null; }
    if (esRef.current) { esRef.current.close(); esRef.current = null; }
    if (pollingRef.current) { clearInterval(pollingRef.current); pollingRef.current = null; }

    const gen = ++genRef.current;
    runIdRef.current = runId;
    setEvents([]);
    setConnected(false);

    let sseGotMessage = false;
    let afterTool = cursor.afterTool;
    let afterAudit = cursor.afterAudit;

    // --- Polling fallback ---
    function startPolling() {
      if (pollingRef.current) return;
      setConnected(true);
      pollingRef.current = setInterval(async () => {
        if (gen !== genRef.current) return;
        try {
          const result = await pollEvents(runId, afterTool, afterAudit);
          if (gen !== genRef.current) return;
          if (result.tool_calls.length > 0 || result.audit_events.length > 0) {
            let runEnded = false;
            setEvents((prev) => {
              let next = prev;
              for (const tc of result.tool_calls) {
                afterTool = Math.max(afterTool, tc.id ?? 0);
                next = mergeToolEvent(next, tc);
              }
              for (const ae of result.audit_events) {
                afterAudit = Math.max(afterAudit, ae.id ?? 0);
                const batchForAudit: PendingItem[] = [{ type: "audit", data: ae }];
                next = applyBatch(next, batchForAudit);
                if (ae.event_type === "run_ended") runEnded = true;
                if (ae.event_type === "session_resumed") onSessionResumedRef.current?.();
              }
              return next;
            });
            if (runEnded && pollingRef.current) {
              clearInterval(pollingRef.current);
              pollingRef.current = null;
              setConnected(false);
              onRunEndedRef.current?.();
            }
          }
        } catch (err) {
          console.warn("Poll request failed:", err);
        }
      }, POLL_INTERVAL);
    }

    function switchToPolling() {
      if (pollingRef.current) return;
      if (esRef.current) { esRef.current.close(); esRef.current = null; }
      startPolling();
    }

    // --- SSE primary with timeout fallback ---
    const es = createSSE(runId, cursor.afterTool, cursor.afterAudit);
    esRef.current = es;

    timeoutRef.current = setTimeout(() => {
      if (gen !== genRef.current) return;
      if (!sseGotMessage) switchToPolling();
    }, SSE_FALLBACK_TIMEOUT_MS);

    es.addEventListener("connected", () => {
      if (gen !== genRef.current) return;
      sseGotMessage = true;
      if (timeoutRef.current) { clearTimeout(timeoutRef.current); timeoutRef.current = null; }
      setConnected(true);
    });

    es.addEventListener("ping", () => {
      if (gen !== genRef.current) return;
      sseGotMessage = true;
    });

    es.addEventListener("tool_call", (e) => {
      if (gen !== genRef.current) return;
      sseGotMessage = true;
      try {
        const data: ToolCall = JSON.parse(e.data);
        pendingRef.current.push({ type: "tool", data });
        scheduleFlush();
      } catch (err) {
        console.warn("Failed to parse tool_call SSE event:", err);
      }
    });

    es.addEventListener("audit", (e) => {
      if (gen !== genRef.current) return;
      sseGotMessage = true;
      try {
        const raw: AuditEvent = JSON.parse(e.data);
        if (raw.event_type === "session_resumed") onSessionResumedRef.current?.();
        pendingRef.current.push({ type: "audit", data: raw });
        scheduleFlush();
      } catch (err) {
        console.warn("Failed to parse audit SSE event:", err);
      }
    });

    es.addEventListener("run_ended", (e) => {
      if (gen !== genRef.current) return;
      sseGotMessage = true;
      try {
        const data = JSON.parse(e.data);
        // Flush any pending batch first, then append run_ended
        const batch = pendingRef.current;
        pendingRef.current = [];
        if (rafRef.current !== 0) {
          cancelAnimationFrame(rafRef.current);
          rafRef.current = 0;
        }
        setEvents((prev) => {
          const next = applyBatch(prev, batch);
          next.push({ _kind: "audit", data: { id: 0, run_id: runId, event_type: "run_ended", details: data, ts: new Date().toISOString() } });
          return next;
        });
      } catch (err) {
        console.warn("Failed to parse run_ended SSE event:", err);
      }
      setConnected(false);
      es.close();
      if (pollingRef.current) { clearInterval(pollingRef.current); pollingRef.current = null; }
      onRunEndedRef.current?.();
    });

    es.onerror = () => {
      if (gen !== genRef.current) return;
      setConnected(false);
      if (!sseGotMessage) switchToPolling();
    };
  }, [scheduleFlush]);

  // Clean up on unmount
  useEffect(() => () => {
    disconnect();
    if (rafRef.current !== 0) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = 0;
    }
  }, [disconnect]);

  return { events, connected, clearEvents, connect, disconnect };
}
