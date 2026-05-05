"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import type { FeedEvent, ToolCall, AuditEvent, UsageEvent, ConnectionState } from "@/lib/types";
import { createSSE, fetchSseToken, pollEvents } from "@/lib/api";
import type { PollEventItem } from "@/lib/api";
import {
  SSE_POLL_INTERVAL_MS,
  SSE_FALLBACK_TIMEOUT_MS,
  RECONNECT_BASE_MS,
  RECONNECT_MAX_MS,
  RECONNECT_MAX_ATTEMPTS,
} from "@/lib/constants";
import { mergeToolEvent } from "@/lib/eventMerge";

export interface SSECursor {
  afterTool: number;
  afterAudit: number;
}

function processAudit(prev: FeedEvent[], raw: AuditEvent): FeedEvent[] {
  let details: Record<string, unknown>;
  if (typeof raw.details === "string") {
    try {
      details = JSON.parse(raw.details) as Record<string, unknown>;
    } catch {
      console.warn("processAudit: invalid JSON in details, skipping event", raw.event_type);
      return prev;
    }
  } else {
    details = raw.details || {};
  }

  if (raw.event_type === "usage") {
    return [
      ...prev,
      { _kind: "usage", data: { ...details, ts: raw.ts } as UsageEvent },
    ];
  }
  if (raw.event_type === "llm_text") {
    const role = String(details.agent_role || "worker");
    const text = String(details.text || "");
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
    const role = String(details.agent_role || "worker");
    const text = String(details.text || "");
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

type BufferedItem =
  | { kind: "tool"; data: ToolCall }
  | { kind: "audit"; data: AuditEvent };

function applyBuffer(prev: FeedEvent[], buffer: BufferedItem[]): FeedEvent[] {
  let next = prev;
  for (const item of buffer) {
    if (item.kind === "tool") {
      next = mergeToolEvent(next, item.data);
    } else {
      next = processAudit(next, item.data);
    }
  }
  return next;
}

const POLL_INTERVAL = SSE_POLL_INTERVAL_MS;

export function useSSE(onRunEnded?: () => void, onSessionResumed?: () => void) {
  const [events, setEvents] = useState<FeedEvent[]>([]);
  const [connectionState, setConnectionState] = useState<ConnectionState>("disconnected");
  const esRef = useRef<EventSource | null>(null);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const runIdRef = useRef<string | null>(null);
  const genRef = useRef(0);
  const onRunEndedRef = useRef(onRunEnded);
  const onSessionResumedRef = useRef(onSessionResumed);
  onRunEndedRef.current = onRunEnded;
  onSessionResumedRef.current = onSessionResumed;

  // RAF-batched event buffer
  const bufferRef = useRef<BufferedItem[]>([]);
  const rafRef = useRef<number | null>(null);

  // Reconnect state
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Cursor tracking for reconnect
  const lastToolCursorRef = useRef(0);
  const lastAuditCursorRef = useRef(0);

  function flushBuffer(): void {
    rafRef.current = null;
    if (bufferRef.current.length === 0) return;
    const snapshot = bufferRef.current;
    bufferRef.current = [];
    setEvents((prev) => applyBuffer(prev, snapshot));
  }

  function scheduleFlush(): void {
    if (rafRef.current !== null) return;
    rafRef.current = requestAnimationFrame(flushBuffer);
  }

  const clearEvents = useCallback(() => setEvents([]), []);

  const disconnect = useCallback(() => {
    genRef.current++;
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
    // Cancel pending RAF and flush any buffered events synchronously
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    if (bufferRef.current.length > 0) {
      const snapshot = bufferRef.current;
      bufferRef.current = [];
      setEvents((prev) => applyBuffer(prev, snapshot));
    }
    setConnectionState("disconnected");
    runIdRef.current = null;
  }, []);

  const connect = useCallback(async (runId: string, cursor: SSECursor): Promise<void> => {
    // Clean up any existing connection and pending reconnect timers
    if (timeoutRef.current) { clearTimeout(timeoutRef.current); timeoutRef.current = null; }
    if (reconnectTimerRef.current) { clearTimeout(reconnectTimerRef.current); reconnectTimerRef.current = null; }
    if (esRef.current) { esRef.current.close(); esRef.current = null; }
    if (pollingRef.current) { clearInterval(pollingRef.current); pollingRef.current = null; }
    if (rafRef.current !== null) { cancelAnimationFrame(rafRef.current); rafRef.current = null; }
    bufferRef.current = [];

    // Reset reconnect attempt counter on fresh connect
    reconnectAttemptRef.current = 0;

    const gen = ++genRef.current;
    runIdRef.current = runId;
    setEvents([]);
    setConnectionState("disconnected");

    // Initialize cursor refs so reconnect uses correct cursors even if no events arrive
    lastToolCursorRef.current = cursor.afterTool;
    lastAuditCursorRef.current = cursor.afterAudit;

    let sseGotMessage = false;
    let afterTool = cursor.afterTool;
    let afterAudit = cursor.afterAudit;

    // --- Polling fallback ---
    function startPolling() {
      if (pollingRef.current) return;
      setConnectionState("connected");
      pollingRef.current = setInterval(async () => {
        if (gen !== genRef.current) return;
        try {
          const result = await pollEvents(runId, afterTool, afterAudit);
          if (gen !== genRef.current) return;
          if (result.events.length > 0) {
            const hasRunEnded = result.events.some(
              (ev) => ev._event_type === "audit" && (ev as AuditEvent & { _event_type: "audit" }).event_type === "run_ended",
            );
            setEvents((prev) => {
              let next = prev;
              for (const ev of result.events) {
                if (ev._event_type === "tool_call") {
                  const tc = ev as PollEventItem & { _event_type: "tool_call" };
                  afterTool = Math.max(afterTool, tc.id ?? 0);
                  lastToolCursorRef.current = afterTool;
                  next = mergeToolEvent(next, tc);
                } else {
                  const ae = ev as PollEventItem & { _event_type: "audit" };
                  afterAudit = Math.max(afterAudit, ae.id ?? 0);
                  lastAuditCursorRef.current = afterAudit;
                  next = processAudit(next, ae);
                  if (ae.event_type === "run_resumed") onSessionResumedRef.current?.();
                }
              }
              return next;
            });
            if (hasRunEnded) {
              if (pollingRef.current) { clearInterval(pollingRef.current); pollingRef.current = null; }
              setConnectionState("disconnected");
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

    function scheduleReconnect() {
      if (gen !== genRef.current) return;
      const attempt = reconnectAttemptRef.current;
      if (attempt >= RECONNECT_MAX_ATTEMPTS) {
        switchToPolling();
        return;
      }
      const delay = Math.min(RECONNECT_BASE_MS * Math.pow(2, attempt), RECONNECT_MAX_MS);
      reconnectAttemptRef.current = attempt + 1;
      reconnectTimerRef.current = setTimeout(() => {
        if (gen !== genRef.current) return;
        reconnectTimerRef.current = null;
        // Fetch a fresh token — the previous one may have expired during backoff
        fetchSseToken().then((token) => {
          if (gen !== genRef.current) return;
          const es2 = createSSE(runId, lastToolCursorRef.current, lastAuditCursorRef.current, token);
          esRef.current = es2;
          attachSSEHandlers(es2);
        }).catch((err) => {
          console.warn("SSE token fetch failed during reconnect, switching to polling:", err);
          if (gen !== genRef.current) return;
          switchToPolling();
        });
      }, delay);
    }

    function attachSSEHandlers(es: EventSource): void {
      es.addEventListener("connected", () => {
        if (gen !== genRef.current) return;
        sseGotMessage = true;
        if (timeoutRef.current) { clearTimeout(timeoutRef.current); timeoutRef.current = null; }
        reconnectAttemptRef.current = 0;
        setConnectionState("connected");
      });

      es.addEventListener("ping", () => {
        if (gen !== genRef.current) return;
        sseGotMessage = true;
      });

      es.addEventListener("tool_call", (e) => {
        if (gen !== genRef.current) return;
        sseGotMessage = true;
        try {
          const data: ToolCall = JSON.parse((e as MessageEvent).data);
          lastToolCursorRef.current = Math.max(lastToolCursorRef.current, data.id ?? 0);
          bufferRef.current.push({ kind: "tool", data });
          scheduleFlush();
        } catch (err) {
          console.warn("Failed to parse tool_call SSE event:", err);
        }
      });

      es.addEventListener("audit", (e) => {
        if (gen !== genRef.current) return;
        sseGotMessage = true;
        try {
          const raw: AuditEvent = JSON.parse((e as MessageEvent).data);
          lastAuditCursorRef.current = Math.max(lastAuditCursorRef.current, raw.id ?? 0);
          if (raw.event_type === "run_resumed") onSessionResumedRef.current?.();
          bufferRef.current.push({ kind: "audit", data: raw });
          scheduleFlush();
        } catch (err) {
          console.warn("Failed to parse audit SSE event:", err);
        }
      });

      es.addEventListener("run_ended", () => {
        if (gen !== genRef.current) return;
        sseGotMessage = true;
        // The run_ended audit event was already emitted to the DB and delivered
        // via the "audit" SSE listener. This server event just signals teardown
        // is complete — flush remaining buffer and disconnect.
        if (rafRef.current !== null) {
          cancelAnimationFrame(rafRef.current);
          rafRef.current = null;
        }
        const pending = bufferRef.current;
        bufferRef.current = [];
        if (pending.length > 0) {
          setEvents((prev) => applyBuffer(prev, pending));
        }
        setConnectionState("disconnected");
        es.close();
        if (pollingRef.current) { clearInterval(pollingRef.current); pollingRef.current = null; }
        onRunEndedRef.current?.();
      });

      es.onerror = () => {
        if (gen !== genRef.current) return;
        if (!sseGotMessage) {
          switchToPolling();
          return;
        }
        // SSE was working — flush buffer then attempt reconnect with backoff
        if (rafRef.current !== null) {
          cancelAnimationFrame(rafRef.current);
          rafRef.current = null;
        }
        if (bufferRef.current.length > 0) {
          const snapshot = bufferRef.current;
          bufferRef.current = [];
          setEvents((prev) => applyBuffer(prev, snapshot));
        }
        es.close();
        esRef.current = null;
        setConnectionState("reconnecting");
        scheduleReconnect();
      };
    }

    // --- SSE primary with timeout fallback ---
    // Fetch an ephemeral token before opening the EventSource so the API key
    // never appears in the SSE URL (and therefore never in server access logs).
    try {
      const token = await fetchSseToken();
      if (gen !== genRef.current) return;
      const es = createSSE(runId, cursor.afterTool, cursor.afterAudit, token);
      esRef.current = es;

      timeoutRef.current = setTimeout(() => {
        if (gen !== genRef.current) return;
        if (!sseGotMessage) switchToPolling();
      }, SSE_FALLBACK_TIMEOUT_MS);

      attachSSEHandlers(es);
    } catch (err) {
      console.warn("SSE token fetch failed, switching to polling:", err);
      if (gen !== genRef.current) return;
      switchToPolling();
    }
  }, []);

  // Clean up on unmount
  useEffect(() => () => { disconnect(); }, [disconnect]);

  const connected = connectionState === "connected";
  return { events, connected, connectionState, clearEvents, connect, disconnect };
}
