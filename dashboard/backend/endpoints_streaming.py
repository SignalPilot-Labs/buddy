"""Dashboard API endpoints — SSE streaming and polling fallback."""

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, desc

from backend import auth
from backend.constants import POLL_LIMIT_DEFAULT, QUERY_MAX_LIMIT, SSE_POLL_INTERVAL_SEC
from backend.models import RunId
from backend.utils import model_to_dict, session
from db.models import AuditLog, Run, ToolCall

log = logging.getLogger("dashboard.streaming")

router = APIRouter(prefix="/api", dependencies=[Depends(auth.verify_api_key)])

_RUN_ENDED_STATUSES = frozenset({"completed", "stopped", "killed", "crashed", "error"})


@router.get("/stream/latest")
async def stream_latest() -> StreamingResponse:
    """Stream events for the most recent run."""
    async with session() as s:
        row = (await s.execute(select(Run.id).order_by(desc(Run.started_at)).limit(1))).scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="No runs found")
    return await stream_events(row)


async def _fetch_new_tool_calls(s, run_id: str, last_id: int) -> tuple[list[str], int]:
    """Fetch new tool call SSE events since last_id."""
    rows = (await s.execute(
        select(ToolCall)
        .where(ToolCall.run_id == run_id, ToolCall.id > last_id)
        .order_by(ToolCall.id)
    )).scalars().all()
    events = [f"event: tool_call\ndata: {json.dumps(model_to_dict(tc), default=str)}\n\n" for tc in rows]
    new_last = rows[-1].id if rows else last_id
    return events, new_last


async def _fetch_new_audit_events(s, run_id: str, last_id: int) -> tuple[list[str], int]:
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


@router.get("/stream/{run_id}")
async def stream_events(run_id: str = RunId) -> StreamingResponse:
    """SSE endpoint — polls Postgres for new tool calls and audit events."""

    async def event_generator():
        last_tool_id, last_audit_id = await _init_cursors(run_id)
        yield f"event: connected\ndata: {json.dumps({'run_id': run_id})}\n\n"

        while True:
            found_any = False
            async with session() as s:
                tool_events, last_tool_id = await _fetch_new_tool_calls(s, run_id, last_tool_id)
                audit_events, last_audit_id = await _fetch_new_audit_events(s, run_id, last_audit_id)
            found_any = bool(tool_events or audit_events)
            for ev in tool_events:
                yield ev
            for ev in audit_events:
                yield ev

            if not found_any:
                yield f"event: ping\ndata: {json.dumps({'ts': 'keepalive'})}\n\n"
                ended_status = await _check_run_ended(run_id)
                if ended_status:
                    yield f"event: run_ended\ndata: {json.dumps({'status': ended_status})}\n\n"
                    return

            await asyncio.sleep(SSE_POLL_INTERVAL_SEC)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.get("/poll/{run_id}")
async def poll_events(
    run_id: str = RunId,
    after_tool: int = Query(default=0, ge=0),
    after_audit: int = Query(default=0, ge=0),
    limit: int = Query(default=POLL_LIMIT_DEFAULT, le=QUERY_MAX_LIMIT),
) -> dict:
    """Polling fallback for environments where SSE doesn't work (e.g. Cloudflare tunnels)."""
    async with session() as s:
        tool_calls = [
            model_to_dict(tc)
            for tc in (await s.execute(
                select(ToolCall)
                .where(ToolCall.run_id == run_id, ToolCall.id > after_tool)
                .order_by(ToolCall.id)
                .limit(limit)
            )).scalars().all()
        ]
        audit_events = [
            model_to_dict(al)
            for al in (await s.execute(
                select(AuditLog)
                .where(AuditLog.run_id == run_id, AuditLog.id > after_audit)
                .order_by(AuditLog.id)
                .limit(limit)
            )).scalars().all()
        ]
    return {"tool_calls": tool_calls, "audit_events": audit_events}
