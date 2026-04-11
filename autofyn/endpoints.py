"""HTTP route handlers for the agent server.

Thin routing. `/start` wires up an ActiveRun + background task; the
control endpoints push events into the run's UserInbox; health
reads the TimeLock for per-run time info.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING

import httpx
from fastapi import FastAPI, HTTPException

from utils import db
from utils.constants import (
    ENV_KEY_CLAUDE_TOKEN,
    ENV_KEY_GIT_TOKEN,
    MAX_CONCURRENT_RUNS,
)
from utils.models import (
    ActiveRun,
    HealthResponse,
    HealthRunEntry,
    InjectRequest,
    StartRequest,
)

if TYPE_CHECKING:
    from server import AgentServer


def _merge_tokens_into_env(
    env: dict[str, str] | None,
    claude_token: str | None,
    git_token: str | None,
) -> dict[str, str] | None:
    """Merge per-run tokens into the env dict without touching os.environ."""
    if not claude_token and not git_token:
        return env
    merged: dict[str, str] = dict(env) if env is not None else {}
    if claude_token:
        merged[ENV_KEY_CLAUDE_TOKEN] = claude_token
    if git_token:
        merged[ENV_KEY_GIT_TOKEN] = git_token
    return merged


def register_routes(app: FastAPI, server: "AgentServer") -> None:
    """Register all HTTP route handlers on the FastAPI app."""

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
                entry.session_unlocked = r.time_lock.is_force_unlocked()
            runs_list.append(entry)
        return HealthResponse(
            status="running" if server.active_count() > 0 else "idle",
            active_runs=server.active_count(),
            max_concurrent=MAX_CONCURRENT_RUNS,
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
        if not body.prompt:
            raise HTTPException(
                status_code=422,
                detail="prompt is required — AutoFyn needs a task",
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

        active = ActiveRun(run_id=run_id)
        server.register_run(active)

        task = asyncio.create_task(server.execute_run(active, body))
        active.task = task
        task.add_done_callback(lambda t: server.on_task_done(active, t))
        return {"ok": True, "status": "starting", "run_id": run_id}

    # ── Control Signals ────────────────────────────────────────────────

    @app.post("/stop")
    async def stop(run_id: str | None = None):
        r = server.get_run_or_first(run_id)
        if not r.inbox:
            raise HTTPException(status_code=409, detail="Run not accepting signals")
        r.inbox.push("stop", "User stop via API")
        return {"ok": True, "event": "stop", "run_id": r.run_id}

    @app.post("/pause")
    async def pause(run_id: str | None = None):
        r = server.get_run_or_first(run_id)
        if not r.inbox:
            raise HTTPException(status_code=409, detail="Run not accepting signals")
        r.inbox.push("pause", "")
        return {"ok": True, "event": "pause", "run_id": r.run_id}

    @app.post("/resume")
    async def resume(run_id: str | None = None):
        """Unpause a paused run. Restart of terminated runs is not supported."""
        r = server.get_run_or_first(run_id)
        if not r.inbox:
            raise HTTPException(status_code=409, detail="Run not accepting signals")
        r.inbox.push("resume", "")
        return {"ok": True, "event": "resume", "run_id": r.run_id}

    @app.post("/inject")
    async def inject(body: InjectRequest, run_id: str | None = None):
        r = server.get_run_or_first(run_id)
        if not r.inbox:
            raise HTTPException(status_code=409, detail="Run not accepting signals")
        r.inbox.push("inject", body.payload or "")
        return {"ok": True, "event": "inject", "run_id": r.run_id}

    @app.post("/unlock")
    async def unlock(run_id: str | None = None):
        r = server.get_run_or_first(run_id)
        if not r.time_lock:
            raise HTTPException(status_code=409, detail="Run not accepting signals")
        r.time_lock.force_unlock()
        if r.inbox:
            r.inbox.push("unlock", "")
        return {"ok": True, "event": "unlock", "run_id": r.run_id}

    @app.post("/kill")
    async def kill(run_id: str | None = None):
        r = server.get_run_or_first(run_id)
        if r.task and not r.task.done():
            r.task.cancel()
        return {"ok": True, "event": "kill", "run_id": r.run_id}

    @app.post("/cleanup")
    async def cleanup():
        terminal = {
            "completed",
            "completed_no_changes",
            "stopped",
            "error",
            "crashed",
            "killed",
            "rate_limited",
        }
        to_remove = [rid for rid, r in server.runs().items() if r.status in terminal]
        for rid in to_remove:
            del server.runs()[rid]
        return {"ok": True, "cleaned": len(to_remove)}

    # ── Logs ───────────────────────────────────────────────────────────

    @app.get("/logs")
    async def get_logs(tail: int, run_id: str | None = None):
        """Return sandbox container logs for a run."""
        lines = await server.pool().get_logs(run_id, tail)
        return {"lines": lines, "total": len(lines)}

    # ── Branches (GitHub API proxy) ────────────────────────────────────

    @app.get("/branches")
    async def list_branches(repo: str, token: str):
        """List branches on the GitHub remote for the given repo.

        Called by the dashboard's StartRunModal to populate the "branch from"
        dropdown. The dashboard passes the git token it has in settings; we
        just proxy to the GitHub API. No sandbox needed because this runs
        before any run has started.
        """
        if "/" not in repo:
            raise HTTPException(status_code=400, detail="repo must be owner/name")
        url = f"https://api.github.com/repos/{repo}/branches"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, headers=headers, params={"per_page": 100})
        if resp.status_code >= 400:
            raise HTTPException(
                status_code=resp.status_code,
                detail=f"GitHub API error: {resp.text[:200]}",
            )
        data = resp.json()
        return [b["name"] for b in data if isinstance(b, dict) and "name" in b]
