"""Dashboard API endpoints — SSE streaming and polling fallback."""

import asyncio
import json
import logging
from datetime import datetime
from typing import AsyncGenerator, NamedTuple

from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend import auth
from backend.constants import (
    POLL_LIMIT_DEFAULT,
    QUERY_MAX_LIMIT,
    SSE_POLL_INTERVAL_SEC,
    TYPE_PRIORITY_AUDIT,
    TYPE_PRIORITY_TOOL,
)
from backend.models import RunId
from backend.utils import model_to_dict, session
from db.constants import TERMINAL_RUN_STATUSES
from db.models import AuditLog, Run, ToolCall

log = logging.getLogger("dashboard.streaming")

router = APIRouter(prefix="/api", dependencies=[Depends(auth.verify_api_key_or_query)])

_RUN_ENDED_STATUSES = TERMINAL_RUN_STATUSES

# Sortable event tuple: (timestamp, type_priority, sse_string)
_SortableEvent = tuple[datetime, int, str]


class _PollResult(NamedTuple):
    events: list[_SortableEvent]
    last_tool_id: int
    last_audit_id: int
    ended_payload: dict | None


@router.get("/stream/latest")
async def stream_latest() -> StreamingResponse:
    """Stream events for the most recent run."""
    async with session() as s:
        row = (await s.execute(select(Run.id).order_by(desc(Run.started_at)).limit(1))).scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="No runs found")
    return await stream_events(row)


async def _fetch_new_tool_calls(
    s: AsyncSession, run_id: str, last_id: int
) -> tuple[list[_SortableEvent], int]:
    """Fetch new tool call events since last_id, returned as sortable tuples."""
    rows = (await s.execute(
        select(ToolCall)
        .where(ToolCall.run_id == run_id, ToolCall.id > last_id)
        .order_by(ToolCall.id)
    )).scalars().all()
    events: list[_SortableEvent] = [
        (tc.ts, TYPE_PRIORITY_TOOL, f"event: tool_call\ndata: {json.dumps(model_to_dict(tc), default=str)}\n\n")
        for tc in rows
    ]
    new_last = rows[-1].id if rows else last_id
    return events, new_last


async def _fetch_new_audit_events(
    s: AsyncSession, run_id: str, last_id: int
) -> tuple[list[_SortableEvent], int]:
    """Fetch new audit log events since last_id, returned as sortable tuples."""
    rows = (await s.execute(
        select(AuditLog)
        .where(AuditLog.run_id == run_id, AuditLog.id > last_id)
        .order_by(AuditLog.id)
    )).scalars().all()
    events: list[_SortableEvent] = [
        (al.ts, TYPE_PRIORITY_AUDIT, f"event: audit\ndata: {json.dumps(model_to_dict(al), default=str)}\n\n")
        for al in rows
    ]
    new_last = rows[-1].id if rows else last_id
    return events, new_last


async def _check_run_ended(run_id: str) -> dict | None:
    """Return a cost payload dict if the run has ended, else None."""
    async with session() as s:
        run = (await s.execute(select(Run).where(Run.id == run_id))).scalar_one_or_none()
    if run is None or run.status not in _RUN_ENDED_STATUSES:
        return None
    return {
        "status": run.status,
        "total_cost_usd": run.total_cost_usd,
        "total_input_tokens": run.total_input_tokens,
        "total_output_tokens": run.total_output_tokens,
        "cache_creation_input_tokens": run.cache_creation_input_tokens,
        "cache_read_input_tokens": run.cache_read_input_tokens,
        "context_tokens": run.context_tokens,
    }


async def _init_cursors(run_id: str) -> tuple[int, int]:
    """Return the current max tool call id and audit log id for a run."""
    async with session() as s:
        last_tool_id = (await s.execute(
            select(func.coalesce(func.max(ToolCall.id), 0)).where(ToolCall.run_id == run_id)
        )).scalar_one()
        last_audit_id = (await s.execute(
            select(func.coalesce(func.max(AuditLog.id), 0)).where(AuditLog.run_id == run_id)
        )).scalar_one()
    return last_tool_id, last_audit_id


