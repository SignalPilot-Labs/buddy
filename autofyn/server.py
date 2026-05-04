"""AutoFyn agent HTTP server.

Orchestrates bootstrap → round loop → teardown. Each run gets its own
sandbox container via SandboxPool for isolation. Round-based execution:
the Python `lifecycle.round_loop` is the long-running thing — each
round starts a fresh Claude SDK session in the sandbox.
"""

import asyncio
import hmac
import json
import logging
import os
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from starlette.responses import JSONResponse
import uvicorn

from config.loader import sandbox_config
from endpoints.registry import register_routes
from lifecycle.bootstrap import bootstrap_run
from lifecycle.round_loop import run_rounds
from lifecycle.teardown import finalize_run
from sandbox_client.client import SandboxClient
from sandbox_client.errors import SandboxStartError
from sandbox_client.pool import SandboxPool
from utils import db
from utils.db import (
    get_setting_value,
    update_run_sandbox_backend_id,
    update_run_sandbox_remote_host,
    update_run_sandbox_snapshot,
)
from utils.db_logging import log_audit
from db.constants import (
    ACTIVE_RUN_STATUSES,
    REMOTE_SANDBOX_KEY_PREFIX,
    RUN_STATUS_CRASHED,
    RUN_STATUS_ERROR,
    RUN_STATUS_KILLED,
    RUN_STATUS_RUNNING,
)
from utils.constants import (
    AccessNoiseFilter,
    ENV_KEY_ANTHROPIC_API,
    ENV_KEY_CLAUDE_TOKEN,
    ENV_KEY_GIT_TOKEN,
    ENV_KEY_INTERNAL_SECRET,
    ENV_KEY_SANDBOX_SECRET,
    INTERNAL_SECRET_HEADER,
    SANDBOX_LOG_TAIL_LINES,
    SERVER_HOST,
    max_concurrent_runs,
    server_port,
)
from utils.models import ActiveRun, BootstrapResult, RunContext
from utils.models_http import StartRequest
from utils.secrets import scrub_secrets

log = logging.getLogger("server")

_SECRET_ENV_KEYS: tuple[str, ...] = (
    ENV_KEY_GIT_TOKEN,
    ENV_KEY_CLAUDE_TOKEN,
    ENV_KEY_INTERNAL_SECRET,
    ENV_KEY_SANDBOX_SECRET,
    ENV_KEY_ANTHROPIC_API,
)


def _scrub_secrets(text: str) -> str:
    """Gather secret values from env and scrub them from `text`.

    Reads os.environ at call time — not a cached snapshot — because the
    run env can be merged late (see endpoints.py) and tests mutate env
    between cases.
    """
    return scrub_secrets(text, [os.environ.get(k) for k in _SECRET_ENV_KEYS])


