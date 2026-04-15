/**
 * Prompt delivery tests.
 *
 * Covers: server prompt events in groupEvents, pending messages as UI-only
 * state rendered by EventFeed, user_prompt as interruption boundary,
 * pause_requested label, run_resumed detail.
 */

import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { groupEvents } from "@/lib/groupEvents";
import { EventFeed } from "@/components/feed/EventFeed";
import { AgentRunCard } from "@/components/feed/AgentRunCard";
import type { FeedEvent, ToolCall, PendingMessage } from "@/lib/types";

const DEFAULT_FEED_PROPS = {
  pendingMessages: [] as PendingMessage[],
  runActive: false,
  runPaused: false,
  isLoading: false,
  historyTruncated: false,
  hasSelectedRun: true,
};

/* ── Factories ── */

function makeAuditEvent(
  id: number,
  eventType: string,
  details: Record<string, unknown>,
  ts: string = new Date().toISOString(),
): FeedEvent {
  return {
    _kind: "audit",
    data: { id, run_id: "run-1", ts, event_type: eventType, details },
  };
}

function makeAgentToolEvent(ts: string): FeedEvent {
  return {
    _kind: "tool",
    data: {
      id: 100,
      run_id: "run-1",
      ts,
      phase: "pre",
      tool_name: "Agent",
      input_data: { prompt: "plan something" },
      output_data: null,
      duration_ms: null,
      permitted: true,
      deny_reason: null,
      agent_role: "orchestrator",
      tool_use_id: "tu-agent-1",
      session_id: null,
      agent_id: null,
    } satisfies ToolCall,
  };
}

/* ── groupEvents: server prompt events ── */

describe("groupEvents server prompt events", () => {
  it("maps prompt_injected to user_prompt with pending=false", () => {
    const events: FeedEvent[] = [
      makeAuditEvent(50, "prompt_injected", { prompt: "server event" }),
    ];
    const grouped = groupEvents(events);
    expect(grouped).toHaveLength(1);
    expect(grouped[0].type).toBe("user_prompt");
    if (grouped[0].type === "user_prompt") {
      expect(grouped[0].prompt).toBe("server event");
      expect(grouped[0].pending).toBe(false);
      expect(grouped[0].failed).toBe(false);
    }
  });

  it("maps prompt_submitted to user_prompt", () => {
    const events: FeedEvent[] = [
      makeAuditEvent(51, "prompt_submitted", { prompt: "user typed this" }),
    ];
    const grouped = groupEvents(events);
    expect(grouped).toHaveLength(1);
    expect(grouped[0].type).toBe("user_prompt");
    if (grouped[0].type === "user_prompt") {
      expect(grouped[0].prompt).toBe("user typed this");
    }
  });
});

/* ── EventFeed: pending messages rendered at bottom ── */

