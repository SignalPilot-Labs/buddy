"""Dashboard API endpoints — SSE streaming and polling fallback."""

import asyncio
import json
import logging
from typing import AsyncGenerator, NamedTuple

from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend import auth
from backend.constants import POLL_LIMIT_DEFAULT, QUERY_MAX_LIMIT, SSE_POLL_INTERVAL_SEC
from backend.models import RunId
from backend.utils import model_to_dict, require_run, session
from db.models import AuditLog, Run, ToolCall

log = logging.getLogger("dashboard.streaming")

router = APIRouter(prefix="/api", dependencies=[Depends(auth.verify_api_key_or_query)])

_RUN_ENDED_STATUSES = frozenset({"completed", "stopped", "killed", "crashed", "error"})


class _PollResult(NamedTuple):
    tool_events: list[str]
    audit_events: list[str]
    last_tool_id: int
    last_audit_id: int
    ended_status: str | None


@router.get("/stream/latest")
async def stream_latest() -> StreamingResponse:
    """Stream events for the most recent run."""
    async with session() as s:
        row = (await s.execute(select(Run.id).order_by(desc(Run.started_at)).limit(1))).scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="No runs found")
    return await stream_events(row)


async def _fetch_new_tool_calls(s: AsyncSession, run_id: str, last_id: int) -> tuple[list[str], int]:
    """Fetch new tool call SSE events since last_id."""
    rows = (await s.execute(
        select(ToolCall)
        .where(ToolCall.run_id == run_id, ToolCall.id > last_id)
        .order_by(ToolCall.id)
    )).scalars().all()
    events = [f"event: tool_call\ndata: {json.dumps(model_to_dict(tc), default=str)}\n\n" for tc in rows]
    new_last = rows[-1].id if rows else last_id
    return events, new_last


async def _fetch_new_audit_events(s: AsyncSession, run_id: str, last_id: int) -> tuple[list[str], int]:
    """Fetch new audit log SSE events since last_id."""
    rows = (await s.execute(
        select(AuditLog)
        .where(AuditLog.run_id == run_id, AuditLog.id > last_id)
        .order_by(AuditLog.id)
    )).scalars().all()
    events = [f"event: audit\ndata: {json.dumps(model_to_dict(al), default=str)}\n\n" for al in rows]
    new_last = rows[-1].id if rows else last_id
    return events, new_last


async def _check_run_ended(run_id: str) -> str | None:
    """Return the run status if it has ended, else None."""
    async with session() as s:
        status = (await s.execute(select(Run.status).where(Run.id == run_id))).scalar_one_or_none()
    return status if status in _RUN_ENDED_STATUSES else None


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

    found_any = bool(tool_events or audit_events)
    ended_status = None if found_any else await _check_run_ended(run_id)
    return _PollResult(tool_events, audit_events, new_tool_id, new_audit_id, ended_status)


@router.get("/stream/{run_id}")
async def stream_events(run_id: str = RunId) -> StreamingResponse:
    """SSE endpoint — polls Postgres for new tool calls and audit events."""
    async with session() as s:
        await require_run(s, run_id)

    async def event_generator() -> AsyncGenerator[str, None]:
        last_tool_id, last_audit_id = await _init_cursors(run_id)
        yield f"event: connected\ndata: {json.dumps({'run_id': run_id})}\n\n"

        while True:
            result = await _poll_and_yield(run_id, last_tool_id, last_audit_id)
            last_tool_id, last_audit_id = result.last_tool_id, result.last_audit_id
            for ev in result.tool_events:
                yield ev
            for ev in result.audit_events:
                yield ev
            if not (result.tool_events or result.audit_events):
                yield f"event: ping\ndata: {json.dumps({'ts': 'keepalive'})}\n\n"
            if result.ended_status:
                yield f"event: run_ended\ndata: {json.dumps({'status': result.ended_status})}\n\n"
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
        await require_run(s, run_id)
        tool_calls = await _query_recent_tool_calls(s, run_id, after_tool, limit)
        audit_events = await _query_recent_audit_events(s, run_id, after_audit, limit)
    return {"tool_calls": tool_calls, "audit_events": audit_events}
