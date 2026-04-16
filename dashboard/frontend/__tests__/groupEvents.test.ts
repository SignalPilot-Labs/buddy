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

/* ── milestone detail rendering ── */

describe("milestone detail text", () => {
  it("end_session_denied renders as Session End Denied with remaining time", () => {
    const events: FeedEvent[] = [
      {
        _kind: "audit",
        data: {
          id: 1,
          run_id: "r",
          event_type: "end_session_denied",
          details: { remaining_minutes: 25.3 },
          ts: new Date().toISOString(),
        },
      },
    ];
    const result = groupEvents(events);
    expect(result).toHaveLength(1);
    if (result[0].type === "milestone") {
      expect(result[0].label).toBe("End Run Denied");
      expect(result[0].detail).toBe("25.3m remaining");
    }
  });

  it("end_session_denied shows ? when remaining_minutes missing", () => {
    const events: FeedEvent[] = [
      {
        _kind: "audit",
        data: {
          id: 2,
          run_id: "r",
          event_type: "end_session_denied",
          details: {},
          ts: new Date().toISOString(),
        },
      },
    ];
    const result = groupEvents(events);
    expect(result).toHaveLength(1);
    if (result[0].type === "milestone") {
      expect(result[0].detail).toBe("?m remaining");
    }
  });
});

