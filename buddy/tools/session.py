"""Session gate: the end_session MCP tool and time-lock logic.

SessionGate is instantiated per-run with a RunContext. It manages the
time lock that prevents the agent from ending early, and provides the
MCP tool that is the agent's only way to stop.
"""

import time
from typing import Any

from claude_agent_sdk import tool, create_sdk_mcp_server

from utils import db
from utils.models import RunContext


class SessionGate:
    """Time-locked session control for a single run.

    Public API:
        is_unlocked, force_unlock, elapsed_minutes, time_remaining_str,
        has_ended, create_mcp_server
    """

    def __init__(self, ctx: RunContext):
        self._ctx = ctx
        self._start = time.time()
        self._duration_sec = ctx.duration_minutes * 60
        self._force_unlocked = False
        self._ended = False

    def force_unlock(self) -> None:
        """Called when operator sends an early unlock signal."""
        self._force_unlocked = True

    def is_unlocked(self) -> bool:
        """Check if end_session is currently allowed."""
        if self._force_unlocked:
            return True
        if self._duration_sec <= 0:
            return True
        return time.time() >= self._start + self._duration_sec

    def time_remaining_str(self) -> str:
        """Human-readable time remaining."""
        remaining = (self._start + self._duration_sec) - time.time()
        if remaining <= 0:
            return "0m"
        hours = int(remaining // 3600)
        minutes = int((remaining % 3600) // 60)
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"

    def elapsed_minutes(self) -> float:
        """Minutes elapsed since run start."""
        return (time.time() - self._start) / 60

    def has_ended(self) -> bool:
        """Check if the session has been ended via the end_session tool."""
        return self._ended

    def create_mcp_server(self):
        """Create the MCP server with the end_session tool bound to this instance."""
        gate = self  # Capture for closure

        @tool(
            "end_session",
            "End the current improvement session. This is the ONLY way to stop working. "
            "Call this when you have completed your improvements and want to finalize. "
            "The tool may be denied if the session time lock has not expired yet — "
            "in that case, continue working on the suggested focus area.",
            {"summary": str, "changes_made": int},
        )
        async def end_session_tool(args: dict[str, Any]) -> dict[str, Any]:
            return await gate._handle_end_session(args)

        return create_sdk_mcp_server(
            name="session_gate",
            version="1.0.0",
            tools=[end_session_tool],
        )

    async def _handle_end_session(self, args: dict[str, Any]) -> dict[str, Any]:
        """The agent's only exit. Denied until the time lock expires."""
        summary = args.get("summary", "No summary provided")
        changes = args.get("changes_made", 0)

        if self.is_unlocked():
            self._ended = True
            await db.log_audit(self._ctx.run_id, "session_ended", {
                "summary": summary,
                "changes_made": changes,
                "elapsed_minutes": round(self.elapsed_minutes(), 1),
                "was_force_unlocked": self._force_unlocked,
            })
            return {"content": [{"type": "text", "text": (
                f"Session ended successfully.\n"
                f"Summary: {summary}\n"
                f"Changes made: {changes}\n"
                f"Elapsed: {round(self.elapsed_minutes(), 1)} minutes\n\n"
                f"Commit any remaining work now. The framework will push "
                f"your branch and create a PR."
            )}]}
        else:
            await db.log_audit(self._ctx.run_id, "end_session_denied", {
                "summary": summary,
                "changes_made": changes,
                "time_remaining": self.time_remaining_str(),
                "elapsed_minutes": round(self.elapsed_minutes(), 1),
            })
            remaining = self.time_remaining_str()
            return {"content": [{"type": "text", "text": (
                f"SESSION LOCKED — {remaining} remaining. You cannot end the session yet.\n\n"
                f"Your task is not done. If you've finished the current assignment, "
                f"stop and wait — a Product Director will review your work and give you "
                f"your next task. Do NOT go looking for unrelated work to do."
            )}]}
