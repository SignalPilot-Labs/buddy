/**
 * Pre/post tool call pairing for live SSE events.
 */

import type { FeedEvent, ToolCall } from "@/lib/types";

/**
 * Merge a tool call event into an existing mutable event array.
 *
 * Mutates `events` in-place when merging a post onto an existing pre, and
 * always pushes new events onto the array. The caller (applyBatch) owns the
 * immutability boundary — it passes a copy of `prev` to this function, then
 * calls setEvents with that mutated copy.
 *
 * Post events are matched to their pre strictly by tool_use_id. A post
 * without a matching pre is appended as-is so error outputs stay visible
 * (see tool-error-render tests). Name-based fallback matching has been
 * removed: the backend always emits a tool_use_id, so a missing one is a
 * bug to surface, not paper over.
 */
export function mergeToolEventMutable(events: FeedEvent[], data: ToolCall): void {
  if (data.phase === "post" && data.tool_use_id) {
    for (let i = events.length - 1; i >= 0; i--) {
      const ev = events[i];
      if (ev._kind !== "tool" || ev.data.phase !== "pre" || ev.data.output_data)
        continue;
      if (ev.data.tool_use_id !== data.tool_use_id) continue;
      const merged = { ...ev.data };
      merged.output_data = data.output_data;
      merged.duration_ms = data.duration_ms;
      merged.phase = "post";
      events[i] = { _kind: "tool", data: merged };
      return;
    }
  }
  events.push({ _kind: "tool", data });
}

/**
 * Immutable variant — returns a new array. Used when a single event arrives
 * outside the rAF batch (e.g. polling path).
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