async def _poll_and_yield(run_id: str, last_tool_id: int, last_audit_id: int) -> _PollResult:
    """Fetch one round of new events; also checks for run-ended when nothing new arrived."""
    async with session() as s:
        tool_events, new_tool_id = await _fetch_new_tool_calls(s, run_id, last_tool_id)
        audit_events, new_audit_id = await _fetch_new_audit_events(s, run_id, last_audit_id)

    merged = sorted(tool_events + audit_events, key=lambda ev: (ev[0], ev[1]))
    found_any = bool(merged)
    ended_payload = None if found_any else await _check_run_ended(run_id)
    return _PollResult(merged, new_tool_id, new_audit_id, ended_payload)


@router.get("/stream/{run_id}")
async def stream_events(
    run_id: str = RunId,
    after_tool: int = Query(default=-1),
    after_audit: int = Query(default=-1),
) -> StreamingResponse:
    """SSE endpoint — polls Postgres for new tool calls and audit events."""

    async def event_generator() -> AsyncGenerator[str, None]:
        if after_tool >= 0 and after_audit >= 0:
            last_tool_id, last_audit_id = after_tool, after_audit
        else:
            last_tool_id, last_audit_id = await _init_cursors(run_id)
        yield f"event: connected\ndata: {json.dumps({'run_id': run_id})}\n\n"

        while True:
            result = await _poll_and_yield(run_id, last_tool_id, last_audit_id)
            last_tool_id, last_audit_id = result.last_tool_id, result.last_audit_id
            for _ts, _priority, ev_str in result.events:
                yield ev_str
            if not result.events:
                yield f"event: ping\ndata: {json.dumps({'ts': 'keepalive'})}\n\n"
            if result.ended_payload:
                yield f"event: run_ended\ndata: {json.dumps(result.ended_payload)}\n\n"
                return
            await asyncio.sleep(SSE_POLL_INTERVAL_SEC)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


async def _query_recent_tool_calls(s: AsyncSession, run_id: str, after_tool: int, limit: int) -> list[dict]:
    """Return tool calls for a run after a given id, up to limit."""
    rows = (await s.execute(
        select(ToolCall)
        .where(ToolCall.run_id == run_id, ToolCall.id > after_tool)
        .order_by(ToolCall.id)
        .limit(limit)
    )).scalars().all()
    return [model_to_dict(tc) for tc in rows]


async def _query_recent_audit_events(s: AsyncSession, run_id: str, after_audit: int, limit: int) -> list[dict]:
    """Return audit events for a run after a given id, up to limit."""
    rows = (await s.execute(
        select(AuditLog)
        .where(AuditLog.run_id == run_id, AuditLog.id > after_audit)
        .order_by(AuditLog.id)
        .limit(limit)
    )).scalars().all()
    return [model_to_dict(al) for al in rows]


@router.get("/poll/{run_id}")
async def poll_events(
    run_id: str = RunId,
    after_tool: int = Query(default=0, ge=0),
    after_audit: int = Query(default=0, ge=0),
    limit: int = Query(default=POLL_LIMIT_DEFAULT, le=QUERY_MAX_LIMIT),
) -> dict:
    """Polling fallback for environments where SSE doesn't work."""
    async with session() as s:
        tool_calls = await _query_recent_tool_calls(s, run_id, after_tool, limit)
        audit_events = await _query_recent_audit_events(s, run_id, after_audit, limit)

    for tc in tool_calls:
        tc["_event_type"] = "tool_call"
    for ae in audit_events:
        ae["_event_type"] = "audit"

    merged = sorted(
        tool_calls + audit_events,
        key=lambda ev: (str(ev.get("ts", "")), TYPE_PRIORITY_TOOL if ev["_event_type"] == "tool_call" else TYPE_PRIORITY_AUDIT),
    )
    return {"events": merged}
