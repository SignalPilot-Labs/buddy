"""HTTP route handlers for the agent server.

All FastAPI routes are registered here via register_routes().
"""

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING

from fastapi import FastAPI, HTTPException

from utils import db
from utils.constants import MAX_CONCURRENT_RUNS
from utils.models import ActiveRun, HealthResponse, HealthRunEntry, StartRequest, ResumeRequest, InjectRequest
from utils.run_helpers import merge_tokens_into_env

if TYPE_CHECKING:
    from server import AgentServer


def register_routes(app: FastAPI, server: AgentServer) -> None:
    """Register all HTTP route handlers on the FastAPI app."""

    @app.get("/health")
    async def health() -> HealthResponse:
        """Agent health with per-run details."""
        runs_list: list[HealthRunEntry] = []
        for r in server._runs.values():
            if not r.run_id:
                continue
            entry = HealthRunEntry(run_id=r.run_id, status=r.status, started_at=r.started_at)
            if r.session:
                entry.elapsed_minutes = round(r.session.elapsed_minutes(), 1)
                entry.time_remaining = r.session.time_remaining_str()
                entry.session_unlocked = r.session.is_unlocked()
            runs_list.append(entry)
        return HealthResponse(
            status="running" if server._active_count() > 0 else "idle",
            active_runs=server._active_count(),
            max_concurrent=MAX_CONCURRENT_RUNS,
            runs=runs_list,
        )

    @app.post("/start")
    async def start_run(body: StartRequest):
        server._check_capacity()

        body.env = merge_tokens_into_env(body.env, body.claude_token, body.git_token)

        run_id = str(uuid.uuid4())
        if not body.github_repo:
            raise HTTPException(status_code=422, detail="github_repo is required")
        github_repo = body.github_repo
        await db.create_run_starting(
            run_id, body.prompt, body.duration_minutes, body.base_branch, github_repo,
            body.model,
        )

        active = ActiveRun(run_id=run_id)
        server._runs[run_id] = active

        task = asyncio.create_task(server._execute_run(active, run_id, body))
        active.task = task
        task.add_done_callback(lambda t: server._on_task_done(active, t))
        return {"ok": True, "status": "starting", "run_id": run_id}

    # ── Control Signals ──

    @app.post("/stop")
    async def stop(run_id: str | None = None):
        r = server._get_run_or_first(run_id)
        if not r.events:
            raise HTTPException(status_code=409, detail="Run not accepting signals")
        r.events.push("stop", "Operator stop via API")
        return {"ok": True, "event": "stop", "run_id": r.run_id}

    @app.post("/pause")
    async def pause(run_id: str | None = None):
        r = server._get_run_or_first(run_id)
        if not r.events:
            raise HTTPException(status_code=409, detail="Run not accepting signals")
        r.events.push("pause", None)
        return {"ok": True, "event": "pause", "run_id": r.run_id}

    @app.post("/resume")
    async def resume(body: ResumeRequest | None = None, run_id: str | None = None):
        """Unpause a paused run, or restart a completed/stopped run."""
        rid = (body.run_id if body else None) or run_id
        active = server._runs.get(rid or "") if rid else None

        if active and active.status == "paused" and active.events:
            active.events.push("resume", None)
            return {"ok": True, "event": "resume", "run_id": active.run_id}

        if not body or not body.run_id:
            raise HTTPException(status_code=422, detail="run_id is required for restart")

        server._check_capacity()
        body.env = merge_tokens_into_env(body.env, body.claude_token, body.git_token)

        active_run = ActiveRun(run_id=body.run_id)
        server._runs[body.run_id] = active_run

        task = asyncio.create_task(
            server._execute_resume(active_run, body)
        )
        active_run.task = task
        task.add_done_callback(lambda t: server._on_task_done(active_run, t))
        return {"ok": True, "status": "starting", "run_id": body.run_id}

    @app.post("/inject")
    async def inject(body: InjectRequest, run_id: str | None = None):
        r = server._get_run_or_first(run_id)
        if not r.events:
            raise HTTPException(status_code=409, detail="Run not accepting signals")
        r.events.push("inject", body.payload)
        return {"ok": True, "event": "inject", "run_id": r.run_id}

    @app.post("/unlock")
    async def unlock(run_id: str | None = None):
        r = server._get_run_or_first(run_id)
        if not r.events:
            raise HTTPException(status_code=409, detail="Run not accepting signals")
        r.events.push("unlock", None)
        return {"ok": True, "event": "unlock", "run_id": r.run_id}

    @app.post("/kill")
    async def kill(run_id: str | None = None):
        r = server._get_run_or_first(run_id)
        if r.task and not r.task.done():
            r.task.cancel()
        return {"ok": True, "event": "kill", "run_id": r.run_id}

    @app.post("/cleanup")
    async def cleanup():
        terminal = {"completed", "stopped", "error", "crashed", "killed", "rate_limited"}
        to_remove = [rid for rid, r in server._runs.items() if r.status in terminal]
        for rid in to_remove:
            del server._runs[rid]
        return {"ok": True, "cleaned": len(to_remove)}

    # ── Logs ──

    @app.get("/logs")
    async def get_logs(tail: int, run_id: str | None = None):
        """Return sandbox container logs for a run."""
        lines = await server._pool.get_logs(run_id, tail)
        return {"lines": lines, "total": len(lines)}

    # ── Branches / Diff ──

    @app.get("/branches")
    async def list_branches():
        return []  # TODO: implement via per-run sandbox

    @app.get("/diff/live")
    async def get_live_diff():
        return {"files": []}  # TODO: implement via per-run sandbox

    @app.get("/diff/{branch}")
    async def get_branch_diff(branch: str, base: str = "main"):
        return {"files": []}  # TODO: implement via per-run sandbox
