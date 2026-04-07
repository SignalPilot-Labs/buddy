"""Session gate MCP tool: time-locked end_session functionality."""

import time
from typing import Any, Callable

from claude_agent_sdk import create_sdk_mcp_server, tool

from session.logging import log_audit

SECONDS_PER_MINUTE: int = 60


def build_session_gate_mcp(
    config: dict,
    run_id: str,
    emit: Callable[[dict], None],
) -> Any:
    """Build MCP server with end_session tool for time-locked sessions."""
    duration_min: float = config["duration_minutes"]
    start = time.time()

    @tool(
        "end_session",
        "End the current session. Denied if the time lock has not expired.",
        {"summary": str, "changes_made": int},
    )
    async def end_session_tool(args: dict[str, Any]) -> dict[str, Any]:
        elapsed_sec = time.time() - start
        elapsed_min = elapsed_sec / SECONDS_PER_MINUTE
        unlocked = duration_min <= 0 or elapsed_sec >= duration_min * SECONDS_PER_MINUTE

        if unlocked:
            await log_audit(run_id, "session_ended", {
                "summary": args["summary"],
                "changes_made": args["changes_made"],
                "elapsed_minutes": round(elapsed_min, 1),
            })
            emit({"event": "end_session", "data": {
                "summary": args["summary"],
                "changes_made": args["changes_made"],
                "elapsed_minutes": round(elapsed_min, 1),
            }})
            return {"content": [{"type": "text", "text": "Session ended."}]}

        remaining = duration_min - elapsed_min
        await log_audit(run_id, "end_session_denied", {
            "remaining_minutes": round(remaining, 1),
        })
        emit({"event": "end_session_denied", "data": {
            "remaining_minutes": round(remaining, 1),
        }})
        return {"content": [{"type": "text", "text": (
            f"SESSION LOCKED — {round(remaining, 1)}m remaining. "
            "Continue working. The planner will tell you when to stop."
        )}]}

    return create_sdk_mcp_server(name="session_gate", tools=[end_session_tool])
