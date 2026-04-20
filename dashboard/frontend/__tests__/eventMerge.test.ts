import { describe, it, expect } from "vitest";
import { mergeToolEvent } from "@/lib/eventMerge";
import type { FeedEvent } from "@/lib/types";
import { makeToolCall, makeToolEvent } from "./testFactories";

describe("mergeToolEvent", () => {
  it("merges a post event into its matching pre event by tool_use_id", () => {
    const pre = makeToolEvent({
      id: 1,
      tool_use_id: "toolu_abc",
      phase: "pre",
      tool_name: "Bash",
      output_data: null,
    });
    const postData = makeToolCall({
      id: 2,
      tool_use_id: "toolu_abc",
      phase: "post",
      tool_name: "Bash",
      output_data: { stdout: "hello" },
      duration_ms: 123,
    });

    const result = mergeToolEvent([pre], postData);

    expect(result).toHaveLength(1);
    const merged = result[0];
    expect(merged._kind).toBe("tool");
    if (merged._kind === "tool") {
      expect(merged.data.phase).toBe("post");
      expect(merged.data.output_data).toEqual({ stdout: "hello" });
      expect(merged.data.duration_ms).toBe(123);
    }
  });

  it("appends a post event without a matching pre as a standalone entry", () => {
    const existing: FeedEvent[] = [
      makeToolEvent({ id: 1, tool_use_id: "toolu_other", phase: "pre" }),
    ];
    const postData = makeToolCall({
      id: 2,
      tool_use_id: "toolu_nomatch",
      phase: "post",
      output_data: { result: "ok" },
    });

    const result = mergeToolEvent(existing, postData);

    expect(result).toHaveLength(2);
    const appended = result[1];
    expect(appended._kind).toBe("tool");
    if (appended._kind === "tool") {
      expect(appended.data.tool_use_id).toBe("toolu_nomatch");
      expect(appended.data.phase).toBe("post");
    }
  });

  it("always appends a pre event (no dedup logic in mergeToolEvent)", () => {
    const existing: FeedEvent[] = [
      makeToolEvent({ id: 1, tool_use_id: "toolu_x", phase: "pre" }),
    ];
    const newPre = makeToolCall({
      id: 2,
      tool_use_id: "toolu_y",
      phase: "pre",
    });

    const result = mergeToolEvent(existing, newPre);

    expect(result).toHaveLength(2);
    const appended = result[1];
    expect(appended._kind).toBe("tool");
    if (appended._kind === "tool") {
      expect(appended.data.tool_use_id).toBe("toolu_y");
      expect(appended.data.phase).toBe("pre");
    }
  });
});
