"""Buddy agent HTTP server.

AgentServer wraps FastAPI and exposes health, git diff, and parallel runner endpoints.
"""

import hmac
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from starlette.responses import JSONResponse
import uvicorn

from utils import db
from utils.constants import SERVER_HOST, SERVER_PORT
from utils.git import GitWorkspace
from utils.helpers import validate_branch_name
from run_manager import RunManager, MAX_CONCURRENT

log = logging.getLogger("server")


class ParallelStartRequest(BaseModel):
    prompt: str | None = None
    max_budget_usd: float = 0
    duration_minutes: float = 0
    base_branch: str = "main"
    claude_token: str | None = None
    git_token: str | None = None
    github_repo: str | None = None


class ParallelSignalRequest(BaseModel):
    payload: str | None = None


class AgentServer:
    """HTTP server that exposes health, git diff, and parallel runner endpoints."""

    def __init__(self):
        self._git = GitWorkspace()
        self.app = FastAPI(title="Buddy Agent", lifespan=self._lifespan)
        self._internal_secret = os.environ.get("AGENT_INTERNAL_SECRET", "")
        self._setup_internal_auth()
        self._register_routes()

    def _setup_internal_auth(self) -> None:
        """Add internal secret authentication middleware if configured."""
        if not self._internal_secret:
            return
        secret = self._internal_secret

        @self.app.middleware("http")
        async def check_internal_secret(request, call_next):
            # Health endpoint is unauthenticated (Docker healthcheck)
            if request.url.path == "/health":
                return await call_next(request)
            provided = request.headers.get("X-Internal-Secret", "")
            if not hmac.compare_digest(provided, secret):
                return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
            return await call_next(request)

    @asynccontextmanager
    async def _lifespan(self, app: FastAPI):
        """Startup: connect DB. Shutdown: close DB."""
        await db.init_db()
        if not _is_worker():
            crashed = await db.mark_crashed_runs()
            if crashed:
                log.info("Marked %d stale run(s) as crashed", crashed)
            orphans = await _run_manager.cleanup_orphans()
            if orphans:
                log.info("Cleaned up %d orphaned worker containers", orphans)
        log.info("Ready — waiting for start command on :%d", SERVER_PORT)
        yield
        await db.close_db()

    # ── Routes ──

    def _register_routes(self) -> None:
        """Register all HTTP routes."""
        app = self.app

        @app.get("/health")
        async def health():
            slots = _run_manager.get_all_slots()
            active = any(s.status == "running" for s in slots)
            status = "running" if active else "idle"
            return {"status": status, "current_run_id": None}

        @app.get("/branches")
        async def list_branches():
            try:
                self._git.setup_auth()
                output = self._git.run_git(["branch", "-r", "--format", "%(refname:short)"])
                branches = [b.replace("origin/", "") for b in output.strip().split("\n") if b.strip() and "HEAD" not in b]
                return sorted(set(branches))
            except Exception as e:
                log.warning("Failed to list branches: %s", e)
                return ["main"]

        @app.get("/diff/live")
        async def get_live_diff():
            try:
                self._git.setup_auth()
                stats = self._git.get_branch_diff_live("main")
                return {
                    "files": stats, "total_files": len(stats),
                    "total_added": sum(f["added"] for f in stats),
                    "total_removed": sum(f["removed"] for f in stats),
                }
            except Exception as e:
                log.warning("Live diff failed: %s", e)
                return {"files": [], "error": "Failed to compute diff"}

        @app.get("/diff/{branch}")
        async def get_branch_diff(branch: str, base: str = "main"):
            try:
                validate_branch_name(branch)
                validate_branch_name(base)
                self._git.setup_auth()
                stats = self._git.get_branch_diff(branch, base)
                return {
                    "files": stats, "total_files": len(stats),
                    "total_added": sum(f["added"] for f in stats),
                    "total_removed": sum(f["removed"] for f in stats),
                }
            except Exception as e:
                log.warning("Branch diff failed: %s", e)
                return {"files": [], "error": "Failed to compute diff"}

        # ── Parallel Runner Endpoints ──

        @app.get("/parallel/runs")
        async def parallel_list_runs():
            return [RunManager.to_dict(s) for s in _run_manager.get_all_slots()]

        @app.post("/parallel/start")
        async def parallel_start(body: ParallelStartRequest):
            creds = {}
            if body.claude_token:
                creds["claude_token"] = body.claude_token
            if body.git_token:
                creds["git_token"] = body.git_token
            if body.github_repo:
                creds["github_repo"] = body.github_repo
            try:
                slot = await _run_manager.start_run(
                    prompt=body.prompt,
                    max_budget_usd=body.max_budget_usd,
                    duration_minutes=body.duration_minutes,
                    base_branch=body.base_branch,
                    credentials=creds,
                )
                return RunManager.to_dict(slot)
            except RuntimeError as e:
                raise HTTPException(status_code=409, detail=str(e))

        @app.get("/parallel/status")
        async def parallel_status():
            slots = _run_manager.get_all_slots()
            return {
                "total_slots": len(slots),
                "active": _run_manager.active_count(),
                "max_concurrent": MAX_CONCURRENT,
                "slots": [RunManager.to_dict(s) for s in slots],
            }

        @app.get("/parallel/runs/{run_id}")
        async def parallel_get_run(run_id: str):
            slot = _run_manager.get_slot_by_run_id(run_id)
            if not slot:
                raise HTTPException(status_code=404, detail="Run not found in parallel slots")
            return RunManager.to_dict(slot)

        @app.get("/parallel/runs/{run_id}/health")
        async def parallel_run_health(run_id: str):
            slot = _run_manager.get_slot_by_run_id(run_id)
            if not slot:
                raise HTTPException(status_code=404, detail="Run not found")
            try:
                return await _run_manager.get_worker_health(slot.container_name)
            except Exception as e:
                raise HTTPException(status_code=502, detail=str(e))

        @app.post("/parallel/runs/{run_id}/stop")
        async def parallel_stop(run_id: str):
            slot = _run_manager.get_slot_by_run_id(run_id)
            if not slot:
                raise HTTPException(status_code=404, detail="Run not found")
            return await _run_manager.stop_run(slot.container_name, "Stopped via dashboard")

        @app.post("/parallel/runs/{run_id}/kill")
        async def parallel_kill(run_id: str):
            slot = _run_manager.get_slot_by_run_id(run_id)
            if not slot:
                raise HTTPException(status_code=404, detail="Run not found")
            return await _run_manager.kill_run(slot.container_name)

        @app.post("/parallel/runs/{run_id}/pause")
        async def parallel_pause(run_id: str):
            slot = _run_manager.get_slot_by_run_id(run_id)
            if not slot:
                raise HTTPException(status_code=404, detail="Run not found")
            return await _run_manager.pause_run(slot.container_name)

        @app.post("/parallel/runs/{run_id}/resume")
        async def parallel_resume(run_id: str):
            slot = _run_manager.get_slot_by_run_id(run_id)
            if not slot:
                raise HTTPException(status_code=404, detail="Run not found")
            return await _run_manager.resume_run(slot.container_name)

        @app.post("/parallel/runs/{run_id}/inject")
        async def parallel_inject(run_id: str, body: ParallelSignalRequest = ParallelSignalRequest()):
            slot = _run_manager.get_slot_by_run_id(run_id)
            if not slot:
                raise HTTPException(status_code=404, detail="Run not found")
            return await _run_manager.inject_prompt(slot.container_name, {"payload": body.payload})

        @app.post("/parallel/runs/{run_id}/unlock")
        async def parallel_unlock(run_id: str):
            slot = _run_manager.get_slot_by_run_id(run_id)
            if not slot:
                raise HTTPException(status_code=404, detail="Run not found")
            return await _run_manager.unlock_run(slot.container_name)

        @app.post("/parallel/cleanup")
        async def parallel_cleanup():
            cleaned = _run_manager.cleanup_all_finished(remove_volumes=True)
            return {"ok": True, "cleaned": cleaned}


def _is_worker() -> bool:
    """Check if this container is a worker (not orchestrator)."""
    hostname = os.environ.get("HOSTNAME", "")
    return hostname.startswith("buddy-worker-") or os.environ.get("WORKER_MODE") == "1"

_run_manager = RunManager()

_server = AgentServer()
app = _server.app


def main():
    """Run the agent HTTP server."""
    logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT, log_level="info")


if __name__ == "__main__":
    main()
