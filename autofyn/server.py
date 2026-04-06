"""AutoFyn agent HTTP server.

AgentServer wraps FastAPI and orchestrates bootstrap → loop → teardown.
Control events are pushed to the active EventBus.
"""

import asyncio
import hmac
import logging
import os
import traceback
from collections.abc import Coroutine
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from starlette.responses import JSONResponse
import uvicorn

from config.loader import sandbox_config
from utils import db
from utils.constants import (
    SANDBOX_CLONE_TIMEOUT_DEFAULT,
    SANDBOX_EXEC_TIMEOUT_DEFAULT,
    SANDBOX_HEALTH_TIMEOUT_DEFAULT,
    SANDBOX_URL_DEFAULT,
    SERVER_HOST,
    SERVER_PORT,
)
from utils.prompts import PromptLoader
from sandbox_manager.client import SandboxClient
from sandbox_manager.repo_ops import RepoOps
from core.bootstrap import Bootstrap
from core.agent_loop import AgentLoop
from endpoints import register_routes
from core.teardown import RunTeardown
from core.event_bus import EventBus
from tools.session import SessionGate
from tools.subagent_tracker import SubagentTracker
from utils.models import RunContext

log = logging.getLogger("server")

BootstrapResult = tuple[RunContext, dict, SessionGate, EventBus, SubagentTracker, str]


class AgentServer:
    """HTTP server that controls the agent lifecycle.

    Orchestrates: bootstrap → agent_loop → teardown.
    Owns the active run state and event bus reference.
    """

    def __init__(self):
        cfg = sandbox_config()
        sandbox_url = cfg.get("url", SANDBOX_URL_DEFAULT)
        health_timeout = cfg.get("health_timeout_sec", SANDBOX_HEALTH_TIMEOUT_DEFAULT)
        self._exec_timeout: int = cfg.get("exec_timeout_sec", SANDBOX_EXEC_TIMEOUT_DEFAULT)
        self._clone_timeout: int = cfg.get("clone_timeout_sec", SANDBOX_CLONE_TIMEOUT_DEFAULT)

        self._sandbox = SandboxClient(sandbox_url, health_timeout)
        self._repo_ops = RepoOps(self._sandbox)
        self._prompts = PromptLoader()
        self._bootstrap = Bootstrap(self._repo_ops, self._sandbox)
        self._loop = AgentLoop(self._repo_ops, self._sandbox, self._prompts)
        self._teardown = RunTeardown(self._repo_ops)
        self._task: asyncio.Task | None = None
        self._events: EventBus | None = None
        self._session: SessionGate | None = None
        self._bootstrapping = False
        self.current_run_id: str | None = None
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
        """Startup: connect DB. Shutdown: close DB and sandbox client."""
        await db.init_db()
        crashed = await db.mark_crashed_runs()
        if crashed:
            log.info("Marked %d stale run(s) as crashed", crashed)
        log.info("Ready — waiting for start command on :%d", SERVER_PORT)
        yield
        await self._sandbox.close()
        await db.close_db()

    # ── Run Lifecycle ──

    async def _execute_run(
        self,
        bootstrap_coro: Coroutine[Any, Any, BootstrapResult],
        custom_prompt: str | None,
    ) -> None:
        """Shared bootstrap → execute → teardown pipeline."""
        self._bootstrapping = True
        run_context, session_options, session, events, tracker, initial = await bootstrap_coro
        self.current_run_id = run_context.run_id
        self._events = events
        self._session = session
        self._bootstrapping = False

        try:
            status = await self._loop.execute(
                session_options, run_context, session, events, tracker, initial,
                custom_prompt, self._exec_timeout,
            )
        finally:
            events.stop_pulse_checker()
            self._events = None
            self._session = None

        await self._teardown.finalize(run_context, status, self._exec_timeout)
        self.current_run_id = None

    async def _run_agent(
        self, custom_prompt: str | None, max_budget: float,
        duration_minutes: float, base_branch: str, github_repo: str,
    ) -> None:
        """Start a new run via the shared execute pipeline."""
        coro = self._bootstrap.setup_new(
            custom_prompt, max_budget, duration_minutes, base_branch, github_repo,
            self._exec_timeout, self._clone_timeout,
        )
        await self._execute_run(coro, custom_prompt)

    async def _resume_agent(
        self, run_id: str, max_budget: float, prompt: str | None,
    ) -> None:
        """Resume a run via the shared execute pipeline."""
        coro = self._bootstrap.setup_resume(
            run_id, max_budget, self._exec_timeout, self._clone_timeout, prompt,
        )
        await self._execute_run(coro, None)

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
            self.current_run_id = None
            self._task = None
            self._events = None
            self._session = None
            self._bootstrapping = False


_server = AgentServer()
app = _server.app


def main():
    """Run the agent HTTP server."""
    logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT, log_level="info")


if __name__ == "__main__":
    main()