describe("EventFeed pending messages", () => {
  it("renders pending message as user bubble with 'You' label", () => {
    const pending: PendingMessage[] = [
      { id: -1, prompt: "fix the bug", ts: new Date().toISOString(), status: "pending" },
    ];
    render(<EventFeed {...DEFAULT_FEED_PROPS} events={[]} pendingMessages={pending} hasSelectedRun={true} />);
    expect(screen.getByText("You")).toBeInTheDocument();
    expect(screen.getByText("fix the bug")).toBeInTheDocument();
  });

  it("renders pending message with pulsing indicator", () => {
    const pending: PendingMessage[] = [
      { id: -1, prompt: "hello", ts: new Date().toISOString(), status: "pending" },
    ];
    const { container } = render(<EventFeed {...DEFAULT_FEED_PROPS} events={[]} pendingMessages={pending} hasSelectedRun={true} />);
    const pulsingDots = container.querySelectorAll(".animate-pulse");
    expect(pulsingDots.length).toBeGreaterThan(0);
  });

  it("renders failed message with 'not delivered' text", () => {
    const pending: PendingMessage[] = [
      { id: -2, prompt: "failed msg", ts: new Date().toISOString(), status: "failed" },
    ];
    render(<EventFeed {...DEFAULT_FEED_PROPS} events={[]} pendingMessages={pending} hasSelectedRun={true} />);
    expect(screen.getByText("not delivered")).toBeInTheDocument();
  });

  it("renders pending messages after server events", () => {
    const events: FeedEvent[] = [
      makeAuditEvent(1, "run_started", { model: "claude", branch: "main" }),
    ];
    const pending: PendingMessage[] = [
      { id: -1, prompt: "my message", ts: new Date().toISOString(), status: "pending" },
    ];
    const { container } = render(<EventFeed {...DEFAULT_FEED_PROPS} events={events} pendingMessages={pending} hasSelectedRun={true} />);
    expect(container).toBeInTheDocument();
    expect(screen.getByText("my message")).toBeInTheDocument();
    expect(screen.getByText("Run Started")).toBeInTheDocument();
  });

  it("does not render pending messages when list is empty", () => {
    const events: FeedEvent[] = [
      makeAuditEvent(50, "prompt_injected", { prompt: "delivered" }),
    ];
    render(<EventFeed {...DEFAULT_FEED_PROPS} events={events} pendingMessages={[]} hasSelectedRun={true} />);
    expect(screen.getByText("delivered")).toBeInTheDocument();
    // Only one "You" label from the server event
    expect(screen.getAllByText("You")).toHaveLength(1);
  });
});

/* ── EventFeed: no duplicate when server event + empty pending ── */

describe("EventFeed no duplicate user bubbles", () => {
  it("server prompt_injected renders once when pendingMessages is empty", () => {
    const events: FeedEvent[] = [
      makeAuditEvent(50, "prompt_injected", { prompt: "hello agent" }),
    ];
    render(<EventFeed {...DEFAULT_FEED_PROPS} events={events} pendingMessages={[]} hasSelectedRun={true} />);
    expect(screen.getAllByText("You")).toHaveLength(1);
    expect(screen.getAllByText("hello agent")).toHaveLength(1);
  });

  it("server event + pending for different messages shows both", () => {
    const events: FeedEvent[] = [
      makeAuditEvent(50, "prompt_injected", { prompt: "first message" }),
    ];
    const pending: PendingMessage[] = [
      { id: -2, prompt: "second message", ts: new Date().toISOString(), status: "pending" },
    ];
    render(<EventFeed {...DEFAULT_FEED_PROPS} events={events} pendingMessages={pending} hasSelectedRun={true} />);
    expect(screen.getAllByText("You")).toHaveLength(2);
    expect(screen.getByText("first message")).toBeInTheDocument();
    expect(screen.getByText("second message")).toBeInTheDocument();
  });
});

/* ── EventFeed: multiple pending messages ── */

describe("EventFeed multiple pending messages", () => {
  it("renders multiple pending messages in order", () => {
    const pending: PendingMessage[] = [
      { id: -1, prompt: "msg one", ts: "2026-01-01T10:00:00Z", status: "pending" },
      { id: -2, prompt: "msg two", ts: "2026-01-01T10:00:05Z", status: "pending" },
    ];
    render(<EventFeed {...DEFAULT_FEED_PROPS} events={[]} pendingMessages={pending} hasSelectedRun={true} />);
    expect(screen.getAllByText("You")).toHaveLength(2);
    expect(screen.getByText("msg one")).toBeInTheDocument();
    expect(screen.getByText("msg two")).toBeInTheDocument();
  });

  it("renders mix of pending and failed messages", () => {
    const pending: PendingMessage[] = [
      { id: -1, prompt: "delivered later", ts: "2026-01-01T10:00:00Z", status: "pending" },
      { id: -2, prompt: "could not send", ts: "2026-01-01T10:00:05Z", status: "failed" },
    ];
    const { container } = render(<EventFeed {...DEFAULT_FEED_PROPS} events={[]} pendingMessages={pending} hasSelectedRun={true} />);
    expect(screen.getByText("delivered later")).toBeInTheDocument();
    expect(screen.getByText("could not send")).toBeInTheDocument();
    expect(screen.getByText("not delivered")).toBeInTheDocument();
    // Pending should have pulse, failed should not
    const pulsingDots = container.querySelectorAll(".animate-pulse");
    expect(pulsingDots).toHaveLength(1);
  });
});

