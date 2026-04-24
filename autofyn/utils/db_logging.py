"""Audit and tool-call logging functions.

All raw variants raise on failure (use for HTTP endpoints).
All wrapped variants swallow errors (use for agent-internal code).
"""

from db.connection import get_session_factory
from db.constants import AUDIT_EVENT_TYPES
from db.models import AuditLog, ToolCall
from utils.db_helpers import swallow_errors


async def log_audit_raw(run_id: str, event_type: str, details: dict | None) -> None:
    """Log an audit event. Raises on failure (use for HTTP endpoints)."""
    if event_type not in AUDIT_EVENT_TYPES:
        raise ValueError(f"Unknown audit event type: {event_type}")
    async with get_session_factory()() as s:
        s.add(
            AuditLog(
                run_id=run_id,
                event_type=event_type,
                details=details or {},
            )
        )
        await s.commit()


@swallow_errors
async def log_audit(run_id: str, event_type: str, details: dict | None) -> None:
    """Log an audit event. Swallows errors (use for agent-internal code)."""
    await log_audit_raw(run_id, event_type, details)


async def log_tool_call_raw(
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
    """Log a tool call event. Raises on failure (use for HTTP endpoints)."""
    async with get_session_factory()() as s:
        s.add(
            ToolCall(
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
            )
        )
        await s.commit()


@swallow_errors
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
    """Log a tool call event. Swallows errors (use for agent-internal code)."""
    await log_tool_call_raw(
        run_id, phase, tool_name, input_data, output_data,
        duration_ms, permitted, deny_reason, agent_role,
        tool_use_id, session_id, agent_id,
    )
