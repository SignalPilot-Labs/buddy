import type { FeedEvent, ToolCall, ToolCategory } from "./types";

export type GroupedEvent =
  | { id: string; type: "llm_message"; role: string; text: string; thinking: string; ts: string }
  | { id: string; type: "tool_group"; category: ToolCategory; label: string; tools: ToolCall[]; ts: string; totalDuration: number }
  | { id: string; type: "agent_run"; tool: ToolCall; childTools: ToolCall[]; finalText: string; agentType: string; ts: string }
  | { id: string; type: "edit_group"; tools: ToolCall[]; ts: string; totalDuration: number }
  | { id: string; type: "bash_group"; tools: ToolCall[]; ts: string; totalDuration: number }
  | { id: string; type: "playwright_group"; tools: ToolCall[]; ts: string; totalDuration: number }
  | { id: string; type: "single_tool"; tool: ToolCall; ts: string }
  | { id: string; type: "control"; text: string; ts: string; retryAction?: () => void }
  | { id: string; type: "milestone"; label: string; detail: string; color: string; ts: string; event?: FeedEvent }
  | { id: string; type: "user_prompt"; prompt: string; ts: string; pending?: boolean; failed?: boolean; injected?: boolean }
  | { id: string; type: "divider"; label: string; ts: string };
