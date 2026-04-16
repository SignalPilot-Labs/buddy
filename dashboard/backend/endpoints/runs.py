"""Dashboard API endpoints — runs, control signals, agent proxy, diff."""

import logging

from fastapi import APIRouter, Body, Depends, Query, HTTPException
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend import auth
from backend.constants import (
    ACTIVE_STATUSES,
    AGENT_TIMEOUT_LONG,
    AGENT_TIMEOUT_SHORT,
    DEFAULT_BASE_BRANCH,
    DEFAULT_STOP_REASON,
    HEADER_GITHUB_TOKEN,
    INJECTABLE_TERMINAL_STATUSES,
    LOG_TAIL_DEFAULT,
    LOG_TAIL_MAX,
    QUERY_DEFAULT_LIMIT,
    QUERY_MAX_LIMIT,
    RESTARTABLE_STATUSES,
    RUNS_PAGE_SIZE,
)
from backend.models import (
    ControlSignalRequest,
    RunId,
    StartRunRequest,
    StopRunRequest,
)
from backend.diff_parser import build_stats_response, parse_diff_stats
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
            .order_by(desc(ToolCall.ts), desc(ToolCall.id))
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
            .order_by(desc(AuditLog.ts), desc(AuditLog.id))
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
    return await send_control_signal(run_id, "pause", {"running"}, None, None)


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
    await agent_request("POST", "/resume", AGENT_TIMEOUT_LONG, resume_body, None, None, extra_headers=None)
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
        if run.status in ("paused", "rate_limited"):
            prompt = (body.payload or "").strip() or None
            if prompt:
                await send_control_signal(run_id, "inject", set(ACTIVE_STATUSES), prompt, None)
            if run.status == "paused":
                return await send_control_signal(run_id, "resume", {"paused"}, None, None)
            return {"ok": True, "signal": "inject", "run_id": run_id}
        if run.status in RESTARTABLE_STATUSES:
            return await _resume_completed_run(
                run, run_id, (body.payload or "").strip() or None, s,
            )
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
        if run.status in ACTIVE_STATUSES:
            return await send_control_signal(
                run_id, "inject", set(ACTIVE_STATUSES), prompt, None,
            )
        if run.status in INJECTABLE_TERMINAL_STATUSES:
            return await _resume_completed_run(run, run_id, prompt, s)
        raise HTTPException(status_code=409, detail=f"Cannot inject into run with status '{run.status}'")


@router.post("/runs/{run_id}/stop")
async def stop_run(run_id: str = RunId, body: StopRunRequest = Body()) -> dict:
    """Stop a running agent."""
    reason = (body.payload or "").strip() or DEFAULT_STOP_REASON
    return await send_control_signal(
        run_id, "stop", set(ACTIVE_STATUSES), reason, {"skip_pr": body.skip_pr},
    )


@router.post("/runs/{run_id}/unlock")
async def unlock_run(run_id: str = RunId) -> dict:
    """Unlock a session time gate."""
    return await send_control_signal(run_id, "unlock", set(ACTIVE_STATUSES), None, None)


# ---------------------------------------------------------------------------
# Agent proxy
# ---------------------------------------------------------------------------

@router.get("/agent/health")
async def agent_health() -> dict:
    """Check if agent container is reachable."""
    return await agent_request("GET", "/health", AGENT_TIMEOUT_SHORT, None, None, {
        "status": "unreachable", "active_runs": 0, "max_concurrent": 0, "runs": [],
    }, extra_headers=None)


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
        "effort": body.effort,
        "claude_token": creds.get("claude_token"),
        "git_token": creds.get("git_token"),
        "github_repo": creds.get("github_repo"),
        "env": creds.get("env"),
        "host_mounts": creds.get("host_mounts"),
    }, None, None, extra_headers=None)


@router.get("/agent/branches")
async def list_branches(repo: str = Query(...)) -> list:
    """List git branches for a repo via the agent (GitHub API proxy)."""
    creds = await read_credentials(repo)
    token = creds.get("git_token")
    if not token:
        raise HTTPException(
            status_code=400,
            detail=f"No git_token configured for {repo} — set one in Settings",
        )
    return await agent_request(
        "GET", "/branches", AGENT_TIMEOUT_LONG,
        None, {"repo": repo}, None, extra_headers={HEADER_GITHUB_TOKEN: token},
    )