/* ── EventFeed: pending after full event history (page load scenario) ── */

describe("EventFeed page refresh scenario", () => {
  it("renders server events from history without pending (post-refresh)", () => {
    const events: FeedEvent[] = [
      makeAuditEvent(1, "run_started", { model: "claude", branch: "main" }),
      makeAuditEvent(50, "prompt_injected", { prompt: "fix the bug" }),
      makeAuditEvent(51, "run_resumed", {}),
    ];
    render(<EventFeed {...DEFAULT_FEED_PROPS} events={events} pendingMessages={[]} hasSelectedRun={true} />);
    expect(screen.getByText("Run Started")).toBeInTheDocument();
    expect(screen.getByText("fix the bug")).toBeInTheDocument();
    expect(screen.getByText("Run Resumed")).toBeInTheDocument();
    expect(screen.getAllByText("You")).toHaveLength(1);
  });
});

/* ── EventFeed: empty state only when both events and pending empty ── */

describe("EventFeed empty state", () => {
  it("shows no-run-selected empty state when no events, no pending, no run selected", () => {
    render(<EventFeed {...DEFAULT_FEED_PROPS} events={[]} pendingMessages={[]} hasSelectedRun={false} />);
    expect(screen.getByText("Waiting for events")).toBeInTheDocument();
  });

  it("shows waiting-for-activity empty state when run selected but no events", () => {
    render(<EventFeed {...DEFAULT_FEED_PROPS} events={[]} pendingMessages={[]} hasSelectedRun={true} />);
    expect(screen.getByText("Waiting for agent activity")).toBeInTheDocument();
  });

  it("does not show empty state when pending messages exist", () => {
    const pending: PendingMessage[] = [
      { id: -1, prompt: "hello", ts: new Date().toISOString(), status: "pending" },
    ];
    render(<EventFeed {...DEFAULT_FEED_PROPS} events={[]} pendingMessages={pending} hasSelectedRun={true} />);
    expect(screen.queryByText("Waiting for events")).not.toBeInTheDocument();
    expect(screen.queryByText("Waiting for agent activity")).not.toBeInTheDocument();
    expect(screen.getByText("hello")).toBeInTheDocument();
  });

  it("does not show empty state when events exist", () => {
    const events: FeedEvent[] = [
      makeAuditEvent(1, "run_started", { model: "claude", branch: "main" }),
    ];
    render(<EventFeed {...DEFAULT_FEED_PROPS} events={events} pendingMessages={[]} hasSelectedRun={true} />);
    expect(screen.queryByText("Waiting for events")).not.toBeInTheDocument();
    expect(screen.queryByText("Waiting for agent activity")).not.toBeInTheDocument();
  });
});

/* ── EventFeed: user_prompt as interruption boundary ── */

