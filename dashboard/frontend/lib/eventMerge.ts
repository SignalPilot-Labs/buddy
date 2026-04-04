/**
 * Shared event merge utilities — pre/post tool call pairing.
 *
 * Used by both useSSE (live events) and page.tsx (history+live merge).
 */

import type { FeedEvent, ToolCall } from "@/lib/types";

/**
 * Merge a tool call event into an existing event list.
 * Post events are matched to their pre by tool_use_id (or tool_name fallback),
 * enriching the pre entry with output_data and duration.
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
  const merged = [...history];

  for (let i = 0; i < merged.length; i++) {
    const ev = merged[i];
    if (
      ev._kind === "tool" &&
      ev.data.phase === "pre" &&
      !ev.data.output_data &&
      ev.data.tool_use_id
    ) {
      preIndex.set(ev.data.tool_use_id, i);
    }
  }

  for (const ev of live) {
    if (
      ev._kind === "tool" &&
      ev.data.phase === "post" &&
      ev.data.tool_use_id &&
      preIndex.has(ev.data.tool_use_id)
    ) {
      const idx = preIndex.get(ev.data.tool_use_id)!;
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
      preIndex.delete(ev.data.tool_use_id);
    } else {
      merged.push(ev);
    }
  }

  return merged;
}
