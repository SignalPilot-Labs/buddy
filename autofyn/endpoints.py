"""HTTP route handlers for the agent server.

All FastAPI routes are registered here via register_routes().
The server instance is passed in to access shared state.
"""

import asyncio
import logging
import os

from fastapi import FastAPI, HTTPException

from utils import db
from utils.constants import (
    PROMPT_SUMMARY_LIMIT,
    WORK_DIR,
)
from utils.helpers import validate_branch_name
from utils.models import InjectRequest, ResumeRequest, StartRequest

log = logging.getLogger("server")


def register_routes(app: FastAPI, server) -> None:
    """Register all HTTP route handlers on the FastAPI app."""

    @app.get("/health")
    async def health():
        if server._bootstrapping:
            return {"status": "bootstrapping", "current_run_id": None}
        if not server.current_run_id:
            return {"status": "idle", "current_run_id": None}
        result: dict = {"status": "running", "current_run_id": server.current_run_id}
        if server._session:
            result["elapsed_minutes"] = round(server._session.elapsed_minutes(), 1)
            result["time_remaining"] = server._session.time_remaining_str()
            result["session_unlocked"] = server._session.is_unlocked()
        return result

    @app.post("/start")
    async def start_run(body: StartRequest = StartRequest()):
        server._require_idle()
        server._inject_credentials(body)
        budget = body.max_budget_usd if body.max_budget_usd else float(os.environ.get("MAX_BUDGET_USD", "0"))

        server._task = asyncio.create_task(server._run_agent(
            body.prompt, budget, body.duration_minutes, body.base_branch,
            body.github_repo or "",
        ))
        server._task.add_done_callback(server._on_task_done)

        return {
            "ok": True, "status": "bootstrapping",
            "prompt": body.prompt[:PROMPT_SUMMARY_LIMIT] if body.prompt else None,
            "max_budget_usd": budget,
            "duration_minutes": body.duration_minutes,
            "base_branch": body.base_branch,
        }

    @app.post("/resume")
    async def resume_run(body: ResumeRequest):
        server._require_idle()
        server._inject_credentials(body)
        budget = body.max_budget_usd or float(os.environ.get("MAX_BUDGET_USD", "0"))

        server._task = asyncio.create_task(server._resume_agent(body.run_id, budget, body.prompt))
        server._task.add_done_callback(server._on_task_done)
        return {"ok": True, "status": "bootstrapping", "run_id": body.run_id, "resumed": True}

    @app.post("/pause")
    async def pause():
        server._require_running()
        server._push_event("pause", None)
        return {"ok": True, "event": "pause"}

    @app.post("/resume_signal")
    async def resume_signal():
        server._require_running()
        server._push_event("resume", None)
        return {"ok": True, "event": "resume"}

    @app.post("/inject")
    async def inject(body: InjectRequest = InjectRequest()):
        server._require_running()
        server._push_event("inject", body.payload)
        return {"ok": True, "event": "inject"}

    @app.post("/unlock")
    async def unlock():
        server._require_running()
        server._push_event("unlock", None)
        return {"ok": True, "event": "unlock"}

    @app.post("/stop")
    async def stop():
        server._require_running()
        server._push_event("stop", "Operator stop via API")
        return {"ok": True, "event": "stop"}

    @app.post("/kill")
    async def kill():
        if server._task is None or server.current_run_id is None:
            raise HTTPException(status_code=409, detail="No run in progress")
        run_id = server.current_run_id
        server._task.cancel()
        # Don't call finish_run here — the CancelledError in agent_loop
        # triggers teardown which calls finish_run. _on_task_done cleans up state.
        return {"ok": True, "event": "kill", "run_id": run_id}

    @app.get("/branches")
    async def list_branches():
        if not server._repo_ops.is_ready():
            return []
        try:
            output = await server._repo_ops.run_git(
                ["branch", "-r", "--format", "%(refname:short)"], server._exec_timeout, WORK_DIR,
            )
            branches = [
                b.replace("origin/", "")
                for b in output.strip().split("\n")
                if b.strip() and "HEAD" not in b
            ]
            return sorted(set(branches))
        except RuntimeError as e:
            log.warning("Failed to list branches: %s", e)
            return []

    @app.get("/diff/live")
    async def get_live_diff():
        if not server._repo_ops.is_ready():
            return {"files": []}
        try:
            base = "main"
            if server.current_run_id:
                run_base = await db.get_run_base_branch(server.current_run_id)
                if run_base:
                    base = run_base
            stats = await server._repo_ops.get_branch_diff_live(base, server._exec_timeout)
            return {
                "files": stats, "total_files": len(stats),
                "total_added": sum(f["added"] for f in stats),
                "total_removed": sum(f["removed"] for f in stats),
            }
        except RuntimeError as e:
            log.warning("Live diff failed: %s", e)
            return {"files": []}

    @app.get("/diff/{branch}")
    async def get_branch_diff(branch: str, base: str = "main"):
        if not server._repo_ops.is_ready():
            return {"files": []}
        try:
            validate_branch_name(branch)
            validate_branch_name(base)
            stats = await server._repo_ops.get_branch_diff(branch, base, server._exec_timeout)
            return {
                "files": stats, "total_files": len(stats),
                "total_added": sum(f["added"] for f in stats),
                "total_removed": sum(f["removed"] for f in stats),
            }
        except RuntimeError as e:
            log.warning("Branch diff failed: %s", e)
            return {"files": []}
