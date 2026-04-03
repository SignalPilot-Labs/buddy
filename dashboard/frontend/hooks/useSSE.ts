"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import type { FeedEvent, ToolCall, AuditEvent, UsageEvent } from "@/lib/types";
import { createSSE } from "@/lib/api";

const MAX_RECONNECT_ATTEMPTS = 10;
const BASE_RECONNECT_DELAY_MS = 1000;
const MAX_RECONNECT_DELAY_MS = 30000;

export function useSSE(runId: string | null) {
  const [events, setEvents] = useState<FeedEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const esRef = useRef<EventSource | null>(null);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const cancelledRef = useRef(false);

  const clearEvents = useCallback(() => setEvents([]), []);

  useEffect(() => {
    if (!runId) return;

    setEvents([]);
    setConnected(false);
    reconnectAttemptRef.current = 0;
    cancelledRef.current = false;

    function connect() {
      if (cancelledRef.current) return;

      // Close any previous connection
      if (esRef.current) {
        esRef.current.close();
      }

      const es = createSSE(runId!);
      esRef.current = es;

      es.addEventListener("connected", () => {
        setConnected(true);
        reconnectAttemptRef.current = 0;
      });

      es.addEventListener("tool_call", (e: MessageEvent) => {
        try {
          const data: ToolCall = JSON.parse(e.data);
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
        } catch (err) {
          console.error("Failed to parse tool_call SSE event:", err);
        }
      });

      es.addEventListener("audit", (e: MessageEvent) => {
        try {
          const raw: AuditEvent = JSON.parse(e.data);
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
        } catch (err) {
          console.error("Failed to parse audit SSE event:", err);
        }
      });

      es.addEventListener("run_ended", (e: MessageEvent) => {
        try {
          const data = JSON.parse(e.data);
          setEvents((prev) => [
            ...prev,
            { _kind: "audit", data: { id: 0, run_id: runId, event_type: "run_ended", details: data, ts: new Date().toISOString() } },
          ]);
        } catch (err) {
          console.error("Failed to parse run_ended event:", err);
        }
        // Clean close — no reconnection needed
        setConnected(false);
        es.close();
      });

      es.onerror = () => {
        setConnected(false);

        if (cancelledRef.current) return;

        // Reconnect with exponential backoff
        if (reconnectAttemptRef.current < MAX_RECONNECT_ATTEMPTS) {
          const delay = Math.min(
            BASE_RECONNECT_DELAY_MS * Math.pow(2, reconnectAttemptRef.current),
            MAX_RECONNECT_DELAY_MS,
          );
          reconnectAttemptRef.current += 1;
          console.warn(
            `SSE disconnected, reconnecting in ${delay}ms ` +
            `(attempt ${reconnectAttemptRef.current}/${MAX_RECONNECT_ATTEMPTS})`,
          );
          reconnectTimerRef.current = setTimeout(connect, delay);
        } else {
          console.error("SSE reconnection failed after max attempts");
        }
      };
    }

    connect();

    return () => {
      cancelledRef.current = true;
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
    };
  }, [runId]);

  return { events, connected, clearEvents };
}
