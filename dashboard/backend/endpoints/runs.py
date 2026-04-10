"""Dashboard API endpoints — runs, control signals, agent proxy, diff."""

import logging

from fastapi import APIRouter, Body, Depends, Query, HTTPException
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend import auth
from backend.constants import (
    AGENT_TIMEOUT_LONG,
    AGENT_TIMEOUT_SHORT,
    DEFAULT_BASE_BRANCH,
    DEFAULT_STOP_REASON,
    LOG_TAIL_DEFAULT,
    LOG_TAIL_MAX,
    QUERY_DEFAULT_LIMIT,
    QUERY_MAX_LIMIT,
    RUNS_PAGE_SIZE,
)
from backend.models import (
    ControlSignalRequest,
    RunId,
    StartRunRequest,
)
from backend.utils import (
    agent_request,
    model_to_dict,
    read_credentials,
    send_control_signal,
    session,
)
from db.models import AuditLog, Run, ToolCall

log = logging.getLogger("dashboard.endpoints")

router = APIRouter(prefix="/api", dependencies=[Depends(auth.verify_api_key)])


# ---------------------------------------------------------------------------
# Run APIs
# ---------------------------------------------------------------------------

@router.get("/runs")
async def list_runs(repo: str | None = Query(default=None)) -> list:
    """List recent runs, optionally filtered by repo."""
    async with session() as s:
        stmt = select(Run).order_by(desc(Run.started_at)).limit(RUNS_PAGE_SIZE)
        if repo:
            stmt = stmt.where(Run.github_repo == repo)
        result = await s.execute(stmt)
        return [model_to_dict(r) for r in result.scalars().all()]


