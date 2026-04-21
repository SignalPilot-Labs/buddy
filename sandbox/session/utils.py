"""Session utility functions — HTTP audit logging, serialization, agent parsing.

Audit and tool-call logging is done via HTTP POST to the agent container.
The sandbox no longer has a direct DB connection.

POSTs use a 10s timeout and retry up to 3 times with exponential backoff
on transient failures (5xx, timeouts, connection errors). After all retries
are exhausted, the failure is logged as a warning — audit logging must
never crash the SDK session.
"""

import asyncio
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
    AGENT_HTTP_TIMEOUT_SEC,
    AGENT_LOG_RETRY_ATTEMPTS,
    AGENT_LOG_RETRY_BASE_SEC,
    AGENT_URL_ENV_VAR,
    INPUT_CONTENT_MAX_LEN,
    INPUT_SUMMARY_MAX_LEN,
    INTERNAL_SECRET_ENV_VAR,
    INTERNAL_SECRET_HEADER,
)
from models import ToolContext

log = logging.getLogger("sandbox.session_utils")

# Cache env-based config at import time. server.py imports this module
# BEFORE it pops SANDBOX_INTERNAL_SECRET from os.environ (line 48), so
# the env var is still present here. After server.py pops it, os.environ
# no longer has it — any lazy read would fail silently.
_AGENT_URL: str = os.environ.get(AGENT_URL_ENV_VAR, "")
_SANDBOX_SECRET: str = os.environ.get(INTERNAL_SECRET_ENV_VAR, "")

# Module-level lazy aiohttp session. Created on first use.
# Closed explicitly via close_agent_client() on server shutdown.
_agent_client: aiohttp.ClientSession | None = None


def _get_agent_client() -> aiohttp.ClientSession:
    """Return the module-level aiohttp session, creating it on first call."""
    global _agent_client
    if _agent_client is None or _agent_client.closed:
        _agent_client = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=AGENT_HTTP_TIMEOUT_SEC),
        )
    return _agent_client


async def close_agent_client() -> None:
    """Close the module-level aiohttp session. Called on server shutdown."""
    global _agent_client
    if _agent_client is not None and not _agent_client.closed:
        await _agent_client.close()
    _agent_client = None


def _agent_url() -> str:
    """Return the cached agent base URL. Raises if not set at import time."""
    if not _AGENT_URL:
        raise RuntimeError(f"{AGENT_URL_ENV_VAR} is not set — cannot reach agent")
    return _AGENT_URL


def _sandbox_secret() -> str:
    """Return the cached sandbox secret. Raises if not set at import time."""
    if not _SANDBOX_SECRET:
        raise RuntimeError(f"{INTERNAL_SECRET_ENV_VAR} is not set")
    return _SANDBOX_SECRET


async def _post_to_agent(path: str, payload: dict) -> None:
    """POST to agent with timeout and retry. Logs warning on final failure.

    Retries on 5xx and transient errors (timeout, connection). Does NOT
    retry on 4xx (indicates a bug, not a transient failure). After all
    retries are exhausted, logs a warning and returns — never raises.
    """
    client = _get_agent_client()
    headers = {INTERNAL_SECRET_HEADER: _sandbox_secret()}
    url = f"{_agent_url()}{path}"
    last_err: str = ""
    for attempt in range(AGENT_LOG_RETRY_ATTEMPTS):
        try:
            async with client.post(url, json=payload, headers=headers) as resp:
                if resp.status < 400:
                    return
                if resp.status < 500:
                    log.warning("Agent returned %d for %s (not retryable)", resp.status, path)
                    return
                last_err = f"Agent returned {resp.status}"
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            last_err = str(e)
        if attempt < AGENT_LOG_RETRY_ATTEMPTS - 1:
            await asyncio.sleep(AGENT_LOG_RETRY_BASE_SEC * (2 ** attempt))
    log.warning(
        "All %d attempts failed for %s: %s",
        AGENT_LOG_RETRY_ATTEMPTS,
        path,
        last_err,
    )


async def log_tool_call(
    run_id: str,
    phase: str,
    context: ToolContext,
    input_data: dict | None,
    output_data: dict | None,
) -> None:
    """POST a tool call event to the agent's /internal/tool-call endpoint."""
    try:
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
        await _post_to_agent("/internal/tool-call", payload)
    except Exception as e:
        log.warning("Failed to log tool call: %s", e)


async def log_audit(run_id: str, event_type: str, details: dict) -> None:
    """POST an audit event to the agent's /internal/audit endpoint."""
    try:
        payload = {
            "run_id": run_id,
            "event_type": event_type,
            "details": details,
        }
        await _post_to_agent("/internal/audit", payload)
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
