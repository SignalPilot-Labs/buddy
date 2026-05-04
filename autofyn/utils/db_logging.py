"""Audit and tool-call logging functions.

All raw variants raise on failure (use for HTTP endpoints).
All wrapped variants swallow errors (use for agent-internal code).

Idempotent variants use ON CONFLICT DO NOTHING with the idempotency_key
column for safe re-delivery on SSE reconnect. They intentionally DO NOT
swallow errors — a failed DB write must propagate so the event is retried,
not silently lost.
"""

from sqlalchemy.dialects.postgresql import insert as pg_insert

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


async def log_audit_idempotent(
    run_id: str,
    event_type: str,
    details: dict | None,
    idempotency_key: str | None,
) -> None:
    """Log an audit event with idempotency key. Duplicate keys are skipped.

    Raises on DB failure — caller must handle retry. This replaced the
    old sandbox POST path and must not silently lose events.
    """
    if event_type not in AUDIT_EVENT_TYPES:
        raise ValueError(f"Unknown audit event type: {event_type}")
    async with get_session_factory()() as s:
        stmt = pg_insert(AuditLog).values(
            run_id=run_id,
            event_type=event_type,
            details=details or {},
            idempotency_key=idempotency_key,
        )
        if idempotency_key is not None:
            stmt = stmt.on_conflict_do_nothing(
                index_elements=["run_id", "idempotency_key"],
                index_where=AuditLog.idempotency_key.isnot(None),
            )
        await s.execute(stmt)
        await s.commit()


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


async def log_tool_call_idempotent(
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
    idempotency_key: str | None,
) -> None:
    """Log a tool call with idempotency key. Duplicate keys are skipped.

    Raises on DB failure — caller must handle retry. This replaced the
    old sandbox POST path and must not silently lose events.
    """
    async with get_session_factory()() as s:
        stmt = pg_insert(ToolCall).values(
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
            idempotency_key=idempotency_key,
        )
        if idempotency_key is not None:
            stmt = stmt.on_conflict_do_nothing(
                index_elements=["run_id", "idempotency_key"],
                index_where=ToolCall.idempotency_key.isnot(None),
            )
        await s.execute(stmt)
        await s.commit()
