import type { ToolCall, AuditEvent, FeedEvent } from "@/lib/types";

export function makeToolCall(overrides?: Partial<ToolCall>): ToolCall {
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

export function makeToolEvent(overrides?: Partial<ToolCall>): FeedEvent {
  return { _kind: "tool", data: makeToolCall(overrides) };
}

export function makeAuditEvent(
  id: number,
  eventType: string,
  details: Record<string, unknown>,
  ts: string,
): FeedEvent {
  const data: AuditEvent = { id, run_id: "r", ts, event_type: eventType, details };
  return { _kind: "audit", data };
}