@router.get("/runs/{run_id}")
async def get_run(run_id: str = RunId) -> dict:
    """Get a single run by ID."""
    async with session() as s:
        run = await s.get(Run, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        return model_to_dict(run)


@router.get("/runs/{run_id}/tools")
async def get_tool_calls(
    run_id: str = RunId,
    limit: int = Query(default=QUERY_DEFAULT_LIMIT, le=QUERY_MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
) -> list:
    """List tool calls for a run."""
    async with session() as s:
        result = await s.execute(
            select(ToolCall)
            .where(ToolCall.run_id == run_id)
            .order_by(desc(ToolCall.ts))
            .limit(limit)
            .offset(offset)
        )
        return [model_to_dict(r) for r in result.scalars().all()]


@router.get("/runs/{run_id}/audit")
async def get_audit_log(
    run_id: str = RunId,
    limit: int = Query(default=QUERY_DEFAULT_LIMIT, le=QUERY_MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
) -> list:
    """List audit log entries for a run."""
    async with session() as s:
        result = await s.execute(
            select(AuditLog)
            .where(AuditLog.run_id == run_id)
            .order_by(desc(AuditLog.ts))
            .limit(limit)
            .offset(offset)
        )
        return [model_to_dict(r) for r in result.scalars().all()]


# ---------------------------------------------------------------------------
# Control Signals
# ---------------------------------------------------------------------------

@router.post("/runs/{run_id}/pause")
async def pause_run(run_id: str = RunId) -> dict:
    """Pause a running agent."""
    return await send_control_signal(run_id, "pause", {"running"}, None)


async def _resume_completed_run(run: Run, run_id: str, prompt: str | None, s: AsyncSession) -> dict:
    """Resume a completed/stopped/error run with the given prompt."""
    creds = await read_credentials(run.github_repo)
    resume_body = {
        "run_id": run_id,
        "prompt": prompt,
        "claude_token": creds.get("claude_token"),
        "git_token": creds.get("git_token"),
        "github_repo": creds.get("github_repo"),
        "env": creds.get("env"),
    }
    await agent_request("POST", "/resume", AGENT_TIMEOUT_LONG, resume_body, None, None)
    run.status = "running"
    run.error_message = None
    await s.commit()
    return {"ok": True, "signal": "resume", "run_id": run_id, "resumed": True}


@router.post("/runs/{run_id}/resume")
async def resume_run(run_id: str = RunId, body: ControlSignalRequest = Body()) -> dict:
    """Resume a run — unpause if paused, restart if completed/stopped."""
    async with session() as s:
        run = await s.get(Run, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        if run.status == "paused":
            prompt = (body.payload or "").strip() or None
            if prompt:
                return await send_control_signal(run_id, "inject", {"paused"}, prompt)
            return await send_control_signal(run_id, "resume", {"paused"}, None)
        restartable = ("completed", "completed_no_changes", "stopped", "error", "crashed", "killed")
        if run.status in restartable:
            return await _resume_completed_run(run, run_id, (body.payload or "").strip() or None, s)
        raise HTTPException(status_code=409, detail=f"Cannot resume run with status '{run.status}'")


@router.post("/runs/{run_id}/inject")
async def inject_prompt(run_id: str = RunId, body: ControlSignalRequest = Body()) -> dict:
    """Inject a prompt into a running, paused, or completed agent."""
    if not body.payload or not body.payload.strip():
        raise HTTPException(status_code=400, detail="Payload (prompt text) is required")
    prompt = body.payload.strip()

    async with session() as s:
        run = await s.get(Run, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        if run.status in ("running", "paused", "rate_limited"):
            return await send_control_signal(run_id, "inject", {"running", "paused", "rate_limited"}, prompt)
        if run.status in ("completed", "stopped", "error"):
            return await _resume_completed_run(run, run_id, prompt, s)
        raise HTTPException(status_code=409, detail=f"Cannot inject into run with status '{run.status}'")


@router.post("/runs/{run_id}/stop")
async def stop_run(run_id: str = RunId, body: ControlSignalRequest = Body()) -> dict:
    """Stop a running agent."""
    reason = (body.payload or "").strip() or DEFAULT_STOP_REASON
    return await send_control_signal(run_id, "stop", {"running", "paused", "rate_limited"}, reason)


@router.post("/runs/{run_id}/unlock")
async def unlock_run(run_id: str = RunId) -> dict:
    """Unlock a session time gate."""
    return await send_control_signal(run_id, "unlock", {"running", "paused", "rate_limited"}, None)


@router.post("/runs/{run_id}/kill")
async def kill_run(run_id: str = RunId) -> dict:
    """Kill a run immediately (cancels the task)."""
    return await send_control_signal(run_id, "kill", {"running", "paused", "rate_limited"}, None)


# ---------------------------------------------------------------------------
# Agent proxy
# ---------------------------------------------------------------------------

@router.get("/agent/health")
async def agent_health() -> dict:
    """Check if agent container is reachable."""
    return await agent_request("GET", "/health", AGENT_TIMEOUT_SHORT, None, None, {
        "status": "unreachable", "active_runs": 0, "max_concurrent": 0, "runs": [],
    })


@router.post("/agent/start")
async def start_agent_run(body: StartRunRequest) -> dict:
    """Trigger a new improvement run."""
    creds = await read_credentials(body.repo)
    return await agent_request("POST", "/start", AGENT_TIMEOUT_LONG, {
        "prompt": body.prompt,
        "max_budget_usd": body.max_budget_usd,
        "duration_minutes": body.duration_minutes,
        "base_branch": body.base_branch,
        "model": body.model,
        "claude_token": creds.get("claude_token"),
        "git_token": creds.get("git_token"),
        "github_repo": creds.get("github_repo"),
        "env": creds.get("env"),
    }, None, None)


@router.get("/agent/branches")
async def list_branches() -> list:
    """List git branches from agent."""
    return await agent_request("GET", "/branches", AGENT_TIMEOUT_LONG, None, None, ["main"])


@router.get("/agent/logs")
async def agent_logs(tail: int = Query(default=LOG_TAIL_DEFAULT, le=LOG_TAIL_MAX)) -> dict:
    """Fetch container logs from the agent."""
    return await agent_request("GET", "/logs", AGENT_TIMEOUT_LONG, None, {"tail": tail}, {"lines": [], "total": 0})


# ---------------------------------------------------------------------------
# Diff
# ---------------------------------------------------------------------------

def _build_stored_diff(diff_stats: list) -> dict:
    """Build a diff response from stored diff_stats."""
    return {
        "files": diff_stats,
        "total_files": len(diff_stats),
        "total_added": sum(f.get("added", 0) for f in diff_stats),
        "total_removed": sum(f.get("removed", 0) for f in diff_stats),
        "source": "stored",
    }


async def _fetch_live_or_agent_diff(is_active: bool, branch_name: str, base_branch: str) -> dict | None:
    """Fetch a live diff (if run active) or from agent by branch name."""
    if is_active:
        data = await agent_request("GET", "/diff/live", AGENT_TIMEOUT_LONG, None, None, None)
        if data:
            data["source"] = "live"
            return data
    data = await agent_request(
        "GET", f"/diff/{branch_name}", AGENT_TIMEOUT_LONG,
        None, {"base": base_branch}, None,
    )
    if data:
        data["source"] = "agent"
        return data
    return None


@router.get("/runs/{run_id}/diff")
async def get_run_diff(run_id: str = RunId) -> dict:
    """Get diff stats for a run — stored, live, or from agent."""
    async with session() as s:
        run = await s.get(Run, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        diff_stats = run.diff_stats
        branch_name = run.branch_name
        base_branch = run.base_branch or DEFAULT_BASE_BRANCH
        is_active = run.status in ("running", "paused", "rate_limited")

    if diff_stats:
        return _build_stored_diff(diff_stats)

    data = await _fetch_live_or_agent_diff(is_active, branch_name, base_branch)
    if data:
        return data

    return {"files": [], "total_files": 0, "total_added": 0, "total_removed": 0, "source": "unavailable"}
