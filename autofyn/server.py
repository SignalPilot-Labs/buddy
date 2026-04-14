"""AutoFyn agent HTTP server.

Orchestrates bootstrap → round loop → teardown. Each run gets its own
sandbox container via SandboxPool for isolation. Round-based execution:
the Python `lifecycle.round_loop` is the long-running thing — each
round starts a fresh Claude SDK session in the sandbox.
"""

import asyncio
import hmac
import logging
import os
import traceback
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from starlette.responses import JSONResponse
import uvicorn

from config.loader import sandbox_config
from endpoints import register_routes
from lifecycle.bootstrap import bootstrap_run
from lifecycle.round_loop import run_rounds
from lifecycle.teardown import finalize_run
from sandbox_client.pool import SandboxPool
from utils import db
from utils.constants import (
    ACTIVE_RUN_STATUSES,
    ENV_KEY_GIT_TOKEN,
    ENV_KEY_INTERNAL_SECRET,
    MAX_CONCURRENT_RUNS,
    SANDBOX_CLONE_TIMEOUT_DEFAULT,
    SANDBOX_EXEC_TIMEOUT_DEFAULT,
    SANDBOX_HEALTH_TIMEOUT_DEFAULT,
    SERVER_HOST,
    SERVER_PORT,
)
from utils.models import ActiveRun, StartRequest

log = logging.getLogger("server")