describe("run_started milestone detail", () => {
  it("shows branch name when present", () => {
    const events: FeedEvent[] = [
      {
        _kind: "audit",
        data: {
          id: 1,
          run_id: "r",
          event_type: "run_started",
          details: { model: "opus", branch: "autofyn/fix-the-bug" },
          ts: new Date().toISOString(),
        },
      },
    ];
    const result = groupEvents(events);
    expect(result).toHaveLength(1);
    expect(result[0].type).toBe("milestone");
    if (result[0].type === "milestone") {
      expect(result[0].detail).toBe("opus · autofyn/fix-the-bug");
    }
  });

  it("does not show null branch name", () => {
    const events: FeedEvent[] = [
      {
        _kind: "audit",
        data: {
          id: 2,
          run_id: "r",
          event_type: "run_started",
          details: { model: "opus", branch: null },
          ts: new Date().toISOString(),
        },
      },
    ];
    const result = groupEvents(events);
    expect(result).toHaveLength(1);
    expect(result[0].type).toBe("milestone");
    if (result[0].type === "milestone") {
      expect(result[0].detail).toBe("opus");
    }
  });

  it("handles missing branch gracefully", () => {
    const events: FeedEvent[] = [
      {
        _kind: "audit",
        data: {
          id: 3,
          run_id: "r",
          event_type: "run_started",
          details: { model: "sonnet" },
          ts: new Date().toISOString(),
        },
      },
    ];
    const result = groupEvents(events);
    expect(result).toHaveLength(1);
    expect(result[0].type).toBe("milestone");
    if (result[0].type === "milestone") {
      expect(result[0].detail).toBe("sonnet");
    }
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

  // Regression: `end_round` and `end_session` both live under the
  it("renders end_round as an End Round milestone with summary", () => {
    const events: FeedEvent[] = [
      makeToolEvent({
        tool_name: "mcp__session_gate__end_round",
        id: 1,
        input_data: { summary: "Fix event batching" },
      }),
    ];
    const result = groupEvents(events);
    expect(result).toHaveLength(1);
    expect(result[0].type).toBe("milestone");
    if (result[0].type === "milestone") {
      expect(result[0].label).toBe("End Round Requested");
      expect(result[0].detail).toBe("Fix event batching");
      expect(result[0].color).toBe("#00ff88");
    }
  });

  it("renders end_session as an End Session milestone", () => {
    const events: FeedEvent[] = [
      makeToolEvent({ tool_name: "mcp__session_gate__end_session", id: 1 }),
    ];
    const result = groupEvents(events);
    expect(result).toHaveLength(1);
    expect(result[0].type).toBe("milestone");
    if (result[0].type === "milestone") {
      expect(result[0].label).toBe("End Run Requested");
    }
  });

  it("filters ToolSearch select: queries (SDK plumbing) but keeps keyword searches", () => {
    const events: FeedEvent[] = [
      makeToolEvent({ tool_name: "ToolSearch", id: 1, input_data: { query: "select:TodoWrite" } }),
      makeToolEvent({ tool_name: "ToolSearch", id: 2, input_data: { query: "notebook jupyter" } }),
    ];
    const result = groupEvents(events);
    // select: query filtered, keyword query kept
    expect(result).toHaveLength(1);
    expect(result[0].type).toBe("single_tool");
    if (result[0].type === "single_tool") {
      expect(result[0].tool.id).toBe(2);
    }
  });
});

function makeAuditEvent(id: number, eventType: string, details: Record<string, unknown>, ts: string): FeedEvent {
  return {
    _kind: "audit",
    data: { id, run_id: "r", ts, event_type: eventType, details },
  };
}

/* ── inject vs submit prompt distinction ── */

describe("prompt_injected vs prompt_submitted", () => {
  it("marks prompt_injected as injected=true on the user_prompt event", () => {
    const ts = new Date().toISOString();
    const events: FeedEvent[] = [
      {
        _kind: "audit",
        data: { id: 1, run_id: "r", ts, event_type: "prompt_injected", details: { prompt: "use ramanujan series" } },
      },
    ];
    const result = groupEvents(events);
    expect(result).toHaveLength(1);
    expect(result[0].type).toBe("user_prompt");
    if (result[0].type === "user_prompt") {
      expect(result[0].injected).toBe(true);
      expect(result[0].prompt).toBe("use ramanujan series");
    }
  });

  it("does NOT mark prompt_submitted as injected", () => {
    const ts = new Date().toISOString();
    const events: FeedEvent[] = [
      {
        _kind: "audit",
        data: { id: 2, run_id: "r", ts, event_type: "prompt_submitted", details: { prompt: "build a calculator" } },
      },
    ];
    const result = groupEvents(events);
    expect(result).toHaveLength(1);
    expect(result[0].type).toBe("user_prompt");
    if (result[0].type === "user_prompt") {
      expect(result[0].injected).toBeFalsy();
    }
  });

  it("inject mid-subagent does not cause agent card to lose its context", () => {
    // Regression: injecting a message while a subagent is running caused
    // the FE to treat the inject as an interruption, which set runActive=false
    // for the in-flight agent card, making it render as "failed".
    const t0 = new Date("2026-04-10T13:18:45Z").toISOString();
    const t1 = new Date("2026-04-10T13:18:50Z").toISOString();
    const t2 = new Date("2026-04-10T13:18:55Z").toISOString();

    const events: FeedEvent[] = [
      // Subagent starts
      makeToolEvent({
        id: 1, tool_name: "Agent", ts: t0, tool_use_id: "toolu_arch",
        input_data: { description: "Design pi digits script", subagent_type: "architect", prompt: "design" },
      }),
      makeAuditEvent(10, "subagent_start", {
        agent_id: "aArch", agent_type: "architect", parent_tool_use_id: "toolu_arch",
      }, t0),
      // Subagent does some work
      makeToolEvent({ id: 2, tool_name: "Bash", ts: t1, agent_id: "aArch" }),
      makeToolEvent({ id: 3, tool_name: "Read", ts: t1, agent_id: "aArch" }),
      // User injects a message WHILE subagent is running
      {
        _kind: "audit",
        data: { id: 11, run_id: "r", ts: t2, event_type: "prompt_injected", details: { prompt: "use ramanujan series" } },
      },
    ];

    const result = groupEvents(events);

    // The agent_run card should still exist with its child tools
    const agentRun = result.find((g) => g.type === "agent_run");
    expect(agentRun).toBeDefined();
    if (agentRun?.type === "agent_run") {
      expect(agentRun.childTools).toHaveLength(2);
      expect(agentRun.agentType).toBe("architect");
    }

    // The inject should be a user_prompt with injected=true
    const userPrompt = result.find((g) => g.type === "user_prompt");
    expect(userPrompt).toBeDefined();
    if (userPrompt?.type === "user_prompt") {
      expect(userPrompt.injected).toBe(true);
    }
  });
});

/* ── subagent attribution via audit-event link ── */

describe("groupEvents subagent attribution", () => {
  it("attributes child tools to the correct Agent card via parent_tool_use_id", () => {
    // Builder call comes first and has 2 child tools; reviewer call comes
    // later with 1 child tool. The old temporal-matching code would
    // mis-pair these when the timestamps overlapped; this test pins the
    // new deterministic audit-event path.
    const t0 = new Date("2026-04-10T13:18:45Z").toISOString();
    const t1 = new Date("2026-04-10T13:18:50Z").toISOString();
    const t2 = new Date("2026-04-10T13:18:55Z").toISOString();
    const t3 = new Date("2026-04-10T13:21:33Z").toISOString();
    const t4 = new Date("2026-04-10T13:21:40Z").toISOString();

    const events: FeedEvent[] = [
      // Orchestrator invokes builder
      makeToolEvent({
        id: 1, tool_name: "Agent", ts: t0, tool_use_id: "toolu_builder",
        input_data: { description: "Round 3 frontend build", subagent_type: "frontend-builder", prompt: "build" },
      }),
      makeAuditEvent(10, "subagent_start", {
        agent_id: "aBuilder", agent_type: "frontend-builder", parent_tool_use_id: "toolu_builder",
      }, t0),
      // Builder's 2 child tools
      makeToolEvent({ id: 2, tool_name: "Read", ts: t1, agent_id: "aBuilder" }),
      makeToolEvent({ id: 3, tool_name: "Edit", ts: t2, agent_id: "aBuilder" }),
      // Orchestrator invokes reviewer AFTER builder finishes
      makeToolEvent({
        id: 4, tool_name: "Agent", ts: t3, tool_use_id: "toolu_reviewer",
        input_data: { description: "Round 3 code review", subagent_type: "reviewer", prompt: "review" },
      }),
      makeAuditEvent(11, "subagent_start", {
        agent_id: "aReviewer", agent_type: "reviewer", parent_tool_use_id: "toolu_reviewer",
      }, t3),
      // Reviewer's 1 child tool
      makeToolEvent({ id: 5, tool_name: "Grep", ts: t4, agent_id: "aReviewer" }),
    ];

    const result = groupEvents(events);
    const agentRuns = result.filter((g) => g.type === "agent_run");
    expect(agentRuns).toHaveLength(2);

    const [builder, reviewer] = agentRuns;
    if (builder.type !== "agent_run" || reviewer.type !== "agent_run") throw new Error("type");

    expect(builder.agentType).toBe("frontend-builder");
    expect(builder.childTools).toHaveLength(2);
    expect(builder.childTools.map((t) => t.tool_name)).toEqual(["Read", "Edit"]);

    expect(reviewer.agentType).toBe("reviewer");
    expect(reviewer.childTools).toHaveLength(1);
    expect(reviewer.childTools[0].tool_name).toBe("Grep");
  });

  it("renders final_text from subagent_complete audit keyed by parent_tool_use_id", () => {
    const ts = new Date().toISOString();
    const events: FeedEvent[] = [
      makeToolEvent({
        id: 1, tool_name: "Agent", ts, tool_use_id: "toolu_x",
        input_data: { description: "Task X", subagent_type: "general-purpose", prompt: "do x" },
      }),
      makeAuditEvent(20, "subagent_start", {
        agent_id: "aX", agent_type: "general-purpose", parent_tool_use_id: "toolu_x",
      }, ts),
      makeAuditEvent(21, "subagent_complete", {
        agent_id: "aX", parent_tool_use_id: "toolu_x", final_text: "done.",
      }, ts),
    ];
    const result = groupEvents(events);
    const agentRun = result.find((g) => g.type === "agent_run");
    expect(agentRun).toBeDefined();
    if (agentRun?.type === "agent_run") {
      expect(agentRun.finalText).toBe("done.");
    }
  });

  it("does NOT attribute child tools to an Agent call whose subagent_start audit is missing", () => {
    // Without a subagent_start audit event, there is no authoritative link
    // from agent_id to parent_tool_use_id. The Agent card should render
    // with zero children rather than guessing via timestamps.
    const ts = new Date().toISOString();
    const events: FeedEvent[] = [
      makeToolEvent({
        id: 1, tool_name: "Agent", ts, tool_use_id: "toolu_y",
        input_data: { description: "Task Y", subagent_type: "general-purpose", prompt: "do y" },
      }),
      // Subagent tools with an agent_id, but no subagent_start audit.
      makeToolEvent({ id: 2, tool_name: "Read", ts, agent_id: "aOrphan" }),
    ];
    const result = groupEvents(events);
    const agentRun = result.find((g) => g.type === "agent_run");
    expect(agentRun).toBeDefined();
    if (agentRun?.type === "agent_run") {
      expect(agentRun.childTools).toHaveLength(0);
    }
  });

  it("skips orphan Agent post events (phantom GENERAL card)", () => {
    // A post-phase Agent row with null input_data is an orphan from a
    // merge miss or PostToolUseFailure — not a real Task invocation.
    // It must not render as a second phantom card.
    const ts = new Date().toISOString();
    const events: FeedEvent[] = [
      makeToolEvent({
        id: 1, tool_name: "Agent", ts, tool_use_id: "toolu_legit", phase: "post",
        input_data: { description: "Real Task", subagent_type: "reviewer", prompt: "p" },
      }),
      makeToolEvent({
        id: 2, tool_name: "Agent", ts, tool_use_id: "toolu_orphan", phase: "post",
        input_data: null,
      }),
    ];
    const result = groupEvents(events);
    const agentRuns = result.filter((g) => g.type === "agent_run");
    expect(agentRuns).toHaveLength(1);
    if (agentRuns[0].type === "agent_run") {
      expect(agentRuns[0].tool.tool_use_id).toBe("toolu_legit");
    }
  });
});
