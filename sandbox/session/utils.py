"""Session utility functions — HTTP audit logging, serialization, agent parsing.

Audit and tool-call logging is done via HTTP POST to the agent container.
The sandbox no longer has a direct DB connection.

Failures in log_audit / log_tool_call are caught and logged as warnings —
audit logging must never crash the SDK session.
"""

import json
import logging
import os
from typing import Any

import aiohttp

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

from constants import (
    AGENT_URL_ENV_VAR,
    INPUT_CONTENT_MAX_LEN,
    INPUT_SUMMARY_MAX_LEN,
    INTERNAL_SECRET_ENV_VAR,
    INTERNAL_SECRET_HEADER,
)
from models import ToolContext

log = logging.getLogger("sandbox.session_utils")

# Module-level lazy aiohttp session. Created on first use so env vars are
# available at call time. Closed explicitly via close_agent_client() on
# server shutdown.
_agent_client: aiohttp.ClientSession | None = None


def _get_agent_client() -> aiohttp.ClientSession:
    """Return the module-level aiohttp session, creating it on first call."""
    global _agent_client
    if _agent_client is None or _agent_client.closed:
        _agent_client = aiohttp.ClientSession()
    return _agent_client


async def close_agent_client() -> None:
    """Close the module-level aiohttp session. Called on server shutdown."""
    global _agent_client
    if _agent_client is not None and not _agent_client.closed:
        await _agent_client.close()
    _agent_client = None


def _agent_url() -> str:
    """Read the agent base URL from env. Raises if not set."""
    url = os.environ.get(AGENT_URL_ENV_VAR, "")
    if not url:
        raise RuntimeError(f"{AGENT_URL_ENV_VAR} is not set — cannot reach agent")
    return url


def _sandbox_secret() -> str:
    """Read the sandbox internal secret from env. Raises if not set."""
    secret = os.environ.get(INTERNAL_SECRET_ENV_VAR, "")
    if not secret:
        raise RuntimeError(f"{INTERNAL_SECRET_ENV_VAR} is not set")
    return secret


async def log_tool_call(
    run_id: str,
    phase: str,
    context: ToolContext,
    input_data: dict | None,
    output_data: dict | None,
) -> None:
    """POST a tool call event to the agent's /internal/tool-call endpoint."""
    try:
        client = _get_agent_client()
        headers = {INTERNAL_SECRET_HEADER: _sandbox_secret()}
        payload = {
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
        }
        async with client.post(
            f"{_agent_url()}/internal/tool-call",
            json=payload,
            headers=headers,
        ) as resp:
            if resp.status >= 400:
                log.warning(
                    "Failed to log tool call: agent returned %d", resp.status
                )
    except Exception as e:
        log.warning("Failed to log tool call: %s", e)


async def log_audit(run_id: str, event_type: str, details: dict) -> None:
    """POST an audit event to the agent's /internal/audit endpoint."""
    try:
        client = _get_agent_client()
        headers = {INTERNAL_SECRET_HEADER: _sandbox_secret()}
        payload = {
            "run_id": run_id,
            "event_type": event_type,
            "details": details,
        }
        async with client.post(
            f"{_agent_url()}/internal/audit",
            json=payload,
            headers=headers,
        ) as resp:
            if resp.status >= 400:
                log.warning(
                    "Failed to log audit event: agent returned %d", resp.status
                )
    except Exception as e:
        log.warning("Failed to log audit event: %s", e)


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