class AgentServer:
    """HTTP server managing concurrent agent runs with per-run sandboxes."""

    def __init__(self) -> None:
        cfg = sandbox_config()
        self._health_timeout: int = cfg["health_timeout_sec"]
        self._exec_timeout: int = cfg["exec_timeout_sec"]
        self._clone_timeout: int = cfg["clone_timeout_sec"]

        self._pool = SandboxPool()
        self._runs: dict[str, ActiveRun] = {}

        self.app = FastAPI(title="AutoFyn Agent", lifespan=self._lifespan)
        self._internal_secret = os.environ[ENV_KEY_INTERNAL_SECRET]
        if not self._internal_secret:
            raise RuntimeError(f"{ENV_KEY_INTERNAL_SECRET} is empty")
        self._sandbox_secret = os.environ[ENV_KEY_SANDBOX_SECRET]
        if not self._sandbox_secret:
            raise RuntimeError(f"{ENV_KEY_SANDBOX_SECRET} is empty")
        self._install_internal_auth()
        register_routes(self.app, self)

    def _install_internal_auth(self) -> None:
        """Require the internal secret header on every endpoint except /health.

        Only checks AGENT_INTERNAL_SECRET (from dashboard). The sandbox no
        longer calls the agent — after SSE consolidation, all data flows
        forward (agent→sandbox) and back via SSE (sandbox→agent stream).
        """
        agent_secret = self._internal_secret

        @self.app.middleware("http")
        async def check_internal_secret(request, call_next):
            if request.url.path == "/health":
                return await call_next(request)
            provided = request.headers.get(INTERNAL_SECRET_HEADER, "")
            if not hmac.compare_digest(provided, agent_secret):
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
        log.info("Ready — waiting for start command on :%d", server_port())
        yield
        await self._pool.destroy_all()
        await db.close_db()

    # ── Accessors used by endpoints.py ─────────────────────────────────

    def active_count(self) -> int:
        """Count non-terminal runs (includes starting/running/paused)."""
        return sum(1 for r in self._runs.values() if r.status in ACTIVE_RUN_STATUSES)

    def ensure_capacity(self) -> None:
        """Raise 409 if max concurrent runs reached."""
        if self.active_count() >= max_concurrent_runs():
            raise HTTPException(
                status_code=409,
                detail=f"Max concurrent runs ({max_concurrent_runs()}) reached",
            )

    def get_run_or_first(self, run_id: str | None) -> ActiveRun:
        """Look up a specific run or the first running run."""
        if run_id:
            run = self._runs.get(run_id)
            if not run:
                raise HTTPException(status_code=404, detail="Run not found")
            return run
        for r in self._runs.values():
            if r.status == RUN_STATUS_RUNNING and r.inbox:
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

    def _validate_run_inputs(
        self,
        active: ActiveRun,
        body: StartRequest,
    ) -> tuple[str, str, str, float, str]:
        """Validate required run fields. Raises RuntimeError for any missing value.

        Returns (run_id, github_repo, task, budget, git_token).
        """
        run_id = active.run_id
        if run_id is None:
            raise RuntimeError("execute_run requires ActiveRun.run_id")

        github_repo = body.github_repo
        if not github_repo:
            raise RuntimeError("github_repo is required")

        task = body.prompt
        if not task:
            raise RuntimeError("prompt is required — AutoFyn needs a task")

        budget = body.max_budget_usd

        run_env = body.env or {}
        git_token = run_env.get(ENV_KEY_GIT_TOKEN, "")
        if not git_token:
            raise RuntimeError(f"{ENV_KEY_GIT_TOKEN} missing from run env")

        return run_id, github_repo, task, budget, git_token

    async def _emit_start_failed(
        self, run_id: str, exc: SandboxStartError, run_env: dict[str, str] | None
    ) -> None:
        """Emit sandbox_start_failed audit event with startup logs from the exception."""
        log_lines: list[str] = [
            event.get("line", "")
            for event in exc.startup_logs
            if event.get("event") == "log"
        ]
        startup_output = _scrub_secrets("\n".join(log_lines))
        error_text = _scrub_secrets(str(exc))
        if run_env:
            run_secrets = [run_env.get(k) for k in _SECRET_ENV_KEYS]
            startup_output = scrub_secrets(startup_output, run_secrets)
            error_text = scrub_secrets(error_text, run_secrets)
        await log_audit(
            run_id,
            "sandbox_start_failed",
            {
                "error": error_text,
                "startup_logs": startup_output,
            },
        )

    async def _capture_crash_logs(self, run_id: str, exc: Exception) -> None:
        """Capture sandbox logs on exception and persist them as a sandbox_crash audit event.

        Scrubs secrets before logging and storing, so tokens never appear
        in audit history or the server log.
        """
        tail_lines = await self._pool.get_logs(run_id, tail=SANDBOX_LOG_TAIL_LINES)
        sandbox_logs = _scrub_secrets("\n".join(tail_lines)) if tail_lines else ""
        await log_audit(
            run_id,
            "sandbox_crash",
            {
                "error": _scrub_secrets(str(exc)),
                "sandbox_logs": sandbox_logs,
            },
        )
        if tail_lines:
            log.error(
                "Run %s sandbox tail logs:\n%s",
                run_id,
                sandbox_logs,
            )

    async def _cleanup_run(
        self,
        run_id: str,
        active: ActiveRun,
        terminal_status: str,
        bootstrap: BootstrapResult | None,
        sandbox: SandboxClient | None,
    ) -> None:
        """Emit the run_ended audit event and tear down the sandbox."""
        elapsed = (
            round(bootstrap.time_lock.elapsed_minutes(), 1)
            if bootstrap and bootstrap.time_lock
            else None
        )
        await log_audit(
            run_id,
            "run_ended",
            {
                "status": active.status or terminal_status,
                "elapsed_minutes": elapsed,
            },
        )
        active.inbox = None
        active.time_lock = None
        if sandbox is not None:
            await sandbox.close()
        await self._pool.destroy(run_id)

    async def _snapshot_sandbox_config(
        self,
        run_id: str,
        body: "StartRequest",
    ) -> None:
        """Snapshot the remote sandbox config to the run record before start.

        Only called when body.sandbox_id is set. Reads config from DB settings
        so the cleanup path knows which sandbox to tear down even if the agent
        restarts mid-run.
        """
        if not body.sandbox_id:
            return
        config_str = await get_setting_value(
            f"{REMOTE_SANDBOX_KEY_PREFIX}{body.sandbox_id}"
        )
        if config_str is None:
            raise ValueError(
                f"No remote sandbox config found for sandbox_id={body.sandbox_id}"
            )
        config: dict = json.loads(config_str)
        await update_run_sandbox_snapshot(
            run_id,
            sandbox_id=body.sandbox_id,
            sandbox_type=config["type"],
            sandbox_ssh_target=config["ssh_target"],
            sandbox_start_cmd=body.start_cmd,
        )

    async def _process_sandbox_events(
        self,
        run_id: str,
        events: list[dict],
    ) -> None:
        """Process NDJSON events from pool.create() and write DB columns.

        Handles: queued (sandbox_backend_id), ready (remote_host/port), log (audit).
        """
        for event in events:
            etype = event.get("event")
            if etype == "queued":
                backend_id = event.get("backend_id")
                if backend_id:
                    await update_run_sandbox_backend_id(run_id, backend_id)
                    await log_audit(run_id, "sandbox_queued", {"backend_id": backend_id})
            elif etype == "ready":
                host: str = event["host"]
                port: int = event["port"]
                await update_run_sandbox_remote_host(run_id, host, port)
            elif etype == "log":
                line: str = event.get("line", "")
                await log_audit(run_id, "startup_log", {"line": line})

    async def execute_run(self, active: ActiveRun, body: StartRequest) -> None:
        """Spin up sandbox → bootstrap → round loop → teardown → destroy."""
        run_id, github_repo, task, budget, git_token = self._validate_run_inputs(active, body)

        sandbox: SandboxClient | None = None
        terminal_status = RUN_STATUS_ERROR
        bootstrap = None
        try:
            await self._snapshot_sandbox_config(run_id, body)
            sandbox, events = await self._pool.create(
                run_id,
                self._health_timeout,
                body.env,
                body.host_mounts,
                self._sandbox_secret,
                body.sandbox_id,
                body.start_cmd,
            )
            await self._process_sandbox_events(run_id, events)
            await log_audit(run_id, "sandbox_created", {})
            bootstrap = await bootstrap_run(
                sandbox=sandbox,
                run_id=run_id,
                custom_prompt=task,
                max_budget_usd=budget,
                duration_minutes=body.duration_minutes,
                base_branch=body.base_branch,
                github_repo=github_repo,
                model=body.model,
                effort=body.effort,
                git_token=git_token,
                clone_timeout=self._clone_timeout,
                mcp_servers=body.mcp_servers,
            )
            active.status = RUN_STATUS_RUNNING
            active.inbox = bootstrap.inbox
            active.time_lock = bootstrap.time_lock
            active.run_context = bootstrap.run

            log.info("Run %s: entering round loop", run_id)
            terminal_status = await run_rounds(
                sandbox,
                bootstrap,
                self._exec_timeout,
                body.host_mounts,
                list((body.env or {}).keys()),
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
        except SandboxStartError as exc:
            await self._emit_start_failed(run_id, exc, body.env)
            raise
        except Exception as exc:
            # Capture sandbox logs before the finally-block destroys the
            # container. Otherwise failures lose their root cause. Persist
            # them as an audit event so they survive container cleanup and
            # show up in the dashboard timeline.
            await self._capture_crash_logs(run_id, exc)
            raise
        finally:
            await self._cleanup_run(run_id, active, terminal_status, bootstrap, sandbox)

    def _persist_terminal_status(
        self,
        run_id: str,
        status: str,
        error_message: str,
        context: RunContext | None,
    ) -> None:
        """Fire-and-forget DB write for crash or cancel terminal states."""
        if context is not None:
            asyncio.create_task(
                db.finish_run(
                    run_id,
                    status,
                    None,
                    context.total_cost,
                    context.total_input_tokens,
                    context.total_output_tokens,
                    error_message,
                    None,
                    None,
                    context.cache_creation_input_tokens,
                    context.cache_read_input_tokens,
                )
            )
        else:
            asyncio.create_task(
                db.update_run_status(run_id, status),
            )

    def on_task_done(self, active: ActiveRun, task: asyncio.Task) -> None:
        """Persist final status for crashes and cancels."""
        context = active.run_context
        try:
            exc = task.exception()
            if exc:
                tb = "".join(
                    traceback.format_exception(type(exc), exc, exc.__traceback__),
                )
                log.error("Run %s crashed:\n%s", active.run_id, _scrub_secrets(tb))
                active.status = RUN_STATUS_CRASHED
                active.error_message = _scrub_secrets(str(exc))
                if active.run_id:
                    self._persist_terminal_status(
                        active.run_id,
                        RUN_STATUS_CRASHED,
                        active.error_message,
                        context,
                    )
        except asyncio.CancelledError:
            active.status = RUN_STATUS_KILLED
            active.error_message = "Cancelled"
            if active.run_id:
                self._persist_terminal_status(
                    active.run_id,
                    RUN_STATUS_KILLED,
                    "Cancelled",
                    context,
                )
        finally:
            active.task = None


_server = AgentServer()
app = _server.app


def main() -> None:
    """Run the agent HTTP server."""
    logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")
    _filt = AccessNoiseFilter()
    for name in ("uvicorn.access", "uvicorn", "httpx", ""):
        logging.getLogger(name).addFilter(_filt)
    uvicorn.run(app, host=SERVER_HOST, port=server_port(), log_level="info")


if __name__ == "__main__":
    main()
