"""Session utility functions — event reporting, serialization, agent parsing.

Shared by SessionManager and Session. Tool-call and audit events are
POSTed to the agent container's /events/* endpoints (see agent_events).
The sandbox does not hold DB credentials or reach Postgres directly.
"""

import json
import logging
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ThinkingBlock,
    ToolUseBlock,
)
from claude_agent_sdk.types import (
    AgentDefinition,
    RateLimitEvent,
    StreamEvent,
)

from constants import INPUT_CONTENT_MAX_LEN, INPUT_SUMMARY_MAX_LEN
from models import ToolContext
from session.agent_events import post_event

log = logging.getLogger("sandbox.session_utils")


async def log_tool_call(
    run_id: str,
    phase: str,
    context: ToolContext,
    input_data: dict | None,
    output_data: dict | None,
) -> None:
    """Report a tool invocation to the agent for DB persistence."""
    await post_event("tool_call", {
        "run_id": run_id,
        "phase": phase,
        "tool_name": context.tool_name,
        "input_data": input_data,
        "output_data": output_data,
        "duration_ms": context.duration_ms,
        "permitted": True,
        "deny_reason": None,
        "agent_role": context.role,
        "tool_use_id": context.tool_use_id,
        "session_id": context.session_id,
        "agent_id": context.agent_id,
    })


async def log_audit(run_id: str, event_type: str, details: dict) -> None:
    """Report an audit event to the agent for DB persistence."""
    await post_event("audit", {
        "run_id": run_id,
        "event_type": event_type,
        "details": details,
    })


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
    CONTENT_KEYS = {"content", "prompt"}
    result: dict[str, Any] = {}
    for key, val in data.items():
        if isinstance(val, str):
            limit = INPUT_CONTENT_MAX_LEN if key in CONTENT_KEYS else INPUT_SUMMARY_MAX_LEN
            if len(val) > limit:
                result[key] = val[:limit] + "..."
            else:
                result[key] = val
        else:
            result[key] = val
    return result


def serialize_message(message: object) -> dict | None:
    """Convert SDK message to a JSON-serializable event dict."""
    if isinstance(message, StreamEvent):
        return {"event": "stream_event", "data": {"event": message.event or {}}}
    if isinstance(message, AssistantMessage):
        blocks = []
        for block in message.content:
            if isinstance(block, TextBlock):
                blocks.append({"type": "text", "text": block.text})
            elif isinstance(block, ThinkingBlock):
                blocks.append({"type": "thinking", "thinking": block.thinking})
            elif isinstance(block, ToolUseBlock):
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    }
                )
        return {
            "event": "assistant_message",
            "data": {"content": blocks, "usage": message.usage},
        }
    if isinstance(message, RateLimitEvent):
        info = message.rate_limit_info
        return {
            "event": "rate_limit",
            "data": {
                "status": info.status,
                "resets_at": info.resets_at,
                "utilization": info.utilization,
            },
        }
    if isinstance(message, ResultMessage):
        return {
            "event": "result",
            "data": {
                "session_id": message.session_id,
                "total_cost_usd": message.total_cost_usd,
                "num_turns": message.num_turns,
                "usage": message.usage,
            },
        }
    return None
