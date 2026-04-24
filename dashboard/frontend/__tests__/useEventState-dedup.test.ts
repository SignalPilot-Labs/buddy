/**
 * Regression test: allEvents deduplicates tool events across history and live.
 *
 * When a live tool event with phase "post" has a tool_use_id matching a
 * history event with phase "pre", the post data is merged into the history
 * entry and the live event is excluded. This prevents duplicate cards for
 * tool calls that span history/live boundary.
 */

import { describe, it, expect } from "vitest";
import { renderHook } from "@testing-library/react";
import { useEventState, deduplicateToolEvents } from "@/hooks/useEventState";
import { makeToolEvent } from "./testFactories";

describe("deduplicateToolEvents (pure function)", () => {
  it("merges post-phase live event into matching pre-phase history entry", () => {
    const historyPre = makeToolEvent({
      id: 99,
      phase: "pre",
      tool_use_id: "toolu_abc",
      output_data: null,
      duration_ms: null,
    });
    const livePost = makeToolEvent({
      id: 101,
      phase: "post",
      tool_use_id: "toolu_abc",
      output_data: { result: "ok" },
      duration_ms: 50,
    });

    const { patchedHistory, filteredLive } = deduplicateToolEvents([historyPre], [livePost]);
    expect(filteredLive).toHaveLength(0);
    expect(patchedHistory).toHaveLength(1);
    const merged = patchedHistory[0];
    expect(merged._kind).toBe("tool");
    if (merged._kind === "tool") {
      expect(merged.data.id).toBe(99);
      expect(merged.data.phase).toBe("post");
      expect(merged.data.output_data).toEqual({ result: "ok" });
      expect(merged.data.duration_ms).toBe(50);
    }
  });
});

describe("useEventState: allEvents dedup across history and live", () => {
  it("merges post-phase live into pre-phase history after history is set", () => {
    const historyPre = makeToolEvent({
      id: 99,
      phase: "pre",
      tool_use_id: "toolu_xyz",
      output_data: null,
      duration_ms: null,
    });
    const livePost = makeToolEvent({
      id: 100,
      phase: "post",
      tool_use_id: "toolu_xyz",
      output_data: { result: "done" },
      duration_ms: 75,
    });

    // Use renderHook with initial props so we can update
    const { result, rerender } = renderHook(
      ({ live }: { live: typeof livePost[] }) => useEventState(live),
      { initialProps: { live: [livePost] } },
    );

    // Set history events
    result.current.setHistoryEvents([historyPre]);
    rerender({ live: [livePost] });

    const allEvents = result.current.allEvents;
    // Should deduplicate: exactly one event for toolu_xyz
    const toolUseEvents = allEvents.filter(
      e => e._kind === "tool" && e.data.tool_use_id === "toolu_xyz",
    );
    expect(toolUseEvents).toHaveLength(1);
    // The merged event should have post-phase data
    const merged = toolUseEvents[0];
    expect(merged._kind).toBe("tool");
    if (merged._kind === "tool") {
      expect(merged.data.phase).toBe("post");
      expect(merged.data.output_data).toEqual({ result: "done" });
      expect(merged.data.duration_ms).toBe(75);
      // id should be from history (99)
      expect(merged.data.id).toBe(99);
    }
  });

  it("does not deduplicate when tool_use_id is null", () => {
    const historyTool = makeToolEvent({ id: 1, phase: "pre", tool_use_id: null });
    const liveTool = makeToolEvent({ id: 2, phase: "post", tool_use_id: null });

    const { result, rerender } = renderHook(
      ({ live }: { live: typeof liveTool[] }) => useEventState(live),
      { initialProps: { live: [liveTool] } },
    );

    result.current.setHistoryEvents([historyTool]);
    rerender({ live: [liveTool] });

    const allEvents = result.current.allEvents;
    // Both events should remain since tool_use_id is null
    expect(allEvents).toHaveLength(2);
  });

  it("does not deduplicate when live event phase is not post", () => {
    const historyTool = makeToolEvent({ id: 1, phase: "pre", tool_use_id: "toolu_pre" });
    const liveTool = makeToolEvent({ id: 2, phase: "pre", tool_use_id: "toolu_pre" });

    const { result, rerender } = renderHook(
      ({ live }: { live: typeof liveTool[] }) => useEventState(live),
      { initialProps: { live: [liveTool] } },
    );

    result.current.setHistoryEvents([historyTool]);
    rerender({ live: [liveTool] });

    const allEvents = result.current.allEvents;
    // Both pre events remain — no dedup for pre/pre pairs
    const matching = allEvents.filter(
      e => e._kind === "tool" && e.data.tool_use_id === "toolu_pre",
    );
    expect(matching).toHaveLength(2);
  });
});
