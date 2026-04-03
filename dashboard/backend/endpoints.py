"""Dashboard API endpoints — runs, control signals, agent proxy, SSE, settings."""

import asyncio
import json
import logging
import re

from fastapi import APIRouter, Body, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, desc

from backend import auth, crypto
from backend.constants import (
    AGENT_TIMEOUT_LONG,
    AGENT_TIMEOUT_SHORT,
    DEFAULT_BASE_BRANCH,
    DEFAULT_STOP_REASON,
    MASK_PREFIX_CLAUDE_TOKEN,
    MASK_PREFIX_DEFAULT,
    MASTER_KEY_PATH,
    QUERY_MAX_LIMIT,
    RUNS_PAGE_SIZE,
    SECRET_KEYS,
    SSE_POLL_INTERVAL_SEC,
)
from backend.models import (
    ControlSignalRequest,
    RunId,
    SetActiveRepoRequest,
    StartRunRequest,
    UpdateSettingsRequest,
)
from backend.utils import (
    agent_request,
    ensure_repo_in_list,
    get_repo_list,
    model_to_dict,
    read_credentials,
    save_repo_list,
    send_control_signal,
    session,
    upsert_setting,
)
from db.models import AuditLog, Run, Setting, ToolCall

log = logging.getLogger("dashboard.endpoints")

router = APIRouter(prefix="/api", dependencies=[Depends(auth.verify_api_key)])


# ---------------------------------------------------------------------------
# Run APIs
# ---------------------------------------------------------------------------

@router.get("/runs")
async def list_runs(repo: str | None = Query(default=None)):
    """List recent runs, optionally filtered by repo."""
    async with session() as s:
        stmt = select(Run).order_by(desc(Run.started_at)).limit(RUNS_PAGE_SIZE)
        if repo:
            stmt = stmt.where(Run.github_repo == repo)
        result = await s.execute(stmt)
        return [model_to_dict(r) for r in result.scalars().all()]


