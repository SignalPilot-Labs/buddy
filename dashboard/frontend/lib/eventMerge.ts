/**
 * Pre/post tool call pairing for live SSE events.
 */

import type { FeedEvent, ToolCall } from "@/lib/types";

const NAME_MATCH_WINDOW_MS = 30_000;

function isWithinWindow(preTs: string, postTs: string): boolean {
  return Math.abs(new Date(postTs).getTime() - new Date(preTs).getTime()) < NAME_MATCH_WINDOW_MS;
}

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
        !data.tool_use_id
        && ev.data.tool_name === data.tool_name
        && isWithinWindow(ev.data.ts, data.ts);
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