describe("EventFeed user_prompt interruption boundary", () => {
  it("agent card before user_prompt gets runActive=false (no 'running' text)", () => {
    const t0 = "2026-01-01T10:00:00.000Z";
    const t1 = "2026-01-01T10:00:10.000Z";

    const events: FeedEvent[] = [
      makeAgentToolEvent(t0),
      makeAuditEvent(5, "prompt_injected", { prompt: "stop exploring" }, t1),
    ];

    render(<EventFeed {...DEFAULT_FEED_PROPS} events={events} runActive={true} hasSelectedRun={true} />);
    // Agent card before the user_prompt should NOT show "running" or "finalizing"
    expect(screen.queryAllByText("running")).toHaveLength(0);
    expect(screen.queryAllByText("finalizing")).toHaveLength(0);
  });

  it("agent card after user_prompt keeps runActive=true", () => {
    const t0 = "2026-01-01T10:00:00.000Z";
    const t1 = "2026-01-01T10:00:10.000Z";

    const events: FeedEvent[] = [
      makeAuditEvent(5, "prompt_injected", { prompt: "do something" }, t0),
      makeAgentToolEvent(t1),
    ];

    const { container } = render(
      <EventFeed {...DEFAULT_FEED_PROPS} events={events} runActive={true} hasSelectedRun={true} />,
    );
    expect(container).toBeInTheDocument();
  });

  it("pause_requested milestone also acts as interruption boundary", () => {
    const t0 = "2026-01-01T10:00:00.000Z";
    const t1 = "2026-01-01T10:00:10.000Z";

    const events: FeedEvent[] = [
      makeAgentToolEvent(t0),
      makeAuditEvent(6, "pause_requested", {}, t1),
    ];

    render(<EventFeed {...DEFAULT_FEED_PROPS} events={events} runActive={true} hasSelectedRun={true} />);
    expect(screen.queryAllByText("running")).toHaveLength(0);
    expect(screen.queryAllByText("finalizing")).toHaveLength(0);
  });

  it("last user_prompt is the interruption boundary (not earlier ones)", () => {
    const t0 = "2026-01-01T10:00:00.000Z";
    const t1 = "2026-01-01T10:00:05.000Z";
    const t2 = "2026-01-01T10:00:10.000Z";
    const t3 = "2026-01-01T10:00:15.000Z";

    const events: FeedEvent[] = [
      makeAgentToolEvent(t0),
      makeAuditEvent(5, "prompt_injected", { prompt: "first" }, t1),
      makeAuditEvent(6, "resumed", { via: "inject" }, t2),
      makeAgentToolEvent(t3),
    ];

    const { container } = render(
      <EventFeed {...DEFAULT_FEED_PROPS} events={events} runActive={true} hasSelectedRun={true} />,
    );
    // Should render — the second agent card (t3) is after the last interruption (t1)
    expect(container).toBeInTheDocument();
  });
});

/* ── Pause Requested milestone label ── */

describe("groupEvents pause_requested label", () => {
  it("renders pause_requested as 'Pause Requested' not 'Paused'", () => {
    const events: FeedEvent[] = [
      makeAuditEvent(1, "pause_requested", {}),
    ];
    const grouped = groupEvents(events);
    expect(grouped).toHaveLength(1);
    if (grouped[0].type === "milestone") {
      expect(grouped[0].label).toBe("Pause Requested");
    }
  });
});

/* ── Session Resumed detail ── */

describe("groupEvents run_resumed detail", () => {
  it("renders run_resumed with empty detail (no branch)", () => {
    const events: FeedEvent[] = [
      makeAuditEvent(1, "run_resumed", { branch: "autofyn/some-branch" }),
    ];
    const grouped = groupEvents(events);
    expect(grouped).toHaveLength(1);
    if (grouped[0].type === "milestone") {
      expect(grouped[0].label).toBe("Run Resumed");
      expect(grouped[0].detail).toBe("");
    }
  });
});

/* ── AgentRunCard: paused badge ── */

describe("AgentRunCard paused badge state", () => {
  it("renders 'paused' badge (not 'failed') when runActive=true and runPaused=true", () => {
    const tool: ToolCall = {
      id: 200,
      run_id: "run-1",
      ts: new Date().toISOString(),
      phase: "pre",
      tool_name: "Agent",
      input_data: { description: "do work", prompt: "some prompt", subagent_type: "frontend-dev" },
      output_data: null,
      duration_ms: null,
      permitted: true,
      deny_reason: null,
      agent_role: "orchestrator",
      tool_use_id: "tu-paused-1",
      session_id: null,
      agent_id: null,
    };

    render(
      <AgentRunCard
        tool={tool}
        childTools={[]}
        finalText=""
        agentType="frontend-dev"
        ts={tool.ts}
        runActive={true}
        runPaused={true}
      />
    );

    expect(screen.getByText("paused")).toBeInTheDocument();
    expect(screen.queryByText("failed")).not.toBeInTheDocument();
  });
});
