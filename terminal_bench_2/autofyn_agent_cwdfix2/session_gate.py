"""Simplified end_session MCP tool — no time lock.

In production AutoFyn the gate is time-locked (agent can't end early).
For Terminal-Bench, Harbor kills the container on timeout, so we just
need end_session to cleanly signal completion and log it.
"""

import time
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool

from terminal_bench.logger import EventLogger


def build_session_gate(logger: EventLogger) -> Any:
    """Return an MCP server with a single unlocked end_session tool."""
    start = time.time()

    @tool(
        "end_session",
        "End the current session. Call when the task is fully complete.",
        {"summary": str, "changes_made": int},
    )
    async def end_session_tool(args: dict[str, Any]) -> dict[str, Any]:
        elapsed = round(time.time() - start, 1)
        logger.log(
            "session_ended",
            summary=args.get("summary", ""),
            changes_made=args.get("changes_made", 0),
            elapsed_sec=elapsed,
        )
        return {"content": [{"type": "text", "text": "Session ended."}]}

    return create_sdk_mcp_server(name="session_gate", tools=[end_session_tool])
