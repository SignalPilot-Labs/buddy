"""Serialization and parsing helpers for Claude SDK messages and agent configs.

Pure utility functions with no state.
"""

import json
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ThinkingBlock,
    ToolUseBlock,
)
from claude_agent_sdk.types import AgentDefinition, RateLimitEvent, StreamEvent

from constants import INPUT_SUMMARY_MAX_LEN


def parse_agents(raw: dict[str, dict]) -> dict[str, AgentDefinition]:
    """Convert plain dicts from the agent into AgentDefinition dataclasses."""
    return {
        name: AgentDefinition(
            description=defn["description"],
            prompt=defn["prompt"],
            model=defn.get("model"),
            tools=defn.get("tools"),
        )
        for name, defn in raw.items()
    }


def summarize(data: Any) -> dict:
    """Truncate large values in tool input/output for DB storage as JSONB."""
    if not isinstance(data, dict):
        raw = json.dumps(data, default=str)
        if len(raw) > INPUT_SUMMARY_MAX_LEN:
            raw = raw[:INPUT_SUMMARY_MAX_LEN] + "..."
        return {"_raw": raw}
    result: dict[str, Any] = {}
    for key, val in data.items():
        if isinstance(val, str) and len(val) > INPUT_SUMMARY_MAX_LEN:
            result[key] = val[:INPUT_SUMMARY_MAX_LEN] + "..."
        else:
            result[key] = val
    return result


def serialize_message(message: object) -> dict | None:
    """Convert SDK message to a JSON-serializable event dict."""
    if isinstance(message, StreamEvent):
        return {"event": "stream_event", "data": {"event": message.event or {}}}
    if isinstance(message, AssistantMessage):
        return _serialize_assistant_message(message)
    if isinstance(message, RateLimitEvent):
        info = message.rate_limit_info
        return {"event": "rate_limit", "data": {
            "status": info.status,
            "resets_at": info.resets_at,
            "utilization": info.utilization,
        }}
    if isinstance(message, ResultMessage):
        return {"event": "result", "data": {
            "session_id": message.session_id,
            "total_cost_usd": message.total_cost_usd,
            "num_turns": message.num_turns,
            "usage": message.usage,
        }}
    return None


def _serialize_assistant_message(message: AssistantMessage) -> dict:
    """Convert an AssistantMessage to a JSON-serializable event dict."""
    blocks = []
    for block in message.content:
        if isinstance(block, TextBlock):
            blocks.append({"type": "text", "text": block.text})
        elif isinstance(block, ThinkingBlock):
            blocks.append({"type": "thinking", "thinking": block.thinking})
        elif isinstance(block, ToolUseBlock):
            blocks.append({
                "type": "tool_use",
                "id": block.id,
                "name": block.name,
                "input": block.input,
            })
    return {"event": "assistant_message", "data": {
        "content": blocks,
        "usage": message.usage,
    }}
