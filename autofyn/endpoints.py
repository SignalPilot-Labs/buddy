"""HTTP route handlers for the agent server.

All FastAPI routes are registered here via register_routes().
"""

from __future__ import annotations

import asyncio
import os
import uuid
from typing import TYPE_CHECKING

from fastapi import FastAPI, HTTPException

from utils import db
from utils.constants import MAX_CONCURRENT_RUNS
from utils.models import ActiveRun, StartRequest, InjectRequest

if TYPE_CHECKING:
    from server import AgentServer


def register_routes(app: FastAPI, server: AgentServer) -> None:
    """Register all HTTP route handlers on the FastAPI app."""

    @app.get("/health")
    async def health():
        return {
            "status": "running" if server._active_count() > 0 else "idle",
            "active_runs": server._active_count(),
            "max_concurrent": MAX_CONCURRENT_RUNS,
        }

    @app.get("/status")
    async def status(run_id: str | None = None):
        """Per-run status if run_id given, otherwise all runs."""
        if run_id:
            r = server._get_run(run_id)
            result: dict = {"run_id": r.run_id, "status": r.status, "error_message": r.error_message}
            if r.session:
                result["elapsed_minutes"] = round(r.session.elapsed_minutes(), 1)
                result["time_remaining"] = r.session.time_remaining_str()
                result["session_unlocked"] = r.session.is_unlocked()
            return result
        return {
            "active": server._active_count(),
            "max_concurrent": MAX_CONCURRENT_RUNS,
            "runs": [
                {"run_id": r.run_id, "status": r.status, "started_at": r.started_at}
                for r in server._runs.values()
            ],
        }

    @app.post("/start")
    async def start_run(body: StartRequest):
        server._check_capacity()

        # Set credentials in env for this process. Tokens are per-account,
        # not per-run — each sandbox gets them via RepoOps._auth_env().
        if body.claude_token:
            os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = body.claude_token
        if body.git_token:
            os.environ["GIT_TOKEN"] = body.git_token

        run_id = str(uuid.uuid4())
        github_repo = body.github_repo or os.environ.get("GITHUB_REPO", "")
        await db.create_run_starting(
            run_id, body.prompt, body.duration_minutes, body.base_branch, github_repo,
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

    @app.post("/resume_signal")
    async def resume_signal(run_id: str | None = None):
        r = server._get_run_or_first(run_id)
        if not r.events:
            raise HTTPException(status_code=409, detail="Run not accepting signals")
        r.events.push("resume", None)
        return {"ok": True, "event": "resume", "run_id": r.run_id}

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