@router.get("/runs/{run_id}")
async def get_run(run_id: str = RunId):
    """Get a single run by ID."""
    async with session() as s:
        run = await s.get(Run, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        return model_to_dict(run)


@router.get("/runs/{run_id}/tools")
async def get_tool_calls(
    run_id: str = RunId,
    limit: int = Query(default=200, le=QUERY_MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
):
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
    limit: int = Query(default=200, le=QUERY_MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
):
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
async def pause_run(run_id: str = RunId):
    """Pause a running agent."""
    return await send_control_signal(run_id, "pause", {"running"}, None)


@router.post("/runs/{run_id}/resume")
async def resume_run(run_id: str = RunId):
    """Resume a paused agent."""
    return await send_control_signal(run_id, "resume", {"paused"}, None)


@router.post("/runs/{run_id}/inject")
async def inject_prompt(run_id: str = RunId, body: ControlSignalRequest = Body()):
    """Inject a prompt into a running, paused, or completed agent.

    For running/paused runs: pushes an inject event to the agent.
    For completed/stopped runs: auto-resumes the run with the prompt as initial context.
    """
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
            creds = await read_credentials()
            resume_body = {
                "run_id": run_id,
                "prompt": prompt,
                "claude_token": creds.get("claude_token"),
                "git_token": creds.get("git_token"),
                "github_repo": creds.get("github_repo"),
            }
            result = await agent_request("POST", "/resume", AGENT_TIMEOUT_LONG, resume_body, None, None)
            run.status = "running"
            await s.commit()
            return {"ok": True, "signal": "inject_resume", "run_id": run_id, "resumed": True}

        raise HTTPException(status_code=409, detail=f"Cannot inject into run with status '{run.status}'")


@router.post("/runs/{run_id}/stop")
async def stop_run(run_id: str = RunId, body: ControlSignalRequest = Body()):
    """Stop a running agent."""
    reason = (body.payload or "").strip() or DEFAULT_STOP_REASON
    return await send_control_signal(run_id, "stop", {"running", "paused", "rate_limited"}, reason)


@router.post("/runs/{run_id}/unlock")
async def unlock_run(run_id: str = RunId):
    """Unlock a session time gate."""
    return await send_control_signal(run_id, "unlock", {"running", "paused", "rate_limited"}, None)


# ---------------------------------------------------------------------------
# Agent proxy
# ---------------------------------------------------------------------------

@router.get("/agent/health")
async def agent_health():
    """Check if agent container is reachable."""
    return await agent_request("GET", "/health", AGENT_TIMEOUT_SHORT, None, None, {"status": "unreachable"})


@router.get("/agent/branches")
async def list_branches():
    """List git branches from agent."""
    return await agent_request("GET", "/branches", AGENT_TIMEOUT_LONG, None, None, ["main"])


@router.get("/runs/{run_id}/diff")
async def get_run_diff(run_id: str = RunId):
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
        return {
            "files": diff_stats,
            "total_files": len(diff_stats),
            "total_added": sum(f.get("added", 0) for f in diff_stats),
            "total_removed": sum(f.get("removed", 0) for f in diff_stats),
            "source": "stored",
        }

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

    return {"files": [], "total_files": 0, "total_added": 0, "total_removed": 0, "source": "unavailable"}


# ---------------------------------------------------------------------------
# Parallel Runner Proxy
# ---------------------------------------------------------------------------

PARALLEL_TIMEOUT = 15  # Seconds for most parallel ops
PARALLEL_START_TIMEOUT = 180  # Starting a container takes longer


@router.get("/parallel/runs")
async def parallel_list_runs():
    """List all parallel worker slots."""
    return await agent_request("GET", "/parallel/runs", PARALLEL_TIMEOUT, None, None, [])


@router.post("/parallel/start")
async def parallel_start(body: StartRunRequest):
    """Start a new parallel worker container."""
    creds = await read_credentials()
    return await agent_request("POST", "/parallel/start", PARALLEL_START_TIMEOUT, {
        "prompt": body.prompt,
        "max_budget_usd": body.max_budget_usd,
        "duration_minutes": body.duration_minutes,
        "base_branch": body.base_branch,
        **creds,
    }, None, None)


@router.get("/parallel/status")
async def parallel_status():
    """Get parallel runner status summary."""
    return await agent_request("GET", "/parallel/status", PARALLEL_TIMEOUT, None, None, {
        "total_slots": 0, "active": 0, "max_concurrent": 10, "slots": [],
    })


@router.get("/parallel/runs/{run_id}")
async def parallel_get_run(run_id: str):
    """Get a single parallel run by run_id."""
    return await agent_request("GET", f"/parallel/runs/{run_id}", PARALLEL_TIMEOUT, None, None, None)


@router.get("/parallel/runs/{run_id}/health")
async def parallel_run_health(run_id: str):
    """Health check for a specific parallel worker."""
    return await agent_request("GET", f"/parallel/runs/{run_id}/health", PARALLEL_TIMEOUT, None, None, None)


@router.post("/parallel/runs/{run_id}/stop")
async def parallel_stop_run(run_id: str):
    """Stop a parallel worker."""
    return await agent_request("POST", f"/parallel/runs/{run_id}/stop", PARALLEL_TIMEOUT, None, None, None)


@router.post("/parallel/runs/{run_id}/kill")
async def parallel_kill_run(run_id: str):
    """Kill a parallel worker."""
    return await agent_request("POST", f"/parallel/runs/{run_id}/kill", PARALLEL_TIMEOUT, None, None, None)


@router.post("/parallel/runs/{run_id}/pause")
async def parallel_pause_run(run_id: str):
    """Pause a parallel worker."""
    return await agent_request("POST", f"/parallel/runs/{run_id}/pause", PARALLEL_TIMEOUT, None, None, None)


@router.post("/parallel/runs/{run_id}/resume")
async def parallel_resume_run(run_id: str):
    """Resume a parallel worker."""
    return await agent_request("POST", f"/parallel/runs/{run_id}/resume", PARALLEL_TIMEOUT, None, None, None)


@router.post("/parallel/runs/{run_id}/inject")
async def parallel_inject_run(run_id: str, body: ControlSignalRequest = Body()):
    """Inject a prompt into a parallel worker."""
    return await agent_request("POST", f"/parallel/runs/{run_id}/inject", PARALLEL_TIMEOUT, {
        "payload": body.payload,
    }, None, None)


@router.post("/parallel/runs/{run_id}/unlock")
async def parallel_unlock_run(run_id: str):
    """Unlock a parallel worker session."""
    return await agent_request("POST", f"/parallel/runs/{run_id}/unlock", PARALLEL_TIMEOUT, None, None, None)


@router.post("/parallel/cleanup")
async def parallel_cleanup():
    """Clean up finished parallel containers."""
    return await agent_request("POST", "/parallel/cleanup", PARALLEL_TIMEOUT, None, None, {"ok": True, "cleaned": 0})


# ---------------------------------------------------------------------------
# SSE Streaming
# ---------------------------------------------------------------------------

@router.get("/stream/latest")
async def stream_latest():
    """Stream events for the most recent run."""
    async with session() as s:
        row = (await s.execute(select(Run.id).order_by(desc(Run.started_at)).limit(1))).scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="No runs found")
    return await stream_events(row)


@router.get("/stream/{run_id}")
async def stream_events(run_id: str = RunId):
    """SSE endpoint — polls Postgres for new tool calls and audit events."""

    async def event_generator():
        async with session() as s:
            last_tool_id = (await s.execute(
                select(func.coalesce(func.max(ToolCall.id), 0)).where(ToolCall.run_id == run_id)
            )).scalar_one()
            last_audit_id = (await s.execute(
                select(func.coalesce(func.max(AuditLog.id), 0)).where(AuditLog.run_id == run_id)
            )).scalar_one()

        yield f"event: connected\ndata: {json.dumps({'run_id': run_id})}\n\n"

        while True:
            found_any = False
            async with session() as s:
                for tc in (await s.execute(
                    select(ToolCall).where(ToolCall.run_id == run_id, ToolCall.id > last_tool_id).order_by(ToolCall.id)
                )).scalars().all():
                    found_any = True
                    last_tool_id = tc.id
                    yield f"event: tool_call\ndata: {json.dumps(model_to_dict(tc), default=str)}\n\n"

                for al in (await s.execute(
                    select(AuditLog).where(AuditLog.run_id == run_id, AuditLog.id > last_audit_id).order_by(AuditLog.id)
                )).scalars().all():
                    found_any = True
                    last_audit_id = al.id
                    yield f"event: audit\ndata: {json.dumps(model_to_dict(al), default=str)}\n\n"

            if not found_any:
                yield f"event: ping\ndata: {json.dumps({'ts': 'keepalive'})}\n\n"

                # Check if run has ended — stop streaming after final events are flushed
                async with session() as s:
                    run_status = (await s.execute(
                        select(Run.status).where(Run.id == run_id)
                    )).scalar_one_or_none()
                if run_status in ("completed", "stopped", "killed", "crashed", "error"):
                    yield f"event: run_ended\ndata: {json.dumps({'status': run_status})}\n\n"
                    return

            await asyncio.sleep(SSE_POLL_INTERVAL_SEC)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Settings API
# ---------------------------------------------------------------------------

@router.get("/settings/status")
async def settings_status():
    """Check which credentials are configured."""
    async with session() as s:
        has = {}
        for key in ("claude_token", "git_token", "github_repo"):
            has[f"has_{key}"] = (await s.get(Setting, key)) is not None
        has["configured"] = all(has.values())
        return has


@router.get("/settings")
async def get_settings():
    """Get all settings with secrets masked."""
    async with session() as s:
        result = await s.execute(select(Setting))
        settings = {}
        for setting in result.scalars().all():
            if setting.encrypted:
                try:
                    plain = crypto.decrypt(setting.value, MASTER_KEY_PATH)
                    prefix = MASK_PREFIX_CLAUDE_TOKEN if setting.key == "claude_token" else MASK_PREFIX_DEFAULT
                    settings[setting.key] = crypto.mask(plain, prefix_len=prefix)
                except Exception as e:
                    log.error("Failed to decrypt setting '%s': %s", setting.key, e)
                    settings[setting.key] = "****"
            else:
                settings[setting.key] = setting.value
        return settings


@router.put("/settings")
async def update_settings(body: UpdateSettingsRequest):
    """Create or update settings. Secrets are encrypted before storage."""
    updates = body.model_dump(exclude_none=True)
    async with session() as s:
        for key, value in updates.items():
            is_secret = key in SECRET_KEYS
            stored_val = crypto.encrypt(value, MASTER_KEY_PATH) if is_secret else value
            await upsert_setting(s, key, stored_val, is_secret)
        if "github_repo" in updates and updates["github_repo"]:
            await ensure_repo_in_list(s, updates["github_repo"])
        await s.commit()
    auth.clear_cache()
    return {"ok": True, "updated": list(updates.keys())}


@router.get("/repos")
async def list_repos():
    """List all configured repos with run counts."""
    async with session() as s:
        repos = await get_repo_list(s)

        active = await s.get(Setting, "github_repo")
        if active and active.value and active.value not in repos:
            await ensure_repo_in_list(s, active.value)
            repos.append(active.value)
            await s.commit()

        result = []
        for repo in repos:
            count = (await s.execute(
                select(func.count()).select_from(Run).where(Run.github_repo == repo)
            )).scalar_one()
            result.append({"repo": repo, "run_count": count})
        return result


@router.put("/repos/active")
async def set_active_repo(body: SetActiveRepoRequest):
    """Set the active repo."""
    async with session() as s:
        await upsert_setting(s, "github_repo", body.repo, False)
        await ensure_repo_in_list(s, body.repo)
        await s.commit()
    return {"ok": True, "active_repo": body.repo}


@router.delete("/repos/{repo_slug:path}")
async def remove_repo(repo_slug: str):
    """Remove a repo from the list (does not delete runs)."""
    if not re.match(r'^[\w\-\.]+/[\w\-\.]+$', repo_slug):
        raise HTTPException(status_code=400, detail="Invalid repo slug format")
    async with session() as s:
        repos = [r for r in await get_repo_list(s) if r != repo_slug]
        await save_repo_list(s, repos)
        await s.commit()
    return {"ok": True, "remaining": repos}
