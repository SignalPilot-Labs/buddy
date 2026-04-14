/**
 * Write tool rendering decision tests.
 *
 * Verifies that the rendering logic correctly distinguishes between:
 * - Edit tools with structuredPatch (show diff)
 * - Write tools with empty structuredPatch but content (show file preview)
 * - Write tools with no output at all
 *
 * Tests the actual data shapes returned by the Claude SDK, as observed
 * in the database (post phase: structuredPatch=[], content in output_data).
 */

import { describe, it, expect } from "vitest";
import type { ToolCall } from "@/lib/types";

function makeToolCall(overrides?: Partial<ToolCall>): ToolCall {
  return {
    id: 1,
    run_id: "test-run",
    ts: new Date().toISOString(),
    phase: "post",
    tool_name: "Write",
    input_data: null,
    output_data: null,
    duration_ms: 69,
    permitted: true,
    deny_reason: null,
    agent_role: "worker",
    tool_use_id: "tu_1",
    session_id: null,
    agent_id: null,
    ...overrides,
  };
}

/**
 * Replicates the rendering decision logic from StyledToolOutput.
 * Returns which renderer would be used for the given tool data.
 */
function resolveWriteRenderer(
  tool: ToolCall
): "diff" | "file_preview" | "json_fallback" | "none" {
  const patch = tool.output_data?.structuredPatch;
  const hasPatch = Array.isArray(patch) && (patch as unknown[]).length > 0;
  if (hasPatch) return "diff";

  const content = tool.output_data?.content;
  if (typeof content === "string" && content.length > 0) return "file_preview";

  if (tool.output_data) return "json_fallback";
  return "none";
}

describe("Write tool render decision", () => {
  it("new file with empty structuredPatch renders file preview, not diff", () => {
    // Actual shape from Claude SDK post-phase Write output
    const tool = makeToolCall({
      output_data: {
        type: "create",
        content: "# Report\n\nSome content here",
        filePath: "/tmp/round-1/architect.md",
        originalFile: null,
        structuredPatch: [],
      },
    });
    expect(resolveWriteRenderer(tool)).toBe("file_preview");
  });

  it("edit with non-empty structuredPatch renders diff", () => {
    const tool = makeToolCall({
      tool_name: "Edit",
      output_data: {
        structuredPatch: [
          {
            oldStart: 1,
            newStart: 1,
            lines: ["-old line", "+new line"],
          },
        ],
      },
    });
    expect(resolveWriteRenderer(tool)).toBe("diff");
  });

  it("write with null output renders none", () => {
    const tool = makeToolCall({ output_data: null });
    expect(resolveWriteRenderer(tool)).toBe("none");
  });

  it("write with empty object output renders json fallback", () => {
    const tool = makeToolCall({ output_data: {} });
    expect(resolveWriteRenderer(tool)).toBe("json_fallback");
  });

  it("write with content but no structuredPatch key renders file preview", () => {
    const tool = makeToolCall({
      output_data: {
        type: "create",
        content: "hello world",
        filePath: "/tmp/test.txt",
      },
    });
    expect(resolveWriteRenderer(tool)).toBe("file_preview");
  });

  it("structuredPatch=null with content renders file preview", () => {
    const tool = makeToolCall({
      output_data: {
        content: "file content",
        structuredPatch: null,
      },
    });
    expect(resolveWriteRenderer(tool)).toBe("file_preview");
  });

  it("structuredPatch=undefined with content renders file preview", () => {
    const tool = makeToolCall({
      output_data: {
        content: "file content",
      },
    });
    expect(resolveWriteRenderer(tool)).toBe("file_preview");
  });
});

describe("Edit group card patch detection", () => {
  /**
   * Replicates the logic in EditGroupCard for deciding whether
   * to show diff or file preview per tool.
   */
  function resolveEditGroupItem(
    tool: ToolCall
  ): "diff" | "file_preview" | "none" {
    const patch = tool.output_data?.structuredPatch;
    const hasPatch = Array.isArray(patch) && (patch as unknown[]).length > 0;
    const content =
      tool.output_data?.content ?? tool.input_data?.content;
    const hasContent = typeof content === "string" && content.length > 0;
    if (hasPatch) return "diff";
    if (hasContent) return "file_preview";
    return "none";
  }

  it("empty structuredPatch with output content shows file preview", () => {
    const tool = makeToolCall({
      output_data: {
        type: "create",
        content: "new file",
        structuredPatch: [],
      },
    });
    expect(resolveEditGroupItem(tool)).toBe("file_preview");
  });

  it("empty structuredPatch with input content shows file preview", () => {
    // Pre-phase data pattern where content is in input_data
    const tool = makeToolCall({
      input_data: { content: "new file", file_path: "/tmp/test.md" },
      output_data: { structuredPatch: [] },
    });
    expect(resolveEditGroupItem(tool)).toBe("file_preview");
  });

  it("non-empty structuredPatch shows diff", () => {
    const tool = makeToolCall({
      output_data: {
        structuredPatch: [{ lines: ["+added"] }],
      },
    });
    expect(resolveEditGroupItem(tool)).toBe("diff");
  });

  it("no content and no patch shows none", () => {
    const tool = makeToolCall({
      output_data: { structuredPatch: [] },
    });
    expect(resolveEditGroupItem(tool)).toBe("none");
  });
});