@router.get("/agent/logs")
async def agent_logs(
    tail: int = Query(default=LOG_TAIL_DEFAULT, le=LOG_TAIL_MAX),
    run_id: str | None = Query(default=None),
) -> dict:
    """Fetch container logs from the agent, optionally filtered by run."""
    params: dict[str, str | int] = {"tail": tail}
    if run_id:
        params["run_id"] = run_id
    return await agent_request("GET", "/logs", AGENT_TIMEOUT_LONG, None, params, {"lines": [], "total": 0}, extra_headers=None)


# ---------------------------------------------------------------------------
# Diff
# ---------------------------------------------------------------------------

@router.get("/runs/{run_id}/diff")
async def get_run_diff(run_id: str = RunId) -> dict:
    """Diff stats for a run.

    Stored (post-teardown) `run.diff_stats` wins when present. For live
    runs mid-execution, teardown hasn't fired yet — fall back to the
    agent's `/diff/repo` endpoint and derive stats on-demand so the
    Changes panel can show real counts during the run.
    """
    async with session() as s:
        run = await s.get(Run, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        diff_stats = run.diff_stats
        branch_name = run.branch_name
        base_branch = run.base_branch or DEFAULT_BASE_BRANCH
        github_repo = run.github_repo

    if diff_stats:
        return build_stats_response(diff_stats, "stored")

    # Live-run path: derive stats from the current unified diff.
    # Two distinct failure modes surface to the frontend as distinct sources:
    #   - "unavailable": nothing to fetch yet (no repo/token, or diff is empty).
    #   - HTTPException: agent is unreachable / returned an error — raise
    #     through so the dashboard reports the problem instead of silently
    #     collapsing it into "unavailable".
    if not github_repo:
        return build_stats_response([], "unavailable")
    creds = await read_credentials(github_repo)
    token = creds.get("git_token")
    if not token:
        return build_stats_response([], "unavailable")
    result: dict = await agent_request(
        "GET", "/diff/repo", AGENT_TIMEOUT_LONG,
        None,
        {
            "run_id": run_id,
            "branch": branch_name,
            "base": base_branch,
            "repo": github_repo,
        },
        None,  # no fallback: agent errors must surface, not masquerade as empty
        extra_headers={HEADER_GITHUB_TOKEN: token},
    )
    diff_text = result["diff"]
    if not diff_text:
        return build_stats_response([], "unavailable")
    return build_stats_response(parse_diff_stats(diff_text), "live")


@router.get("/runs/{run_id}/diff/repo")
async def get_diff_repo(run_id: str = RunId) -> dict:
    """Full unified diff — proxies to agent (sandbox or GitHub API). Cached on agent."""
    async with session() as s:
        run = await s.get(Run, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        branch_name = run.branch_name
        base_branch = run.base_branch or DEFAULT_BASE_BRANCH
        github_repo = run.github_repo

    if not github_repo:
        raise HTTPException(status_code=404, detail="Run has no github_repo")

    creds = await read_credentials(github_repo)
    token = creds.get("git_token")
    if not token:
        raise HTTPException(status_code=400, detail="No git_token configured for this repo")

    return await agent_request(
        "GET", "/diff/repo", AGENT_TIMEOUT_LONG,
        None,
        {
            "run_id": run_id,
            "branch": branch_name,
            "base": base_branch,
            "repo": github_repo,
        },
        None,
        extra_headers={HEADER_GITHUB_TOKEN: token},
    )


@router.get("/runs/{run_id}/diff/tmp")
async def get_diff_tmp(run_id: str = RunId) -> dict:
    """List archived tmp/round files for a run."""
    return await agent_request(
        "GET", "/diff/tmp", AGENT_TIMEOUT_LONG,
        None, {"run_id": run_id}, None, extra_headers=None,
    )
