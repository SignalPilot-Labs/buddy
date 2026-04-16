"""HTTP client for the sandbox container.

SandboxClient owns the shared httpx.AsyncClient and binds four handlers
— execute, file_system, repo, session — to it. These handlers are not
separate clients; they are typed namespaces over the same connection.
There is exactly one SandboxClient per sandbox container.

The sandbox-scoped secret is required. If SANDBOX_INTERNAL_SECRET is
not set in the environment, construction raises — there is no dev-mode
fallback that silently drops the header.
"""

import logging
import os

import httpx

from sandbox_client.handlers.execute import Execute
from sandbox_client.handlers.file_system import FileSystem
from sandbox_client.handlers.repo import Repo
from sandbox_client.handlers.session import Session
from utils.constants import ENV_KEY_SANDBOX_SECRET, SANDBOX_CLIENT_DEFAULT_TIMEOUT

log = logging.getLogger("sandbox_client.client")


class SandboxClient:
    """The one client for a sandbox container.

    Exposed handlers:
        execute      — raw command execution
        file_system  — typed file I/O
        repo         — git/gh operations bound to an active working branch
        session      — Claude SDK session lifecycle

    Public API:
        health() -> dict
        close()  -> None
    """

    def __init__(self, base_url: str, health_timeout: int) -> None:
        self._base_url = base_url.rstrip("/")
        self._health_timeout = health_timeout
        secret = os.environ[ENV_KEY_SANDBOX_SECRET]
        if not secret:
            raise RuntimeError(
                f"{ENV_KEY_SANDBOX_SECRET} is empty — refusing to talk to sandbox",
            )
        self._http = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(SANDBOX_CLIENT_DEFAULT_TIMEOUT),
            headers={"X-Internal-Secret": secret},
        )
        self.execute: Execute = Execute(self._http)
        self.file_system: FileSystem = FileSystem(self._http)
        self.repo: Repo = Repo(self._http)
        self.session: Session = Session(self._http)

    async def health(self) -> dict:
        """Check sandbox health."""
        resp = await self._http.get("/health", timeout=self._health_timeout)
        resp.raise_for_status()
        return resp.json()

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._http.aclose()
