"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import type { FeedEvent, ToolCall, AuditEvent, UsageEvent } from "@/lib/types";
import { createSSE, pollEvents } from "@/lib/api";
import { fetchRun } from "@/lib/api";
import { SSE_POLL_INTERVAL_MS, SSE_FALLBACK_TIMEOUT_MS, SSE_RECONNECT_DELAY_MS, TERMINAL_STATUSES } from "@/lib/constants";
import type { RunStatus } from "@/lib/types";
import { mergeToolEvent } from "@/lib/eventMerge";

export interface SSECursor {
  afterTool: number;
  afterAudit: number;
}

function processAudit(prev: FeedEvent[], raw: AuditEvent): FeedEvent[] {
  const details =
    typeof raw.details === "string"
      ? (JSON.parse(raw.details) as Record<string, unknown>)
      : raw.details;

  if (raw.event_type === "usage") {
    return [
      ...prev,
      { _kind: "usage", data: { ...details, ts: raw.ts } as UsageEvent },
    ];
  }
  if (raw.event_type === "llm_text") {
    const role = typeof details.agent_role === "string" ? details.agent_role : "worker";
    const text = typeof details.text === "string" ? details.text : "";
    const last = prev[prev.length - 1];
    if (last && last._kind === "llm_text" && last.agent_role === role) {
      return [
        ...prev.slice(0, -1),
        { ...last, text: last.text + text },
      ];
    }
    return [
      ...prev,
      {
        _kind: "llm_text",
        text,
        ts: raw.ts,
        agent_role: role,
      },
    ];
  }
  if (raw.event_type === "llm_thinking") {
    const role = typeof details.agent_role === "string" ? details.agent_role : "worker";
    const text = typeof details.text === "string" ? details.text : "";
    const last = prev[prev.length - 1];
    if (last && last._kind === "llm_thinking" && last.agent_role === role) {
      return [
        ...prev.slice(0, -1),
        { ...last, text: last.text + text },
      ];
    }
    return [
      ...prev,
      {
        _kind: "llm_thinking",
        text,
        ts: raw.ts,
        agent_role: role,
      },
    ];
  }
  return [...prev, { _kind: "audit", data: { ...raw, details } }];
}

const POLL_INTERVAL = SSE_POLL_INTERVAL_MS;

type PendingSSEEvent =
  | { type: "tool"; data: ToolCall }
  | { type: "audit"; data: AuditEvent };

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

  // SSE batching refs
  const pendingEventsRef = useRef<PendingSSEEvent[]>([]);
  const batchScheduledRef = useRef(false);

  const clearEvents = useCallback(() => setEvents([]), []);

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

  const connect = useCallback((runId: string, cursor: SSECursor, onConnected?: () => void) => {
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
            setEvents((prev) => {
              let next = prev;
              for (const tc of result.tool_calls) {
                afterTool = Math.max(afterTool, tc.id);
                next = mergeToolEvent(next, tc);
              }
              for (const ae of result.audit_events) {
                afterAudit = Math.max(afterAudit, ae.id);
                next = processAudit(next, ae);
                if (ae.event_type === "session_resumed") onSessionResumedRef.current?.();
              }
              return next;
            });
          } else {
            // No new events — check if run has reached a terminal status
            try {
              const run = await fetchRun(runId);
              if (gen !== genRef.current) return;
              if (TERMINAL_STATUSES.has(run.status as RunStatus)) {
                if (pollingRef.current) {
                  clearInterval(pollingRef.current);
                  pollingRef.current = null;
                }
                setConnected(false);
                onRunEndedRef.current?.();
              }
            } catch (statusErr) {
              console.warn("Failed to check run status:", statusErr);
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

    // Flush all pending SSE events in a single state update
    function flushPending(): void {
      batchScheduledRef.current = false;
      const batch = pendingEventsRef.current;
      pendingEventsRef.current = [];
      if (batch.length === 0) return;
      setEvents((prev) => {
        let next = prev;
        for (const item of batch) {
          if (item.type === "tool") {
            next = mergeToolEvent(next, item.data);
          } else {
            next = processAudit(next, item.data);
          }
        }
        return next;
      });
    }

    function scheduleFlush(): void {
      if (batchScheduledRef.current) return;
      batchScheduledRef.current = true;
      queueMicrotask(flushPending);
    }

    es.addEventListener("connected", () => {
      if (gen !== genRef.current) return;
      sseGotMessage = true;
      if (timeoutRef.current) { clearTimeout(timeoutRef.current); timeoutRef.current = null; }
      setConnected(true);
      onConnected?.();
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
        pendingEventsRef.current.push({ type: "tool", data });
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
        pendingEventsRef.current.push({ type: "audit", data: raw });
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
        setEvents((prev) => [
          ...prev,
          { _kind: "audit", data: { id: 0, run_id: runId, event_type: "run_ended", details: data, ts: new Date().toISOString() } },
        ]);
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
      if (sseGotMessage) {
        // SSE was working then dropped — wait 5s for EventSource to auto-reconnect
        // before switching to polling.
        if (timeoutRef.current) clearTimeout(timeoutRef.current);
        timeoutRef.current = setTimeout(() => {
          if (gen !== genRef.current) return;
          switchToPolling();
        }, SSE_RECONNECT_DELAY_MS);
      } else {
        switchToPolling();
      }
    };
  }, []);

  // Clean up on unmount
  useEffect(() => () => { disconnect(); }, [disconnect]);

  return { events, connected, clearEvents, connect, disconnect };
}
