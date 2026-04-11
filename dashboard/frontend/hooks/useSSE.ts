"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import type { FeedEvent, ToolCall, AuditEvent, UsageEvent } from "@/lib/types";
import { createSSE, pollEvents } from "@/lib/api";
import { SSE_POLL_INTERVAL_MS, SSE_FALLBACK_TIMEOUT_MS, SSE_RECONNECT_DELAY_MS, SSE_MAX_RECONNECTS, DEFAULT_AGENT_ROLE } from "@/lib/constants";
import { mergeToolEvent } from "@/lib/eventMerge";

export interface SSECursor {
  afterTool: number;
  afterAudit: number;
}

type PendingItem =
  | { type: "tool"; data: ToolCall }
  | { type: "audit"; data: AuditEvent };

function processAudit(prev: FeedEvent[], raw: AuditEvent): FeedEvent[] {
  const details =
    typeof raw.details === "string"
      ? JSON.parse(raw.details)
      : raw.details || {};

  if (raw.event_type === "usage") {
    return [
      ...prev,
      { _kind: "usage", data: { ...details, ts: raw.ts } as UsageEvent },
    ];
  }

  if (raw.event_type === "llm_text" || raw.event_type === "llm_thinking") {
    const kind = raw.event_type === "llm_text" ? "llm_text" as const : "llm_thinking" as const;
    const role = String(details.agent_role || DEFAULT_AGENT_ROLE);

    // Scan backward for the last matching event of this kind+role.
    // Stop if a tool/audit/usage boundary is hit — those mark temporal
    // separations after which LLM text of the same role should NOT be merged.
    // Passing over LLM events of OTHER roles is allowed (parallel agents).
    let matchIndex = -1;
    let foundBoundary = false;
    for (let i = prev.length - 1; i >= 0; i--) {
      const e = prev[i];
      if (e._kind === kind && e.agent_role === role) {
        matchIndex = i;
        break;
      }
      if (e._kind === "tool" || e._kind === "audit" || e._kind === "usage") {
        foundBoundary = true;
        break;
      }
    }

    if (matchIndex >= 0 && !foundBoundary) {
      const existing = prev[matchIndex] as Extract<FeedEvent, { _kind: "llm_text" | "llm_thinking" }>;
      const updated = { ...existing, text: existing.text + String(details.text || "") };
      return [...prev.slice(0, matchIndex), updated, ...prev.slice(matchIndex + 1)];
    }

    return [
      ...prev,
      {
        _kind: kind,
        text: String(details.text || ""),
        ts: raw.ts,
        agent_role: role,
      },
    ];
  }

  return [...prev, { _kind: "audit", data: { ...raw, details } }];
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

  // Cursor refs — track the highest IDs seen so reconnect/polling can resume
  const afterToolRef = useRef(0);
  const afterAuditRef = useRef(0);

  // Reconnect state
  const reconnectCountRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // rAF batch buffer: accumulate pending events and flush in a single setState
  const pendingRef = useRef<PendingItem[]>([]);
  const flushScheduledRef = useRef(false);

  const flushPending = useCallback(() => {
    flushScheduledRef.current = false;
    const items = pendingRef.current.splice(0);
    if (items.length === 0) return;
    setEvents((prev) => {
      let next = prev;
      for (const item of items) {
        if (item.type === "tool") {
          afterToolRef.current = Math.max(afterToolRef.current, item.data.id ?? 0);
          next = mergeToolEvent(next, item.data);
        } else {
          afterAuditRef.current = Math.max(afterAuditRef.current, item.data.id ?? 0);
          next = processAudit(next, item.data);
        }
      }
      return next;
    });
  }, []);

  const scheduleFlush = useCallback(() => {
    if (flushScheduledRef.current) return;
    flushScheduledRef.current = true;
    requestAnimationFrame(flushPending);
  }, [flushPending]);

  const clearEvents = useCallback(() => setEvents([]), []);

  const disconnect = useCallback(() => {
    genRef.current++;
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
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
    // Clean up any existing connection and pending reconnect
    if (reconnectTimerRef.current) { clearTimeout(reconnectTimerRef.current); reconnectTimerRef.current = null; }
    if (timeoutRef.current) { clearTimeout(timeoutRef.current); timeoutRef.current = null; }
    if (esRef.current) { esRef.current.close(); esRef.current = null; }
    if (pollingRef.current) { clearInterval(pollingRef.current); pollingRef.current = null; }

    const gen = ++genRef.current;
    runIdRef.current = runId;

    // Initialise cursor refs from the caller-supplied cursor
    afterToolRef.current = cursor.afterTool;
    afterAuditRef.current = cursor.afterAudit;

    // Do NOT clear events here — the caller (useDashboard) manages clearing
    // to avoid the flash of empty state before history loads.
    setConnected(false);

    let sseGotMessage = false;

    // --- Polling fallback ---
    function startPolling() {
      if (pollingRef.current) return;
      setConnected(true);
      pollingRef.current = setInterval(async () => {
        if (gen !== genRef.current) return;
        try {
          const result = await pollEvents(runId, afterToolRef.current, afterAuditRef.current);
          if (gen !== genRef.current) return;
          if (result.tool_calls.length > 0 || result.audit_events.length > 0) {
            let runEnded = false;
            setEvents((prev) => {
              let next = prev;
              for (const tc of result.tool_calls) {
                afterToolRef.current = Math.max(afterToolRef.current, tc.id ?? 0);
                next = mergeToolEvent(next, tc);
              }
              for (const ae of result.audit_events) {
                afterAuditRef.current = Math.max(afterAuditRef.current, ae.id ?? 0);
                next = processAudit(next, ae);
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
      reconnectCountRef.current = 0;
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
        // Flush any pending before appending run_ended so order is preserved
        const pending = pendingRef.current.splice(0);
        setEvents((prev) => {
          let next = prev;
          for (const item of pending) {
            if (item.type === "tool") {
              afterToolRef.current = Math.max(afterToolRef.current, item.data.id ?? 0);
              next = mergeToolEvent(next, item.data);
            } else {
              afterAuditRef.current = Math.max(afterAuditRef.current, item.data.id ?? 0);
              next = processAudit(next, item.data);
            }
          }
          return [
            ...next,
            { _kind: "audit", data: { id: 0, run_id: runId, event_type: "run_ended", details: data, ts: new Date().toISOString() } },
          ];
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
      if (!sseGotMessage) {
        switchToPolling();
        return;
      }
      // SSE was live and then dropped — attempt reconnect
      if (reconnectCountRef.current < SSE_MAX_RECONNECTS) {
        reconnectCountRef.current++;
        const capturedGen = gen;
        reconnectTimerRef.current = setTimeout(() => {
          if (capturedGen !== genRef.current) return;
          connect(runId, { afterTool: afterToolRef.current, afterAudit: afterAuditRef.current });
        }, SSE_RECONNECT_DELAY_MS);
      } else {
        switchToPolling();
      }
    };
  }, [scheduleFlush]);

  // Clean up on unmount
  useEffect(() => () => { disconnect(); }, [disconnect]);

  return { events, connected, clearEvents, connect, disconnect };
}
