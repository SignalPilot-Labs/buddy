"""Route handlers for control signals: stop, pause, resume, inject, unlock, cleanup."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from fastapi import FastAPI, HTTPException

from db.constants import CLEANABLE_RUN_STATUSES
from endpoints.helpers import merge_tokens_into_env
from utils import db
from utils.db_logging import log_audit
from utils.models import ActiveRun
from utils.models_http import InjectRequest, ResumeRequest, StartRequest, StopRequest

if TYPE_CHECKING:
    from server import AgentServer

log = logging.getLogger("endpoints.control")


async def _restart_terminal_run(server: "AgentServer", body: ResumeRequest) -> dict:
    """Restart a stopped/crashed/completed run by re-bootstrapping from its branch."""
    run_id = body.run_id
    run_info = await db.get_run_for_resume(run_id)
    if not run_info:
        raise HTTPException(status_code=404, detail="Run not found")
    if not run_info["branch_name"]:
        raise HTTPException(status_code=409, detail="Run has no branch — cannot resume")

    prompt = body.prompt or run_info["custom_prompt"]
    if not prompt:
        raise HTTPException(status_code=409, detail="Run has no prompt and none provided")
    github_repo = body.github_repo or run_info["github_repo"]
    if not github_repo:
        raise HTTPException(status_code=409, detail="Run has no github_repo")
    if not run_info["model_name"]:
        raise HTTPException(status_code=409, detail="Run has no model_name in DB")
    if not run_info["base_branch"]:
        raise HTTPException(status_code=409, detail="Run has no base_branch in DB")

    merged_env = merge_tokens_into_env(body.env, body.claude_token, body.git_token)
    start_cmd = await server.pool().resolve_start_cmd(body.sandbox_id)
    start_body = StartRequest(
        prompt=prompt,
        max_budget_usd=0,
        duration_minutes=run_info["duration_minutes"],
        base_branch=run_info["base_branch"],
        model=run_info["model_name"],
        github_repo=github_repo,
        env=merged_env,
        mcp_servers=body.mcp_servers,
        sandbox_id=body.sandbox_id,
        start_cmd=start_cmd,
    )

    # Clean up stale ActiveRun if present (e.g. crashed but not cleaned up).
    server.remove_run(run_id)

    active = ActiveRun(run_id=run_id)
    server.register_run(active)

    task = asyncio.create_task(server.execute_run(active, start_body))
    active.task = task
    task.add_done_callback(lambda t: server.on_task_done(active, t))
    return {"ok": True, "event": "resume", "run_id": run_id, "restarted": True}


def register_control_routes(app: FastAPI, server: "AgentServer") -> None:
    """Register control signal route handlers."""

    @app.post("/stop")
    async def stop(body: StopRequest, run_id: str | None = None) -> dict:
        r = server.get_run_or_first(run_id)
        if not r.inbox:
            raise HTTPException(status_code=409, detail="Run not accepting signals")
        r.skip_pr = body.skip_pr
        r.inbox.push("stop", "User stop via API")
        return {"ok": True, "event": "stop", "run_id": r.run_id}

    @app.post("/pause")
    async def pause(run_id: str | None = None) -> dict:
        r = server.get_run_or_first(run_id)
        if not r.inbox:
            raise HTTPException(status_code=409, detail="Run not accepting signals")
        r.inbox.push("pause", "")
        return {"ok": True, "event": "pause", "run_id": r.run_id}

    @app.post("/resume")
    async def resume(body: ResumeRequest | None = None, run_id: str | None = None) -> dict:
        """Unpause a paused run or restart a terminal run."""
        # If body has run_id, this is a restart of a terminal run.
        if body and body.run_id:
            return await _restart_terminal_run(server, body)

        # Otherwise, unpause a paused run.
        r = server.get_run_or_first(run_id)
        if not r.inbox:
            raise HTTPException(status_code=409, detail="Run not accepting signals")
        r.inbox.push("resume", "")
        return {"ok": True, "event": "resume", "run_id": r.run_id}

    @app.post("/inject")
    async def inject(body: InjectRequest, run_id: str | None = None) -> dict:
        r = server.get_run_or_first(run_id)
        if not r.inbox:
            raise HTTPException(status_code=409, detail="Run not accepting signals")
        r.inbox.push("inject", body.payload or "")
        return {"ok": True, "event": "inject", "run_id": r.run_id}

    @app.post("/unlock")
    async def unlock(run_id: str | None = None) -> dict:
        r = server.get_run_or_first(run_id)
        if not r.time_lock:
            raise HTTPException(status_code=409, detail="Run not accepting signals")
        r.time_lock.unlock()
        await log_audit(r.run_id, "run_unlocked", {})
        if r.inbox:
            r.inbox.push("unlock", "")
        return {"ok": True, "event": "unlock", "run_id": r.run_id}

    @app.post("/cleanup")
    async def cleanup() -> dict:
        to_remove = [rid for rid, r in server.runs().items() if r.status in CLEANABLE_RUN_STATUSES]
        for rid in to_remove:
            del server.runs()[rid]
        return {"ok": True, "cleaned": len(to_remove)}