class AgentServer:
    """HTTP server managing concurrent agent runs with per-run sandboxes."""

    def __init__(self) -> None:
        cfg = sandbox_config()
        self._health_timeout: int = cfg.get(
            "health_timeout_sec",
            SANDBOX_HEALTH_TIMEOUT_DEFAULT,
        )
        self._exec_timeout: int = cfg.get(
            "exec_timeout_sec",
            SANDBOX_EXEC_TIMEOUT_DEFAULT,
        )
        self._clone_timeout: int = cfg.get(
            "clone_timeout_sec",
            SANDBOX_CLONE_TIMEOUT_DEFAULT,
        )

        self._pool = SandboxPool()
        self._runs: dict[str, ActiveRun] = {}

        self.app = FastAPI(title="AutoFyn Agent", lifespan=self._lifespan)
        self._internal_secret = os.environ[ENV_KEY_INTERNAL_SECRET]
        if not self._internal_secret:
            raise RuntimeError(f"{ENV_KEY_INTERNAL_SECRET} is empty")
        self._install_internal_auth()
        register_routes(self.app, self)

    def _install_internal_auth(self) -> None:
        """Require the internal secret header on every endpoint except /health."""
        secret = self._internal_secret

        @self.app.middleware("http")
        async def check_internal_secret(request, call_next):
            if request.url.path == "/health":
                return await call_next(request)
            provided = request.headers.get("X-Internal-Secret", "")
            if not hmac.compare_digest(provided, secret):
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Unauthorized"},
                )
            return await call_next(request)

    @asynccontextmanager
    async def _lifespan(self, app: FastAPI):
        """Startup: init DB + mark crashed runs. Shutdown: tear down sandboxes."""
        await db.init_db()
        crashed = await db.mark_crashed_runs()
        if crashed:
            log.info("Marked %d stale run(s) as crashed", crashed)
        log.info("Ready — waiting for start command on :%d", SERVER_PORT)
        yield
        await self._pool.destroy_all()
        await db.close_db()

    # ── Accessors used by endpoints.py ─────────────────────────────────

    def active_count(self) -> int:
        """Count non-terminal runs (includes starting/running/paused)."""
        return sum(1 for r in self._runs.values() if r.status in ACTIVE_RUN_STATUSES)

    def ensure_capacity(self) -> None:
        """Raise 409 if max concurrent runs reached."""
        if self.active_count() >= MAX_CONCURRENT_RUNS:
            raise HTTPException(
                status_code=409,
                detail=f"Max concurrent runs ({MAX_CONCURRENT_RUNS}) reached",
            )

    def get_run_or_first(self, run_id: str | None) -> ActiveRun:
        """Look up a specific run or the first running run."""
        if run_id:
            run = self._runs.get(run_id)
            if not run:
                raise HTTPException(status_code=404, detail="Run not found")
            return run
        for r in self._runs.values():
            if r.status == "running" and r.inbox:
                log.warning(
                    "get_run_or_first called without run_id — "
                    "falling back to first active run",
                )
                return r
        raise HTTPException(status_code=409, detail="No run in progress")

    def register_run(self, active: ActiveRun) -> None:
        """Insert a new ActiveRun into the in-process registry."""
        if active.run_id is None:
            raise RuntimeError("register_run requires run_id")
        self._runs[active.run_id] = active

    def remove_run(self, run_id: str) -> None:
        """Remove a run from the registry (idempotent)."""
        self._runs.pop(run_id, None)

    def runs(self) -> dict[str, ActiveRun]:
        """Expose the run dict (read-only use by endpoints)."""
        return self._runs

    def pool(self) -> SandboxPool:
        """Expose the sandbox pool."""
        return self._pool

    # ── Run Lifecycle ──────────────────────────────────────────────────

    async def execute_run(self, active: ActiveRun, body: StartRequest) -> None:
        """Spin up sandbox → bootstrap → round loop → teardown → destroy."""
        run_id = active.run_id
        if run_id is None:
            raise RuntimeError("execute_run requires ActiveRun.run_id")

        github_repo = body.github_repo
        if not github_repo:
            raise RuntimeError("github_repo is required")
        task = body.prompt
        if not task:
            raise RuntimeError("prompt is required — AutoFyn needs a task")

        budget = body.max_budget_usd or float(
            os.environ.get("MAX_BUDGET_USD", "0"),
        )
        run_env = body.env or {}
        git_token = run_env.get(ENV_KEY_GIT_TOKEN, "")
        if not git_token:
            raise RuntimeError(f"{ENV_KEY_GIT_TOKEN} missing from run env")

        sandbox = await self._pool.create(
            run_id,
            self._health_timeout,
            body.env,
        )
        terminal_status = "error"
        try:
            bootstrap = await bootstrap_run(
                sandbox=sandbox,
                run_id=run_id,
                custom_prompt=task,
                max_budget_usd=budget,
                duration_minutes=body.duration_minutes,
                base_branch=body.base_branch,
                github_repo=github_repo,
                model=body.model,
                git_token=git_token,
                clone_timeout=self._clone_timeout,
            )
            active.status = "running"
            active.inbox = bootstrap.inbox
            active.time_lock = bootstrap.time_lock
            active.run_context = bootstrap.run

            log.info("Run %s: entering round loop", run_id)
            terminal_status = await run_rounds(
                sandbox,
                bootstrap,
                self._exec_timeout,
            )
            log.info("Run %s: round loop returned %s", run_id, terminal_status)

            bootstrap.run.skip_pr = active.skip_pr
            await finalize_run(
                sandbox=sandbox,
                run=bootstrap.run,
                metadata_store=bootstrap.metadata,
                status=terminal_status,
                exec_timeout=self._exec_timeout,
            )
            active.status = terminal_status
        except Exception as exc:
            # Capture sandbox logs before the finally-block destroys the
            # container. Otherwise failures lose their root cause. Persist
            # them as an audit event so they survive container cleanup and
            # show up in the dashboard timeline.
            tail_lines = await self._pool.get_logs(run_id, tail=200)
            await db.log_audit(
                run_id,
                "sandbox_crash",
                {
                    "error": str(exc),
                    "sandbox_logs": "\n".join(tail_lines) if tail_lines else "",
                },
            )
            if tail_lines:
                log.error(
                    "Run %s sandbox tail logs:\n%s",
                    run_id,
                    "\n".join(tail_lines),
                )
            raise
        finally:
            active.inbox = None
            active.time_lock = None
            await sandbox.close()
            await self._pool.destroy(run_id)

    def on_task_done(self, active: ActiveRun, task: asyncio.Task) -> None:
        """Persist final status for crashes and cancels."""
        context = active.run_context
        try:
            exc = task.exception()
            if exc:
                tb = "".join(
                    traceback.format_exception(type(exc), exc, exc.__traceback__),
                )
                log.error("Run %s crashed:\n%s", active.run_id, tb)
                active.status = "crashed"
                active.error_message = str(exc)
                if active.run_id and context is not None:
                    asyncio.create_task(
                        db.finish_run(
                            active.run_id,
                            "crashed",
                            None,
                            context.total_cost,
                            context.total_input_tokens,
                            context.total_output_tokens,
                            str(exc),
                            None,
                            None,
                            context.cache_creation_input_tokens,
                            context.cache_read_input_tokens,
                        )
                    )
                elif active.run_id:
                    asyncio.create_task(
                        db.update_run_status(active.run_id, "crashed"),
                    )
        except asyncio.CancelledError:
            active.status = "killed"
            active.error_message = "Cancelled"
            if active.run_id and context is not None:
                asyncio.create_task(
                    db.finish_run(
                        active.run_id,
                        "killed",
                        None,
                        context.total_cost,
                        context.total_input_tokens,
                        context.total_output_tokens,
                        "Cancelled",
                        None,
                        None,
                        context.cache_creation_input_tokens,
                        context.cache_read_input_tokens,
                    )
                )
            elif active.run_id:
                asyncio.create_task(
                    db.update_run_status(active.run_id, "killed"),
                )
        finally:
            active.task = None


def _new_run_id() -> str:
    """Generate a fresh run id."""
    return str(uuid.uuid4())


_server = AgentServer()
app = _server.app


def main() -> None:
    """Run the agent HTTP server."""
    logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT, log_level="info")


if __name__ == "__main__":
    main()
