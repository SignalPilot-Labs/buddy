/**
 * Pre/post tool call pairing for live SSE events.
 */

import type { FeedEvent, ToolCall } from "@/lib/types";

/**
 * Merge a tool call event into an existing event list.
 *
 * Post events are matched to their pre strictly by tool_use_id. A post
 * without a matching pre is appended as-is so error outputs stay visible
 * (see tool-error-render tests). Name-based fallback matching has been
 * removed: the backend always emits a tool_use_id, so a missing one is a
 * bug to surface, not paper over.
 */
export function mergeToolEvent(prev: FeedEvent[], data: ToolCall): FeedEvent[] {
  if (data.phase === "post" && data.tool_use_id) {
    for (let i = prev.length - 1; i >= 0; i--) {
      const ev = prev[i];
      if (ev._kind !== "tool" || ev.data.phase !== "pre" || ev.data.output_data)
        continue;
      if (ev.data.tool_use_id !== data.tool_use_id) continue;
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
}
