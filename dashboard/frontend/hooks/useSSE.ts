"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import type { FeedEvent, ToolCall, AuditEvent, UsageEvent } from "@/lib/types";
import { createSSE, pollEvents } from "@/lib/api";
import type { PollEventItem } from "@/lib/api";
import { SSE_POLL_INTERVAL_MS, SSE_FALLBACK_TIMEOUT_MS } from "@/lib/constants";
import { mergeToolEvent } from "@/lib/eventMerge";

export interface SSECursor {
  afterTool: number;
  afterAudit: number;
}

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
  if (raw.event_type === "llm_text") {
    const role = details.agent_role || "worker";
    const last = prev[prev.length - 1];
    if (last && last._kind === "llm_text" && last.agent_role === role) {
      return [
        ...prev.slice(0, -1),
        { ...last, text: last.text + (details.text || "") },
      ];
    }
    return [
      ...prev,
      {
        _kind: "llm_text",
        text: details.text || "",
        ts: raw.ts,
        agent_role: role,
      },
    ];
  }
  if (raw.event_type === "llm_thinking") {
    const role = details.agent_role || "worker";
    const last = prev[prev.length - 1];
    if (last && last._kind === "llm_thinking" && last.agent_role === role) {
      return [
        ...prev.slice(0, -1),
        { ...last, text: last.text + (details.text || "") },
      ];
    }
    return [
      ...prev,
      {
        _kind: "llm_thinking",
        text: details.text || "",
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

  // RAF-batched event buffer
  const bufferRef = useRef<BufferedItem[]>([]);
  const rafRef = useRef<number | null>(null);

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
    setConnected(false);
    runIdRef.current = null;
  }, []);

  const connect = useCallback((runId: string, cursor: SSECursor) => {
    // Clean up any existing connection
    if (timeoutRef.current) { clearTimeout(timeoutRef.current); timeoutRef.current = null; }
    if (esRef.current) { esRef.current.close(); esRef.current = null; }
    if (pollingRef.current) { clearInterval(pollingRef.current); pollingRef.current = null; }
    if (rafRef.current !== null) { cancelAnimationFrame(rafRef.current); rafRef.current = null; }
    bufferRef.current = [];

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
          if (result.events.length > 0) {
            let runEnded = false;
            setEvents((prev) => {
              let next = prev;
              for (const ev of result.events) {
                if (ev._event_type === "tool_call") {
                  const tc = ev as PollEventItem & { _event_type: "tool_call" };
                  afterTool = Math.max(afterTool, tc.id ?? 0);
                  next = mergeToolEvent(next, tc);
                } else {
                  const ae = ev as PollEventItem & { _event_type: "audit" };
                  afterAudit = Math.max(afterAudit, ae.id ?? 0);
                  next = processAudit(next, ae);
                  if (ae.event_type === "run_ended") runEnded = true;
                  if (ae.event_type === "session_resumed") onSessionResumedRef.current?.();
                }
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
        const raw: AuditEvent = JSON.parse(e.data);
        if (raw.event_type === "session_resumed") onSessionResumedRef.current?.();
        bufferRef.current.push({ kind: "audit", data: raw });
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
        // Flush any buffered events before appending run_ended
        if (rafRef.current !== null) {
          cancelAnimationFrame(rafRef.current);
          rafRef.current = null;
        }
        const pending = bufferRef.current;
        bufferRef.current = [];
        setEvents((prev) => {
          let next = applyBuffer(prev, pending);
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
      if (!sseGotMessage) switchToPolling();
    };
  }, []);

  // Clean up on unmount
  useEffect(() => () => { disconnect(); }, [disconnect]);

  return { events, connected, clearEvents, connect, disconnect };
}
