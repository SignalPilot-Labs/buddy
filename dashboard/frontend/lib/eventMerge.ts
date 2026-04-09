/**
 * Shared event merge utilities — pre/post tool call pairing.
 *
 * Used by both useSSE (live events) and page.tsx (history+live merge).
 */

import type { FeedEvent, ToolCall } from "@/lib/types";

export const NO_RESPONSE_SENTINEL: Record<string, unknown> = { _no_response: true };

/**
 * Scan backward through events and mark the most recent unmatched pre event
 * for the same agent as completed with a no-response sentinel.
 * Tools within a single agent execute sequentially, so a new pre event means
 * the previous tool finished (even if no post event arrived).
 */
function closeOrphanedPre(events: FeedEvent[], newPre: ToolCall): FeedEvent[] {
  for (let i = events.length - 1; i >= 0; i--) {
    const ev = events[i];
    if (
      ev._kind !== "tool" ||
      ev.data.phase !== "pre" ||
      ev.data.output_data !== null
    ) {
      continue;
    }
    if (ev.data.agent_id !== newPre.agent_id) continue;

    const closed: FeedEvent = {
      _kind: "tool",
      data: {
        ...ev.data,
        phase: "post",
        output_data: NO_RESPONSE_SENTINEL,
      },
    };
    const next = [...events];
    next[i] = closed;
    return next;
  }
  return events;
}

/**
 * Merge a tool call event into an existing event list.
 * Post events are matched to their pre by tool_use_id (or tool_name fallback),
 * enriching the pre entry with output_data and duration.
 * When a pre event arrives, any orphaned pre from the same agent is auto-closed.
 */
export function mergeToolEvent(prev: FeedEvent[], data: ToolCall): FeedEvent[] {
  if (data.phase === "post") {
    for (let i = prev.length - 1; i >= 0; i--) {
      const ev = prev[i];
      if (ev._kind !== "tool" || ev.data.phase !== "pre" || ev.data.output_data)
        continue;
      const idMatch =
        data.tool_use_id && ev.data.tool_use_id === data.tool_use_id;
      const nameMatch =
        !data.tool_use_id && ev.data.tool_name === data.tool_name;
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
  }

  if (data.phase === "pre") {
    const withOrphanClosed = closeOrphanedPre(prev, data);
    return [...withOrphanClosed, { _kind: "tool", data }];
  }

  return [...prev, { _kind: "tool", data }];
}

/**
 * Merge live events into a history list.
 * Post tool events that match a pre in history get merged in-place;
 * all other events are appended.
 */
export function mergeHistoryWithLive(
  history: FeedEvent[],
  live: FeedEvent[],
): FeedEvent[] {
  if (live.length === 0) return history;

  const preIndex = new Map<string, number>();
  const preIndexByName = new Map<string, number>();
  const seenAuditIds = new Set<number>();
  const seenToolIds = new Set<number>();
  const hasHistoryText = history.some((e) => e._kind === "llm_text" || e._kind === "llm_thinking");
  const merged = [...history];

  for (let i = 0; i < merged.length; i++) {
    const ev = merged[i];
    if (ev._kind === "tool") {
      if (ev.data.phase === "pre" && !ev.data.output_data) {
        if (ev.data.tool_use_id) {
          preIndex.set(ev.data.tool_use_id, i);
        } else {
          preIndexByName.set(ev.data.tool_name, i);
        }
      }
      if (ev.data.id) seenToolIds.add(ev.data.id);
    } else if (ev._kind === "audit" && ev.data.id) {
      seenAuditIds.add(ev.data.id);
    }
  }

  for (const ev of live) {
    if (ev._kind === "tool" && ev.data.phase === "post") {
      const idxById = ev.data.tool_use_id ? preIndex.get(ev.data.tool_use_id) : undefined;
      const idxByName = !ev.data.tool_use_id ? preIndexByName.get(ev.data.tool_name) : undefined;
      const idx = idxById ?? idxByName;

      if (idx !== undefined) {
        const pre = merged[idx];
        if (pre._kind === "tool") {
          merged[idx] = {
            _kind: "tool",
            data: {
              ...pre.data,
              output_data: ev.data.output_data,
              duration_ms: ev.data.duration_ms,
              phase: "post",
            },
          };
        }
        if (ev.data.tool_use_id) {
          preIndex.delete(ev.data.tool_use_id);
        } else {
          preIndexByName.delete(ev.data.tool_name);
        }
        continue;
      }
    }

    if (ev._kind === "audit" && ev.data.id && seenAuditIds.has(ev.data.id)) {
      continue;
    } else if (ev._kind === "tool" && ev.data.id && seenToolIds.has(ev.data.id)) {
      continue;
    } else if (hasHistoryText && (ev._kind === "llm_text" || ev._kind === "llm_thinking")) {
      continue;
    } else {
      merged.push(ev);
    }
  }

  return merged;
}
