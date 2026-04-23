"""Route handlers for run lifecycle: health and start."""

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING

from fastapi import FastAPI, HTTPException

from db.constants import RUN_STATUS_STARTING
from endpoints.helpers import _merge_tokens_into_env
from prompts.loader import load_markdown
from utils import db
from utils.constants import max_concurrent_runs
from utils.models import (
    ActiveRun,
    HealthResponse,
    HealthRunEntry,
    StartRequest,
)

if TYPE_CHECKING:
    from server import AgentServer


def register_run_routes(app: FastAPI, server: "AgentServer") -> None:
    """Register health and start_run route handlers."""

    @app.get("/health")
    async def health() -> HealthResponse:
        """Agent health with per-run details."""
        runs_list: list[HealthRunEntry] = []
        for r in server.runs().values():
            if not r.run_id:
                continue
            entry = HealthRunEntry(
                run_id=r.run_id,
                status=r.status,
                started_at=r.started_at,
            )
            if r.time_lock:
                entry.elapsed_minutes = round(r.time_lock.elapsed_minutes(), 1)
                entry.time_remaining = r.time_lock.time_remaining_str()
                entry.run_unlocked = not r.time_lock.locked
            runs_list.append(entry)
        return HealthResponse(
            status="running" if server.active_count() > 0 else "idle",
            active_runs=server.active_count(),
            max_concurrent=max_concurrent_runs(),
            runs=runs_list,
        )

    @app.post("/start")
    async def start_run(body: StartRequest):
        """Start a new run — bootstraps a sandbox and kicks off the round loop."""
        server.ensure_capacity()

        body.env = _merge_tokens_into_env(
            body.env,
            body.claude_token,
            body.git_token,
        )

        if not body.github_repo:
            raise HTTPException(
                status_code=422,
                detail="github_repo is required",
            )
        if body.preset:
            body.prompt = load_markdown(f"starter/{body.preset}")
        if not body.prompt:
            raise HTTPException(
                status_code=422,
                detail="prompt or preset is required — AutoFyn needs a task",
            )

        run_id = str(uuid.uuid4())
        await db.create_run_starting(
            run_id,
            body.prompt,
            body.duration_minutes,
            body.base_branch,
            body.github_repo,
            body.model,
        )

        await db.log_audit(run_id, "run_starting", {"repo": body.github_repo})

        active = ActiveRun(run_id=run_id)
        server.register_run(active)

        task = asyncio.create_task(server.execute_run(active, body))
        active.task = task
        task.add_done_callback(lambda t: server.on_task_done(active, t))
        return {"ok": True, "status": RUN_STATUS_STARTING, "run_id": run_id}
