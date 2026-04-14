"use client";

import type { FeedEvent, ToolCall } from "@/lib/types";
import { fetchToolCalls, fetchAuditLog } from "@/lib/api";
import { HISTORY_FETCH_LIMIT } from "@/lib/constants";

function mergeToolPhases(tools: ToolCall[]): ToolCall[] {
  // Pair pre/post tool rows strictly by tool_use_id. An unmatched post is
  // kept as-is so error outputs stay visible. Name-based fallback matching
  // has been removed — it was dead code (the backend always stores a
  // tool_use_id) and could mis-pair concurrent Agent calls.
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
  truncated: boolean;
}

export async function loadRunHistory(id: string): Promise<HistoryResult> {
  const [tools, audits] = await Promise.all([
    fetchToolCalls(id, HISTORY_FETCH_LIMIT + 1),
    fetchAuditLog(id, HISTORY_FETCH_LIMIT + 1),
  ]);

  const truncated = tools.length > HISTORY_FETCH_LIMIT || audits.length > HISTORY_FETCH_LIMIT;
  const trimmedTools = tools.length > HISTORY_FETCH_LIMIT ? tools.slice(0, HISTORY_FETCH_LIMIT) : tools;
  const trimmedAudits = audits.length > HISTORY_FETCH_LIMIT ? audits.slice(0, HISTORY_FETCH_LIMIT) : audits;

  const lastToolId = trimmedTools.reduce((max, t) => Math.max(max, t.id ?? 0), 0);
  const lastAuditId = trimmedAudits.reduce((max, a) => Math.max(max, a.id ?? 0), 0);

  trimmedTools.sort((a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime() || a.id - b.id);
  trimmedAudits.sort((a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime() || a.id - b.id);

  const toolEvents: FeedEvent[] = mergeToolPhases(trimmedTools).map((t) => ({
    _kind: "tool" as const,
    data: t,
  }));
  const auditEvents = buildAuditEvents(trimmedAudits);

  // Sort merged events by ts, then audits before tools (priority 0 vs 1), then by id
  const events = [...toolEvents, ...auditEvents].sort((a, b) => {
    const tsA = new Date(getEventTs(a)).getTime();
    const tsB = new Date(getEventTs(b)).getTime();
    if (tsA !== tsB) return tsA - tsB;
    const prioA = a._kind === "tool" ? 1 : 0;
    const prioB = b._kind === "tool" ? 1 : 0;
    if (prioA !== prioB) return prioA - prioB;
    const idA = a._kind === "tool" ? a.data.id : a._kind === "audit" ? a.data.id : 0;
    const idB = b._kind === "tool" ? b.data.id : b._kind === "audit" ? b.data.id : 0;
    return idA - idB;
  });

  return { events, lastToolId, lastAuditId, truncated };
}
