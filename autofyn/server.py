"""AutoFyn agent HTTP server.

Orchestrates bootstrap → loop → teardown. Each run gets its own sandbox
container via SandboxPool for full isolation.
"""

import asyncio
import hmac
import logging
import os
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from starlette.responses import JSONResponse
import uvicorn

from config.loader import sandbox_config
from utils import db
from utils.constants import (
    MAX_CONCURRENT_RUNS,
    SANDBOX_CLONE_TIMEOUT_DEFAULT,
    SANDBOX_EXEC_TIMEOUT_DEFAULT,
    SANDBOX_HEALTH_TIMEOUT_DEFAULT,
    SERVER_HOST,
    SERVER_PORT,
)
from utils.prompts import PromptLoader
from utils.models import ActiveRun, ResumeRequest, StartRequest
from utils.run_helpers import (
    CapacityError,
    RunLookupError,
    active_count,
    check_capacity,
    get_run_or_first,
)
from sandbox_manager.pool import SandboxPool
from sandbox_manager.repo_ops import RepoOps
from core.bootstrap import Bootstrap
from core.session_runner import SessionRunner
from core.teardown import RunTeardown
from endpoints import register_routes

log = logging.getLogger("server")


class AgentServer:
    """HTTP server managing concurrent agent runs with per-run sandboxes."""

    def __init__(self) -> None:
        cfg = sandbox_config()
        self._health_timeout: int = cfg.get("health_timeout_sec", SANDBOX_HEALTH_TIMEOUT_DEFAULT)
        self._exec_timeout: int = cfg.get("exec_timeout_sec", SANDBOX_EXEC_TIMEOUT_DEFAULT)
        self._clone_timeout: int = cfg.get("clone_timeout_sec", SANDBOX_CLONE_TIMEOUT_DEFAULT)

        self._prompts = PromptLoader()
        self._pool = SandboxPool()
        self._runs: dict[str, ActiveRun] = {}

        self.app = FastAPI(title="AutoFyn Agent", lifespan=self._lifespan)
        self._internal_secret = os.environ.get("AGENT_INTERNAL_SECRET", "")
        self._setup_internal_auth()
        register_routes(self.app, self)

    def _setup_internal_auth(self) -> None:
        """Add internal secret authentication middleware if configured."""
        if not self._internal_secret:
            return
        secret = self._internal_secret

        @self.app.middleware("http")
        async def check_internal_secret(request, call_next):
            if request.url.path == "/health":
                return await call_next(request)
            provided = request.headers.get("X-Internal-Secret", "")
            if not hmac.compare_digest(provided, secret):
                return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
            return await call_next(request)

    @asynccontextmanager
    async def _lifespan(self, app: FastAPI):
        """Startup: connect DB. Shutdown: tear down sandboxes, close DB."""
        await db.init_db()
        crashed = await db.mark_crashed_runs()
        if crashed:
            log.info("Marked %d stale run(s) as crashed", crashed)
        log.info("Ready — waiting for start command on :%d", SERVER_PORT)
        yield
        await self._pool.destroy_all()
        await db.close_db()

    def _active_count(self) -> int:
        """Count non-terminal runs (including paused — they still hold sandbox resources)."""
        return active_count(self._runs)

    def _check_capacity(self) -> None:
        """Raise 409 if max concurrent runs reached."""
        try:
            check_capacity(self._runs, MAX_CONCURRENT_RUNS)
        except CapacityError as e:
            raise HTTPException(status_code=e.status_code, detail=e.detail) from e

    def _get_run(self, run_id: str) -> ActiveRun:
        """Look up a run or raise 404."""
        run = self._runs.get(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        return run

    def _get_run_or_first(self, run_id: str | None) -> ActiveRun:
        """Get specific run by id, or first running run. Raises 409 if none."""
        try:
            return get_run_or_first(self._runs, run_id)
        except RunLookupError as e:
            raise HTTPException(status_code=e.status_code, detail=e.detail) from e

    # ── Run Lifecycle ──

    async def _execute_run(self, active: ActiveRun, run_id: str, body: StartRequest) -> None:
        """Spin up sandbox → bootstrap → execute → teardown → destroy sandbox."""
        github_repo = body.github_repo
        if not github_repo:
            raise RuntimeError("github_repo is required — configure it in dashboard settings")
        budget = body.max_budget_usd or float(os.environ.get("MAX_BUDGET_USD", "0"))

        run_env = body.env or {}
        sandbox = await self._pool.create(run_id, self._health_timeout, body.env)
        try:
            repo_ops = RepoOps(sandbox, run_env)
            bootstrap = Bootstrap(repo_ops, sandbox)
            runner = SessionRunner(sandbox, self._prompts)
            teardown = RunTeardown(repo_ops)

            ctx, options, session, events, tracker, initial = await bootstrap.setup_new(
                run_id, body.prompt, budget, body.duration_minutes,
                body.base_branch, github_repo,
                self._exec_timeout, self._clone_timeout,
                body.model,
            )

            active.status = "running"
            active.events = events
            active.session = session
            active.run_context = ctx

            try:
                log.info("Run %s: starting agent loop", run_id)
                status = await runner.execute(
                    options, ctx, session, events, tracker, initial,
                )
                log.info("Run %s: loop returned status=%s", run_id, status)
            finally:
                events.stop_pulse_checker()

            log.info("Run %s: starting teardown", run_id)
            await teardown.finalize(ctx, status, self._exec_timeout)
            log.info("Run %s: teardown complete", run_id)
            active.status = status
        finally:
            active.events = None
            active.session = None
            await sandbox.close()
            await self._pool.destroy(run_id)

    async def _execute_resume(self, active: ActiveRun, body: ResumeRequest) -> None:
        """Spin up sandbox → bootstrap resume → execute → teardown → destroy sandbox."""
        run_id = body.run_id
        budget = body.max_budget_usd or float(os.environ.get("MAX_BUDGET_USD", "0"))

        run_env = body.env or {}
        sandbox = await self._pool.create(run_id, self._health_timeout, body.env)
        try:
            repo_ops = RepoOps(sandbox, run_env)
            bootstrap = Bootstrap(repo_ops, sandbox)
            runner = SessionRunner(sandbox, self._prompts)
            teardown = RunTeardown(repo_ops)

            ctx, options, session, events, tracker, initial = await bootstrap.setup_resume(
                run_id, budget, self._exec_timeout, self._clone_timeout, body.prompt,
                body.model,
            )

            active.status = "running"
            active.events = events
            active.session = session
            active.run_context = ctx

            try:
                log.info("Run %s: resuming agent loop", run_id)
                status = await runner.execute(
                    options, ctx, session, events, tracker, initial,
                )
                log.info("Run %s: loop returned status=%s", run_id, status)
            finally:
                events.stop_pulse_checker()

            log.info("Run %s: starting teardown", run_id)
            await teardown.finalize(ctx, status, self._exec_timeout)
            log.info("Run %s: teardown complete", run_id)
            active.status = status
        finally:
            active.events = None
            active.session = None
            await sandbox.close()
            await self._pool.destroy(run_id)

    def _on_task_done(self, active: ActiveRun, task: asyncio.Task) -> None:
        """Handle task completion or crash. Persists final status to DB."""
        ctx = active.run_context
        try:
            exc = task.exception()
            if exc:
                tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
                log.error("Run %s crashed:\n%s", active.run_id, tb)
                active.status = "crashed"
                active.error_message = str(exc)
                if active.run_id:
                    if ctx is not None:
                        asyncio.create_task(db.finish_run(
                            active.run_id, "crashed", None,
                            ctx.total_cost, ctx.total_input_tokens, ctx.total_output_tokens,
                            str(exc), None, None,
                            ctx.cache_creation_input_tokens, ctx.cache_read_input_tokens,
                        ))
                    else:
                        asyncio.create_task(db.update_run_status(active.run_id, "crashed"))
        except asyncio.CancelledError:
            active.status = "killed"
            active.error_message = "Cancelled"
            if active.run_id:
                if ctx is not None:
                    asyncio.create_task(db.finish_run(
                        active.run_id, "killed", None,
                        ctx.total_cost, ctx.total_input_tokens, ctx.total_output_tokens,
                        "Cancelled", None, None,
                        ctx.cache_creation_input_tokens, ctx.cache_read_input_tokens,
                    ))
                else:
                    asyncio.create_task(db.update_run_status(active.run_id, "killed"))
        finally:
            active.task = None


_server = AgentServer()
app = _server.app


def main() -> None:
    """Run the agent HTTP server."""
    logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT, log_level="info")


if __name__ == "__main__":
    main()
