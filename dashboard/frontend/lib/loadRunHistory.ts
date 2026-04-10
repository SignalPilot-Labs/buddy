"use client";

import type { FeedEvent, ToolCall } from "@/lib/types";
import { fetchToolCalls, fetchAuditLog } from "@/lib/api";
import { HISTORY_FETCH_LIMIT } from "@/lib/constants";

function mergeToolPhases(tools: ToolCall[]): ToolCall[] {
  const merged: ToolCall[] = [];

  for (const t of tools) {
    if (t.phase === "pre") {
      merged.push({ ...t });
      continue;
    }
    let matched = false;
    if (t.tool_use_id) {
      for (let j = merged.length - 1; j >= 0; j--) {
        const pre = merged[j];
        if (pre.tool_use_id === t.tool_use_id && pre.phase === "pre") {
          pre.output_data = t.output_data;
          pre.duration_ms = t.duration_ms;
          pre.phase = "post";
          matched = true;
          break;
        }
      }
    }
    if (!matched) {
      for (let j = merged.length - 1; j >= 0; j--) {
        const pre = merged[j];
        if (pre.tool_name === t.tool_name && pre.phase === "pre" && !pre.output_data) {
          pre.output_data = t.output_data;
          pre.duration_ms = t.duration_ms;
          pre.phase = "post";
          matched = true;
          break;
        }
      }
    }
    if (!matched) merged.push({ ...t });
  }

  return merged;
}

function buildAuditEvents(audits: { id: number; run_id: string; ts: string; event_type: string; details: Record<string, unknown> }[]): FeedEvent[] {
  const events: FeedEvent[] = [];
  for (const a of audits) {
    let details: Record<string, unknown>;
    try {
      details = typeof a.details === "string" ? JSON.parse(a.details) : a.details || {};
    } catch {
      details = {};
    }
    if (a.event_type === "llm_text" || a.event_type === "llm_thinking") {
      const kind = a.event_type === "llm_text" ? "llm_text" as const : "llm_thinking" as const;
      const role = String(details.agent_role || "worker");
      const last = events[events.length - 1];
      if (last && last._kind === kind && last.agent_role === role) {
        events[events.length - 1] = { ...last, text: last.text + String(details.text || "") };
      } else {
        events.push({ _kind: kind, text: String(details.text || ""), ts: a.ts, agent_role: role });
      }
    } else {
      events.push({ _kind: "audit" as const, data: { ...a, details } });
    }
  }
  return events;
}

function getEventTs(e: FeedEvent): string {
  if (e._kind === "tool") return e.data.ts;
  if (e._kind === "audit") return e.data.ts;
  if (e._kind === "usage") return e.data.ts;
  return e.ts;
}

export interface HistoryResult {
  events: FeedEvent[];
  lastToolId: number;
  lastAuditId: number;
}

export async function loadRunHistory(id: string): Promise<HistoryResult> {
  const [tools, audits] = await Promise.all([
    fetchToolCalls(id, HISTORY_FETCH_LIMIT),
    fetchAuditLog(id, HISTORY_FETCH_LIMIT),
  ]);

  const lastToolId = tools.reduce((max, t) => Math.max(max, t.id ?? 0), 0);
  const lastAuditId = audits.reduce((max, a) => Math.max(max, a.id ?? 0), 0);

  tools.sort((a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime());
  audits.sort((a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime());

  const toolEvents: FeedEvent[] = mergeToolPhases(tools).map((t) => ({
    _kind: "tool" as const,
    data: t,
  }));
  const auditEvents = buildAuditEvents(audits);

  const events = [...toolEvents, ...auditEvents].sort(
    (a, b) => new Date(getEventTs(a)).getTime() - new Date(getEventTs(b)).getTime()
  );

  return { events, lastToolId, lastAuditId };
}
