"""DB logging helpers for tool calls and audit events.

Pure async DB writes — no state, no side effects beyond persisting rows.
"""

import logging

from db.connection import get_session_factory
from db.models import AuditLog, ToolCall

log = logging.getLogger("sandbox.session_manager")


async def log_tool_call(
    run_id: str,
    phase: str,
    tool_name: str,
    input_data: dict | None,
    output_data: dict | None,
    duration_ms: int | None,
    permitted: bool,
    deny_reason: str | None,
    agent_role: str,
    tool_use_id: str | None,
    session_id: str | None,
    agent_id: str | None,
) -> None:
    """Insert a tool call row into the database."""
    try:
        async with get_session_factory()() as s:
            s.add(ToolCall(
                run_id=run_id,
                phase=phase,
                tool_name=tool_name,
                input_data=input_data,
                output_data=output_data,
                duration_ms=duration_ms,
                permitted=permitted,
                deny_reason=deny_reason,
                agent_role=agent_role,
                tool_use_id=tool_use_id,
                session_id=session_id,
                agent_id=agent_id,
            ))
            await s.commit()
    except Exception as e:
        log.warning("Failed to log tool call: %s", e)


async def log_audit(run_id: str, event_type: str, details: dict) -> None:
    """Insert an audit log row into the database."""
    try:
        async with get_session_factory()() as s:
            s.add(AuditLog(run_id=run_id, event_type=event_type, details=details))
            await s.commit()
    except Exception as e:
        log.warning("Failed to log audit event: %s", e)
