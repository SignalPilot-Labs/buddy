/**
 * EventFeed component tests.
 *
 * Covers: empty state, rendering events, no duplicate rendering.
 */

import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { EventFeed } from "@/components/feed/EventFeed";
import type { FeedEvent } from "@/lib/types";

function makeToolEvent(id: number, name: string): FeedEvent {
  return {
    _kind: "tool",
    data: {
      id,
      run_id: "run-1",
      ts: new Date().toISOString(),
      phase: "post" as const,
      tool_name: name,
      input_data: { command: "echo hello" },
      output_data: { result: "hello" },
      duration_ms: 100,
      permitted: true,
      deny_reason: null,
      agent_role: "worker",
      tool_use_id: `tu-${id}`,
      session_id: null,
      agent_id: null,
    },
  };
}

function makeControlEvent(text: string): FeedEvent {
  return {
    _kind: "control",
    text,
    ts: new Date().toISOString(),
  };
}

describe("EventFeed", () => {
  it("renders without crashing on empty events", () => {
    const { container } = render(<EventFeed events={[]} />);
    expect(container).toBeInTheDocument();
  });

  it("renders tool events", () => {
    render(<EventFeed events={[makeToolEvent(1, "Bash")]} />);
    expect(screen.getByText(/Bash/)).toBeInTheDocument();
  });

  it("renders control events", () => {
    render(<EventFeed events={[makeControlEvent("Run starting...")]} />);
    expect(screen.getByText(/Run starting/)).toBeInTheDocument();
  });

  it("renders multiple events without crashing", () => {
    const events = [
      makeToolEvent(1, "Read"),
      makeToolEvent(2, "Write"),
      makeToolEvent(3, "Bash"),
    ];
    const { container } = render(<EventFeed events={events} />);
    expect(container).toBeInTheDocument();
  });

  it("does not duplicate control event text", () => {
    const events = [makeControlEvent("Run starting with custom prompt...")];
    render(<EventFeed events={events} />);
    const matches = screen.getAllByText(/Run starting/);
    expect(matches).toHaveLength(1);
  });
});
