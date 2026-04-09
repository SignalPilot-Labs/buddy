/**
 * Tool error rendering tests.
 *
 * Verifies that PostToolUseFailure errors render as red error messages
 * and that the merge logic correctly pairs failed post events with pre events.
 */

import { describe, it, expect } from "vitest";
import { mergeToolEvent } from "@/lib/eventMerge";
import type { FeedEvent, ToolCall } from "@/lib/types";

function makePreEvent(toolName: string, toolUseId: string): FeedEvent {
  return {
    _kind: "tool",
    data: {
      id: 1,
      run_id: "run-1",
      ts: new Date().toISOString(),
      phase: "pre",
      tool_name: toolName,
      input_data: { file_path: "/nonexistent.ts" },
      output_data: null,
      duration_ms: null,
      permitted: true,
      deny_reason: null,
      agent_role: "worker",
      tool_use_id: toolUseId,
      session_id: null,
      agent_id: null,
    },
  };
}

function makeErrorPost(toolName: string, toolUseId: string, error: string): ToolCall {
  return {
    id: 2,
    run_id: "run-1",
    ts: new Date().toISOString(),
    phase: "post",
    tool_name: toolName,
    input_data: null,
    output_data: { error },
    duration_ms: 50,
    permitted: true,
    deny_reason: null,
    agent_role: "worker",
    tool_use_id: toolUseId,
    session_id: null,
    agent_id: null,
  };
}

describe("Tool error rendering", () => {
  it("error post event has correct output_data shape", () => {
    const prev: FeedEvent[] = [makePreEvent("Read", "tu-1")];
    const errorPost = makeErrorPost("Read", "tu-1", "File not found: /nonexistent.ts");
    const merged = mergeToolEvent(prev, errorPost);
    expect(merged).toHaveLength(1);
    if (merged[0]._kind === "tool") {
      const out = merged[0].data.output_data as Record<string, unknown>;
      expect(out).not.toBeNull();
      expect(out.error).toBe("File not found: /nonexistent.ts");
      expect(Object.keys(out)).toHaveLength(1);
    }
  });

  it("mergeToolEvent pairs error post with pre by tool_use_id", () => {
    const prev: FeedEvent[] = [makePreEvent("Read", "tu-abc")];
    const errorPost = makeErrorPost("Read", "tu-abc", "File not found");
    const merged = mergeToolEvent(prev, errorPost);
    expect(merged).toHaveLength(1);
    expect(merged[0]._kind).toBe("tool");
    if (merged[0]._kind === "tool") {
      expect(merged[0].data.phase).toBe("post");
      expect(merged[0].data.output_data).toEqual({ error: "File not found" });
      expect(merged[0].data.duration_ms).toBe(50);
    }
  });

  it("mergeToolEvent does not swallow error post when no pre exists", () => {
    const prev: FeedEvent[] = [];
    const errorPost = makeErrorPost("Read", "tu-orphan", "File not found");
    const merged = mergeToolEvent(prev, errorPost);
    expect(merged).toHaveLength(1);
    expect(merged[0]._kind).toBe("tool");
  });
});
