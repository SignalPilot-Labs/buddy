"""Buddy agent HTTP server.

AgentServer wraps FastAPI and orchestrates bootstrap → loop → teardown.
Control events are pushed to the active EventBus.
"""

import asyncio
import hmac
import logging
import os
import time
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Path
from pydantic import BaseModel
from starlette.responses import JSONResponse
import uvicorn

from utils import db
from utils.constants import KILL_WAIT_SEC, PROMPT_SUMMARY_LIMIT, SERVER_HOST, SERVER_PORT
from utils.git import GitWorkspace
from utils.helpers import validate_branch_name
from utils.models import InjectRequest, ResumeRequest, StartRequest
from utils.prompts import PromptLoader
from core.bootstrap import RunBootstrap
from core.agent_loop import AgentLoop
from core.teardown import RunTeardown
from core.event_bus import EventBus
from tools.session import SessionGate
from run_manager import RunManager, MAX_CONCURRENT

log = logging.getLogger("server")


class _StartRateLimiter:
    """Simple sliding-window rate limiter for parallel/start."""
    def __init__(self, max_calls: int = 5, window_sec: float = 60.0):
        self._max = max_calls
        self._window = window_sec
        self._timestamps: list[float] = []

    def check(self) -> bool:
        now = time.monotonic()
        self._timestamps = [t for t in self._timestamps if now - t < self._window]
        if len(self._timestamps) >= self._max:
            return False
        self._timestamps.append(now)
        return True


