"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import type { FeedEvent, ToolCall, AuditEvent, UsageEvent } from "@/lib/types";
import { createSSE, pollEvents } from "@/lib/api";

const SSE_TIMEOUT = 3000;
const POLL_INTERVAL = 1000;

export function useSSE(runId: string | null) {
  const [events, setEvents] = useState<FeedEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const esRef = useRef<EventSource | null>(null);
  const afterToolRef = useRef(0);
  const afterAuditRef = useRef(0);
  const pollingRef = useRef(false);
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const sseTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const gotMessageRef = useRef(false);
  const cancelledRef = useRef(false);

  const clearEvents = useCallback(() => setEvents([]), []);

  useEffect(() => {
    if (!runId) return;

    setEvents([]);
    setConnected(false);
    afterToolRef.current = 0;
    afterAuditRef.current = 0;
    pollingRef.current = false;
    gotMessageRef.current = false;
    cancelledRef.current = false;

    function processTool(data: ToolCall) {
      if (data.phase === "post") {
        setEvents((prev) => {
          for (let i = prev.length - 1; i >= 0; i--) {
            const ev = prev[i];
            if (ev._kind !== "tool" || ev.data.phase !== "pre" || ev.data.output_data) continue;

            const idMatch = data.tool_use_id && ev.data.tool_use_id === data.tool_use_id;
            const nameMatch = !data.tool_use_id && ev.data.tool_name === data.tool_name;

            if (idMatch || nameMatch) {
              const merged = { ...ev.data };
              merged.output_data = data.output_data;
              merged.duration_ms = data.duration_ms;
              merged.phase = "post";
              const next = [...prev];
              next[i] = { _kind: "tool", data: merged };
              return next;
            }
          }
          return [...prev, { _kind: "tool", data }];
        });
      } else {
        setEvents((prev) => [...prev, { _kind: "tool", data }]);
      }
    }

    function processAudit(raw: AuditEvent) {
      const details =
        typeof raw.details === "string"
          ? JSON.parse(raw.details)
          : raw.details || {};

      if (raw.event_type === "usage") {
        setEvents((prev) => [
          ...prev,
          { _kind: "usage", data: { ...details, ts: raw.ts } as UsageEvent },
        ]);
      } else if (raw.event_type === "llm_text") {
        const role = details.agent_role || "worker";
        setEvents((prev) => {
          const last = prev[prev.length - 1];
          if (last && last._kind === "llm_text" && last.agent_role === role) {
            return [
              ...prev.slice(0, -1),
              { ...last, text: last.text + (details.text || "") },
            ];
          }
          return [
            ...prev,
            { _kind: "llm_text", text: details.text || "", ts: raw.ts, agent_role: role },
          ];
        });
      } else if (raw.event_type === "llm_thinking") {
        const role = details.agent_role || "worker";
        setEvents((prev) => {
          const last = prev[prev.length - 1];
          if (last && last._kind === "llm_thinking" && last.agent_role === role) {
            return [
              ...prev.slice(0, -1),
              { ...last, text: last.text + (details.text || "") },
            ];
          }
          return [
            ...prev,
            { _kind: "llm_thinking", text: details.text || "", ts: raw.ts, agent_role: role },
          ];
        });
      } else {
        setEvents((prev) => [
          ...prev,
          { _kind: "audit", data: { ...raw, details } },
        ]);
      }
    }

    async function doPoll() {
      if (cancelledRef.current || !runId) return;
      try {
        const result = await pollEvents(runId, afterToolRef.current, afterAuditRef.current);

        for (const tc of result.tool_calls) {
          processTool(tc);
          if (tc.id > afterToolRef.current) afterToolRef.current = tc.id;
        }

        for (const al of result.audit_events) {
          processAudit(al);
          if (al.id > afterAuditRef.current) afterAuditRef.current = al.id;
        }
      } catch (err) {
        console.error("Poll failed:", err);
      }
    }

    function switchToPolling() {
      if (cancelledRef.current || pollingRef.current) return;

      pollingRef.current = true;
      setConnected(false);

      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }

      pollIntervalRef.current = setInterval(doPoll, POLL_INTERVAL);
    }

    function cancelSseTimeout() {
      if (sseTimeoutRef.current) {
        clearTimeout(sseTimeoutRef.current);
        sseTimeoutRef.current = null;
      }
    }

    function onAnyMessage() {
      if (!gotMessageRef.current) {
        gotMessageRef.current = true;
        cancelSseTimeout();
      }
    }

    const es = createSSE(runId);
    esRef.current = es;

    sseTimeoutRef.current = setTimeout(() => {
      if (!gotMessageRef.current && !cancelledRef.current) {
        console.warn("SSE timeout — switching to polling");
        switchToPolling();
      }
    }, SSE_TIMEOUT);

    es.addEventListener("connected", () => {
      onAnyMessage();
      setConnected(true);
    });

    es.addEventListener("ping", () => {
      onAnyMessage();
    });

    es.addEventListener("tool_call", (e: MessageEvent) => {
      onAnyMessage();
      try {
        const data: ToolCall = JSON.parse(e.data);
        processTool(data);
        if (data.id > afterToolRef.current) afterToolRef.current = data.id;
      } catch (err) {
        console.error("Failed to parse tool_call SSE event:", err);
      }
    });

    es.addEventListener("audit", (e: MessageEvent) => {
      onAnyMessage();
      try {
        const raw: AuditEvent = JSON.parse(e.data);
        processAudit(raw);
        if (raw.id > afterAuditRef.current) afterAuditRef.current = raw.id;
      } catch (err) {
        console.error("Failed to parse audit SSE event:", err);
      }
    });

    es.addEventListener("run_ended", (e: MessageEvent) => {
      onAnyMessage();
      try {
        const data = JSON.parse(e.data);
        setEvents((prev) => [
          ...prev,
          { _kind: "audit", data: { id: 0, run_id: runId ?? "", event_type: "run_ended", details: data, ts: new Date().toISOString() } },
        ]);
      } catch (err) {
        console.error("Failed to parse run_ended event:", err);
      }
      setConnected(false);
      es.close();
    });

    es.onerror = () => {
      setConnected(false);
      if (cancelledRef.current) return;

      if (!gotMessageRef.current) {
        cancelSseTimeout();
        console.warn("SSE error before first message — switching to polling");
        switchToPolling();
      }
    };

    return () => {
      cancelledRef.current = true;
      cancelSseTimeout();
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
    };
  }, [runId]);

  return { events, connected, clearEvents };
}
