import { describe, it, expect } from "vitest";
import { getToolCategory } from "@/lib/types";
import {
  extractReadFiles,
  extractReadPaths,
  extractEditSummary,
  extractBashCommands,
  groupEvents,
} from "@/lib/groupEvents";
import type { ToolCall, FeedEvent } from "@/lib/types";

/* ── Test Data Factory ── */

function makeToolCall(overrides?: Partial<ToolCall>): ToolCall {
  return {
    id: 1,
    run_id: "test-run",
    ts: new Date().toISOString(),
    phase: "pre",
    tool_name: "Bash",
    input_data: null,
    output_data: null,
    duration_ms: null,
    permitted: true,
    deny_reason: null,
    agent_role: "builder",
    tool_use_id: null,
    session_id: null,
    agent_id: null,
    ...overrides,
  };
}

function makeToolEvent(overrides?: Partial<ToolCall>): FeedEvent {
  return { _kind: "tool", data: makeToolCall(overrides) };
}

/* ── getToolCategory ── */

describe("getToolCategory", () => {
  it('maps "Bash" → "bash"', () => {
    expect(getToolCategory("Bash")).toBe("bash");
  });

  it('maps "Read" → "read"', () => {
    expect(getToolCategory("Read")).toBe("read");
  });

  it('maps "Write" → "write"', () => {
    expect(getToolCategory("Write")).toBe("write");
  });

  it('maps "Edit" → "edit"', () => {
    expect(getToolCategory("Edit")).toBe("edit");
  });

  it('maps "Glob" → "glob"', () => {
    expect(getToolCategory("Glob")).toBe("glob");
  });

  it('maps "Grep" → "grep"', () => {
    expect(getToolCategory("Grep")).toBe("grep");
  });

  it('maps "WebSearch" → "web_search"', () => {
    expect(getToolCategory("WebSearch")).toBe("web_search");
  });

  it('maps "WebFetch" → "web_fetch"', () => {
    expect(getToolCategory("WebFetch")).toBe("web_fetch");
  });

  it('maps "TodoWrite" → "todo"', () => {
    expect(getToolCategory("TodoWrite")).toBe("todo");
  });

  it('maps "Agent" → "agent"', () => {
    expect(getToolCategory("Agent")).toBe("agent");
  });

  it('maps a tool containing "browser_navigate" → "playwright_navigate"', () => {
    expect(getToolCategory("mcp_browser_navigate")).toBe("playwright_navigate");
  });

  it('maps a tool containing "browser_take_screenshot" → "playwright_screenshot"', () => {
    expect(getToolCategory("mcp_browser_take_screenshot")).toBe("playwright_screenshot");
  });

  it('maps unknown tool "CustomTool" → "default"', () => {
    expect(getToolCategory("CustomTool")).toBe("default");
  });

  it('is case-insensitive: "BASH" → "bash"', () => {
    expect(getToolCategory("BASH")).toBe("bash");
  });

  it('is case-insensitive: "bash" → "bash"', () => {
    expect(getToolCategory("bash")).toBe("bash");
  });
});

/* ── extractReadFiles ── */

describe("extractReadFiles", () => {
  it("returns [] for empty array", () => {
    expect(extractReadFiles([])).toEqual([]);
  });

  it("strips repo prefix and returns filename for /home/agentuser/repo path", () => {
    const tools = [makeToolCall({ input_data: { file_path: "/home/agentuser/repo/src/foo.ts" } })];
    expect(extractReadFiles(tools)).toEqual(["foo.ts"]);
  });

  it("strips /workspace prefix and returns filename", () => {
    const tools = [makeToolCall({ input_data: { file_path: "/workspace/lib/bar.py" } })];
    expect(extractReadFiles(tools)).toEqual(["bar.py"]);
  });

  it("returns filenames for two tools with different paths", () => {
    const tools = [
      makeToolCall({ input_data: { file_path: "/home/agentuser/repo/src/foo.ts" } }),
      makeToolCall({ input_data: { file_path: "/workspace/lib/bar.py" } }),
    ];
    expect(extractReadFiles(tools)).toEqual(["foo.ts", "bar.py"]);
  });
});

/* ── extractReadPaths ── */

describe("extractReadPaths", () => {
  it("strips /home/agentuser/repo prefix and returns relative path", () => {
    const tools = [makeToolCall({ input_data: { file_path: "/home/agentuser/repo/src/foo.ts" } })];
    expect(extractReadPaths(tools)).toEqual(["src/foo.ts"]);
  });

  it("strips /workspace prefix and returns relative path", () => {
    const tools = [makeToolCall({ input_data: { file_path: "/workspace/lib/bar.py" } })];
    expect(extractReadPaths(tools)).toEqual(["lib/bar.py"]);
  });

  it("returns empty string when input_data is null", () => {
    const tools = [makeToolCall({ input_data: null })];
    expect(extractReadPaths(tools)).toEqual([""]);
  });
});