_start_limiter = _StartRateLimiter()


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
    """HTTP server that controls the agent lifecycle.

    Orchestrates: bootstrap → agent_loop → teardown.
    Owns the active run state and event bus reference.
    """

    def __init__(self):
        self._git = GitWorkspace()
        self._prompts = PromptLoader()
        self._bootstrap = RunBootstrap(self._git)
        self._loop = AgentLoop(self._git, self._prompts)
        self._teardown = RunTeardown(self._git)
        self._task: asyncio.Task | None = None
        self._events: EventBus | None = None
        self._session: SessionGate | None = None
        self._bootstrapping = False
        self.current_run_id: str | None = None
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
        # Graceful shutdown: stop all running workers before closing
        if not _is_worker():
            active_slots = [s for s in _run_manager.get_all_slots() if s.status in ("starting", "running")]
            if active_slots:
                log.info("Shutting down %d active worker(s)...", len(active_slots))
                for slot in active_slots:
                    try:
                        await _run_manager.send_signal(slot.container_name, "stop", {"reason": "Orchestrator shutdown"})
                    except Exception as e:
                        log.warning("Failed to stop worker %s: %s", slot.container_name, e)
        await db.close_db()

    # ── Run Lifecycle ──

    async def _run_agent(
        self, custom_prompt: str | None, max_budget: float,
        duration_minutes: float, base_branch: str, github_repo: str,
    ) -> None:
        """Bootstrap → execute → teardown for a new run."""
        self._bootstrapping = True
        ctx, options, session, events, logger, initial = await self._bootstrap.setup_new(
            custom_prompt, max_budget, duration_minutes, base_branch, github_repo,
        )
        self.current_run_id = ctx.run_id
        self._events = events
        self._session = session
        self._bootstrapping = False
        asyncio.get_event_loop().run_in_executor(None, self._git.install_deps)

        try:
            status = await self._loop.execute(options, ctx, session, events, initial, custom_prompt)
        finally:
            events.stop_pulse_checker()
            self._events = None
            self._session = None

        await self._teardown.finalize(ctx, status)
        self.current_run_id = None

    async def _resume_agent(self, run_id: str, max_budget: float, prompt: str | None = None) -> None:
        """Bootstrap → execute → teardown for a resumed run."""
        self._bootstrapping = True
        ctx, options, session, events, logger, initial = await self._bootstrap.setup_resume(run_id, max_budget, prompt)
        self.current_run_id = ctx.run_id
        self._events = events
        self._session = session
        self._bootstrapping = False
        asyncio.get_event_loop().run_in_executor(None, self._git.install_deps)

        try:
            status = await self._loop.execute(options, ctx, session, events, initial, None)
        finally:
            events.stop_pulse_checker()
            self._events = None
            self._session = None

        await self._teardown.finalize(ctx, status)
        self.current_run_id = None

    # ── Helpers ──

    def _push_event(self, event: str, payload: str | None) -> None:
        """Push an event to the active EventBus."""
        if self._events:
            self._events.push(event, payload)

    def _require_running(self) -> None:
        """Raise 409 if no run is in progress."""
        if self.current_run_id is None:
            raise HTTPException(status_code=409, detail="No run in progress")

    def _require_idle(self) -> None:
        """Raise 409 if a run is already in progress."""
        if self.current_run_id is not None:
            raise HTTPException(status_code=409, detail=f"Run already in progress: {self.current_run_id}")

    def _inject_credentials(self, body) -> None:
        """Set environment variables from monitor-provided credentials."""
        if body.claude_token:
            os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = body.claude_token
        if body.git_token:
            os.environ["GIT_TOKEN"] = body.git_token

    def _on_task_done(self, task: asyncio.Task) -> None:
        """Callback when the agent task finishes or crashes."""
        try:
            exc = task.exception()
            if exc:
                tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
                log.error("Run task crashed:\n%s", tb)
        except asyncio.CancelledError:
            pass
        finally:
            # Always clean up so new runs can start after a crash
            self.current_run_id = None
            self._task = None
            self._events = None
            self._session = None
            self._bootstrapping = False

    # ── Routes ──

    def _register_routes(self) -> None:
        """Register all HTTP routes."""
        app = self.app

        @app.get("/health")
        async def health():
            if self._bootstrapping:
                return {"status": "bootstrapping", "current_run_id": None}
            if not self.current_run_id:
                return {"status": "idle", "current_run_id": None}
            result: dict = {"status": "running", "current_run_id": self.current_run_id}
            if self._session:
                result["elapsed_minutes"] = round(self._session.elapsed_minutes(), 1)
                result["time_remaining"] = self._session.time_remaining_str()
                result["session_unlocked"] = self._session.is_unlocked()
            return result

        @app.post("/start")
        async def start_run(body: StartRequest = StartRequest()):
            self._require_idle()
            self._inject_credentials(body)
            budget = body.max_budget_usd if body.max_budget_usd else float(os.environ.get("MAX_BUDGET_USD", "0"))

            self._task = asyncio.create_task(self._run_agent(
                body.prompt, budget, body.duration_minutes, body.base_branch,
                body.github_repo or "",
            ))
            self._task.add_done_callback(self._on_task_done)

            return {
                "ok": True, "status": "bootstrapping",
                "prompt": body.prompt[:PROMPT_SUMMARY_LIMIT] if body.prompt else None,
                "max_budget_usd": budget,
                "duration_minutes": body.duration_minutes,
                "base_branch": body.base_branch,
            }

        @app.post("/resume")
        async def resume_run(body: ResumeRequest):
            self._require_idle()
            self._inject_credentials(body)
            budget = body.max_budget_usd or float(os.environ.get("MAX_BUDGET_USD", "0"))

            self._task = asyncio.create_task(self._resume_agent(body.run_id, budget, body.prompt))
            self._task.add_done_callback(self._on_task_done)
            return {"ok": True, "status": "bootstrapping", "run_id": body.run_id, "resumed": True}

        @app.post("/pause")
        async def pause():
            self._require_running()
            self._push_event("pause", None)
            return {"ok": True, "event": "pause"}

        @app.post("/resume_signal")
        async def resume_signal():
            self._require_running()
            self._push_event("resume", None)
            return {"ok": True, "event": "resume"}

        @app.post("/inject")
        async def inject(body: InjectRequest = InjectRequest()):
            self._require_running()
            self._push_event("inject", body.payload)
            return {"ok": True, "event": "inject"}

        @app.post("/unlock")
        async def unlock():
            self._require_running()
            self._push_event("unlock", None)
            return {"ok": True, "event": "unlock"}

        @app.post("/stop")
        async def stop():
            self._require_running()
            self._push_event("stop", "Operator stop via API")
            return {"ok": True, "event": "stop"}

        @app.post("/kill")
        async def kill():
            if self._task is None or self.current_run_id is None:
                raise HTTPException(status_code=409, detail="No run in progress")
            run_id = self.current_run_id
            self._task.cancel()
            await asyncio.sleep(KILL_WAIT_SEC)
            try:
                await db.finish_run(run_id, "killed", None, None, None, None, None, None, None)
            except Exception as e:
                log.error("Failed to mark run %s as killed in DB: %s", run_id, e)
            self.current_run_id = None
            return {"ok": True, "event": "kill", "run_id": run_id}

        @app.get("/branches")
        async def list_branches():
            if not self._git.is_ready():
                return []
            try:
                output = self._git.run_git(["branch", "-r", "--format", "%(refname:short)"])
                branches = [b.replace("origin/", "") for b in output.strip().split("\n") if b.strip() and "HEAD" not in b]
                return sorted(set(branches))
            except RuntimeError as e:
                log.warning("Failed to list branches: %s", e)
                return []

        @app.get("/diff/live")
        async def get_live_diff():
            if not self._git.is_ready():
                return {"files": []}
            try:
                base = "main"
                if self.current_run_id:
                    run_base = await db.get_run_base_branch(self.current_run_id)
                    if run_base:
                        base = run_base
                stats = self._git.get_branch_diff_live(base)
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
            if not self._git.is_ready():
                return {"files": []}
            try:
                validate_branch_name(branch)
                validate_branch_name(base)
                stats = self._git.get_branch_diff(branch, base)
                return {
                    "files": stats, "total_files": len(stats),
                    "total_added": sum(f["added"] for f in stats),
                    "total_removed": sum(f["removed"] for f in stats),
                }
            except RuntimeError as e:
                log.warning("Branch diff failed: %s", e)
                return {"files": []}

        # ── Parallel Runner Endpoints ──

        @app.get("/parallel/runs")
        async def parallel_list_runs():
            return [RunManager.to_dict(s) for s in _run_manager.get_all_slots()]

        @app.post("/parallel/start")
        async def parallel_start(body: ParallelStartRequest):
            if not _start_limiter.check():
                raise HTTPException(status_code=429, detail="Too many start requests. Max 5 per minute.")
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
        async def parallel_get_run(run_id: str = Path(min_length=8, max_length=8, pattern=r"^[a-f0-9]{8}$")):
            slot = _run_manager.get_slot_by_run_id(run_id)
            if not slot:
                raise HTTPException(status_code=404, detail="Run not found in parallel slots")
            return RunManager.to_dict(slot)

        @app.get("/parallel/runs/{run_id}/health")
        async def parallel_run_health(run_id: str = Path(min_length=8, max_length=8, pattern=r"^[a-f0-9]{8}$")):
            slot = _run_manager.get_slot_by_run_id(run_id)
            if not slot:
                raise HTTPException(status_code=404, detail="Run not found")
            try:
                return await _run_manager.get_worker_health(slot.container_name)
            except Exception as e:
                raise HTTPException(status_code=502, detail=str(e))

        @app.post("/parallel/runs/{run_id}/stop")
        async def parallel_stop(run_id: str = Path(min_length=8, max_length=8, pattern=r"^[a-f0-9]{8}$")):
            slot = _run_manager.get_slot_by_run_id(run_id)
            if not slot:
                raise HTTPException(status_code=404, detail="Run not found")
            return await _run_manager.stop_run(slot.container_name, "Stopped via dashboard")

        @app.post("/parallel/runs/{run_id}/kill")
        async def parallel_kill(run_id: str = Path(min_length=8, max_length=8, pattern=r"^[a-f0-9]{8}$")):
            slot = _run_manager.get_slot_by_run_id(run_id)
            if not slot:
                raise HTTPException(status_code=404, detail="Run not found")
            return await _run_manager.kill_run(slot.container_name)

        @app.post("/parallel/runs/{run_id}/pause")
        async def parallel_pause(run_id: str = Path(min_length=8, max_length=8, pattern=r"^[a-f0-9]{8}$")):
            slot = _run_manager.get_slot_by_run_id(run_id)
            if not slot:
                raise HTTPException(status_code=404, detail="Run not found")
            return await _run_manager.pause_run(slot.container_name)

        @app.post("/parallel/runs/{run_id}/resume")
        async def parallel_resume(run_id: str = Path(min_length=8, max_length=8, pattern=r"^[a-f0-9]{8}$")):
            slot = _run_manager.get_slot_by_run_id(run_id)
            if not slot:
                raise HTTPException(status_code=404, detail="Run not found")
            return await _run_manager.resume_run(slot.container_name)

        @app.post("/parallel/runs/{run_id}/inject")
        async def parallel_inject(run_id: str = Path(min_length=8, max_length=8, pattern=r"^[a-f0-9]{8}$"), body: ParallelSignalRequest = ParallelSignalRequest()):
            slot = _run_manager.get_slot_by_run_id(run_id)
            if not slot:
                raise HTTPException(status_code=404, detail="Run not found")
            return await _run_manager.inject_prompt(slot.container_name, {"payload": body.payload})

        @app.post("/parallel/runs/{run_id}/unlock")
        async def parallel_unlock(run_id: str = Path(min_length=8, max_length=8, pattern=r"^[a-f0-9]{8}$")):
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
