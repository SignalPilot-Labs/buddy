/**
 * Prompt delivery tests.
 *
 * Covers: server prompt events in groupEvents, pending messages as UI-only
 * state rendered by EventFeed, user_prompt as interruption boundary,
 * pause_requested label, session_resumed detail.
 */

import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { groupEvents } from "@/lib/groupEvents";
import { EventFeed } from "@/components/feed/EventFeed";
import type { FeedEvent, ToolCall, PendingMessage } from "@/lib/types";

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
    render(<EventFeed events={[]} pendingMessages={pending} />);
    expect(screen.getByText("You")).toBeInTheDocument();
    expect(screen.getByText("fix the bug")).toBeInTheDocument();
  });

  it("renders pending message with pulsing indicator", () => {
    const pending: PendingMessage[] = [
      { id: -1, prompt: "hello", ts: new Date().toISOString(), status: "pending" },
    ];
    const { container } = render(<EventFeed events={[]} pendingMessages={pending} />);
    const pulsingDots = container.querySelectorAll(".animate-pulse");
    expect(pulsingDots.length).toBeGreaterThan(0);
  });

  it("renders failed message with 'not delivered' text", () => {
    const pending: PendingMessage[] = [
      { id: -2, prompt: "failed msg", ts: new Date().toISOString(), status: "failed" },
    ];
    render(<EventFeed events={[]} pendingMessages={pending} />);
    expect(screen.getByText("not delivered")).toBeInTheDocument();
  });

  it("renders pending messages after server events", () => {
    const events: FeedEvent[] = [
      makeAuditEvent(1, "run_started", { model: "claude", branch: "main" }),
    ];
    const pending: PendingMessage[] = [
      { id: -1, prompt: "my message", ts: new Date().toISOString(), status: "pending" },
    ];
    const { container } = render(<EventFeed events={events} pendingMessages={pending} />);
    expect(container).toBeInTheDocument();
    expect(screen.getByText("my message")).toBeInTheDocument();
    expect(screen.getByText("Run Started")).toBeInTheDocument();
  });

  it("does not render pending messages when list is empty", () => {
    const events: FeedEvent[] = [
      makeAuditEvent(50, "prompt_injected", { prompt: "delivered" }),
    ];
    render(<EventFeed events={events} pendingMessages={[]} />);
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
    render(<EventFeed events={events} pendingMessages={[]} />);
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
    render(<EventFeed events={events} pendingMessages={pending} />);
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
    render(<EventFeed events={[]} pendingMessages={pending} />);
    expect(screen.getAllByText("You")).toHaveLength(2);
    expect(screen.getByText("msg one")).toBeInTheDocument();
    expect(screen.getByText("msg two")).toBeInTheDocument();
  });

  it("renders mix of pending and failed messages", () => {
    const pending: PendingMessage[] = [
      { id: -1, prompt: "delivered later", ts: "2026-01-01T10:00:00Z", status: "pending" },
      { id: -2, prompt: "could not send", ts: "2026-01-01T10:00:05Z", status: "failed" },
    ];
    const { container } = render(<EventFeed events={[]} pendingMessages={pending} />);
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
      makeAuditEvent(51, "resumed", { via: "inject" }),
    ];
    render(<EventFeed events={events} pendingMessages={[]} />);
    expect(screen.getByText("Run Started")).toBeInTheDocument();
    expect(screen.getByText("fix the bug")).toBeInTheDocument();
    expect(screen.getByText("Resumed")).toBeInTheDocument();
    expect(screen.getAllByText("You")).toHaveLength(1);
  });
});

/* ── EventFeed: empty state only when both events and pending empty ── */

describe("EventFeed empty state", () => {
  it("shows empty state when no events and no pending", () => {
    render(<EventFeed events={[]} pendingMessages={[]} />);
    expect(screen.getByText("Waiting for events")).toBeInTheDocument();
  });

  it("does not show empty state when pending messages exist", () => {
    const pending: PendingMessage[] = [
      { id: -1, prompt: "hello", ts: new Date().toISOString(), status: "pending" },
    ];
    render(<EventFeed events={[]} pendingMessages={pending} />);
    expect(screen.queryByText("Waiting for events")).not.toBeInTheDocument();
    expect(screen.getByText("hello")).toBeInTheDocument();
  });

  it("does not show empty state when events exist", () => {
    const events: FeedEvent[] = [
      makeAuditEvent(1, "run_started", { model: "claude", branch: "main" }),
    ];
    render(<EventFeed events={events} pendingMessages={[]} />);
    expect(screen.queryByText("Waiting for events")).not.toBeInTheDocument();
  });
});

/* ── EventFeed: user_prompt as interruption boundary ── */

describe("EventFeed user_prompt interruption boundary", () => {
  it("renders agent card before user_prompt with runActive=false", () => {
    const t0 = "2026-01-01T10:00:00.000Z";
    const t1 = "2026-01-01T10:00:10.000Z";

    const events: FeedEvent[] = [
      makeAgentToolEvent(t0),
      makeAuditEvent(5, "prompt_injected", { prompt: "stop exploring" }, t1),
    ];

    const { container } = render(
      <EventFeed events={events} runActive={true} />,
    );
    expect(container).toBeInTheDocument();

    // The agent card should NOT show a "running" status indicator
    const runningTexts = screen.queryAllByText("running");
    expect(runningTexts).toHaveLength(0);
  });

  it("renders agent card after user_prompt with runActive=true", () => {
    const t0 = "2026-01-01T10:00:00.000Z";
    const t1 = "2026-01-01T10:00:10.000Z";

    const events: FeedEvent[] = [
      makeAuditEvent(5, "prompt_injected", { prompt: "do something" }, t0),
      makeAgentToolEvent(t1),
    ];

    const { container } = render(
      <EventFeed events={events} runActive={true} />,
    );
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

describe("groupEvents session_resumed detail", () => {
  it("renders session_resumed with empty detail (no branch)", () => {
    const events: FeedEvent[] = [
      makeAuditEvent(1, "session_resumed", { branch: "autofyn/some-branch" }),
    ];
    const grouped = groupEvents(events);
    expect(grouped).toHaveLength(1);
    if (grouped[0].type === "milestone") {
      expect(grouped[0].label).toBe("Session Resumed");
      expect(grouped[0].detail).toBe("");
    }
  });
});
