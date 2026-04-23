"""Route handlers for log endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI

from utils.constants import RUN_ID_LOG_PREFIX_LEN

if TYPE_CHECKING:
    from server import AgentServer


def register_log_routes(app: FastAPI, server: "AgentServer") -> None:
    """Register log route handlers."""

    @app.get("/logs")
    async def get_logs(tail: int, run_id: str | None = None):
        """Return agent container logs, optionally filtered by run_id.

        Log lines from the agent use run_id[:8] as prefix, e.g.
        ``[abc12345] Round 1 begin``. Continuation lines (tracebacks)
        lack the prefix but belong to the preceding log entry — they
        are included when the parent line matched.

        A line is a "new entry" if it starts with ``[`` (our log format)
        or a timestamp digit. Everything else is a continuation.
        """
        lines = await server.pool().get_self_logs(tail)
        if run_id:
            prefix = run_id[:RUN_ID_LOG_PREFIX_LEN]
            filtered: list[str] = []
            keep = False
            for line in lines:
                if line and (line[0] == "[" or line[0].isdigit()):
                    keep = prefix in line
                if keep:
                    filtered.append(line)
            lines = filtered
        return {"lines": lines, "total": len(lines)}