/* ── extractEditSummary ── */

describe("extractEditSummary", () => {
  it("returns zeros when no structuredPatch", () => {
    const tools = [
      makeToolCall({
        input_data: { file_path: "/home/agentuser/repo/src/foo.ts" },
        output_data: {},
      }),
    ];
    const result = extractEditSummary(tools);
    expect(result).toHaveLength(1);
    expect(result[0]).toMatchObject({ added: 0, removed: 0, file: "foo.ts", path: "src/foo.ts" });
  });

  it("counts added and removed lines from a hunk", () => {
    const tools = [
      makeToolCall({
        input_data: { file_path: "/home/agentuser/repo/src/foo.ts" },
        output_data: {
          structuredPatch: [{ lines: ["+added line", "-removed line", "context"] }],
        },
      }),
    ];
    const result = extractEditSummary(tools);
    expect(result[0]).toMatchObject({ added: 1, removed: 1 });
  });

  it("excludes +++ and --- header lines from counts", () => {
    const tools = [
      makeToolCall({
        input_data: { file_path: "/home/agentuser/repo/src/foo.ts" },
        output_data: {
          structuredPatch: [{ lines: ["+++", "---", "+real add"] }],
        },
      }),
    ];
    const result = extractEditSummary(tools);
    expect(result[0]).toMatchObject({ added: 1, removed: 0 });
  });
});

/* ── extractBashCommands ── */

describe("extractBashCommands", () => {
  it("returns [] for empty array", () => {
    expect(extractBashCommands([])).toEqual([]);
  });

  it("uses command as cmd when no description, exitOk true with no stderr", () => {
    const tools = [
      makeToolCall({ input_data: { command: "ls -la", description: "" }, output_data: {} }),
    ];
    const result = extractBashCommands(tools);
    expect(result[0].cmd).toBe("ls -la");
    expect(result[0].exitOk).toBe(true);
  });

  it("uses description as cmd when description is present", () => {
    const tools = [
      makeToolCall({ input_data: { command: "ls -la", description: "List files" }, output_data: {} }),
    ];
    const result = extractBashCommands(tools);
    expect(result[0].cmd).toBe("List files");
  });

  it("truncates long command to 120 characters when no description", () => {
    const longCmd = "a".repeat(150);
    const tools = [makeToolCall({ input_data: { command: longCmd, description: "" }, output_data: {} })];
    const result = extractBashCommands(tools);
    expect(result[0].cmd).toBe("a".repeat(120));
  });

  it("sets exitOk false and prepends [stderr] when stderr is present", () => {
    const tools = [
      makeToolCall({
        input_data: { command: "bad-cmd", description: "" },
        output_data: { stderr: "error msg", stdout: "out" },
      }),
    ];
    const result = extractBashCommands(tools);
    expect(result[0].exitOk).toBe(false);
    expect(result[0].output).toMatch(/^\[stderr\]/);
  });
});

/* ── groupEvents smoke tests ── */

describe("groupEvents", () => {
  it("returns [] for empty input", () => {
    expect(groupEvents([])).toEqual([]);
  });

  it("returns length 1 with a valid type for a single tool event", () => {
    const events: FeedEvent[] = [makeToolEvent({ tool_name: "Bash" })];
    const result = groupEvents(events);
    expect(result).toHaveLength(1);
    expect(result[0]).toHaveProperty("type");
  });

  it("groups two consecutive read tools into a tool_group with category 'read'", () => {
    const ts = new Date().toISOString();
    const events: FeedEvent[] = [
      makeToolEvent({ tool_name: "Read", ts, id: 1 }),
      makeToolEvent({ tool_name: "Read", ts, id: 2 }),
    ];
    const result = groupEvents(events);
    expect(result).toHaveLength(1);
    const group = result[0];
    expect(group.type).toBe("tool_group");
    if (group.type === "tool_group") {
      expect(group.category).toBe("read");
      expect(group.tools).toHaveLength(2);
    }
  });

  it("does not throw on any valid input", () => {
    const events: FeedEvent[] = [
      makeToolEvent({ tool_name: "Bash" }),
      makeToolEvent({ tool_name: "Read" }),
      makeToolEvent({ tool_name: "Edit" }),
      { _kind: "llm_text", text: "hello", ts: new Date().toISOString() },
    ];
    expect(() => groupEvents(events)).not.toThrow();
  });
});
