"""HTTP client for the sandbox container.

SandboxClient is the agent's only interface to the sandbox. All command
execution and Claude SDK sessions go through here.
"""

import json
import logging
import os
from collections.abc import AsyncIterator
from dataclasses import asdict

import httpx

from utils.constants import SANDBOX_CLIENT_DEFAULT_TIMEOUT
from utils.models import ExecRequest, ExecResult

log = logging.getLogger("sandbox_manager.client")


class SandboxClient:
    """Thin async HTTP client for sandbox communication.

    Public API:
        exec(request) -> ExecResult
        start_session(options) -> str
        stream_events(session_id) -> AsyncIterator[dict]
        send_message(session_id, text) -> None
        stop_session(session_id) -> None
        interrupt_session(session_id) -> None
        health() -> dict
        close() -> None
    """

    def __init__(self, base_url: str, health_timeout: int) -> None:
        self._base_url = base_url.rstrip("/")
        self._health_timeout = health_timeout
        headers: dict[str, str] = {}
        secret = os.environ.get("AGENT_INTERNAL_SECRET", "")
        if secret:
            headers["X-Internal-Secret"] = secret
        self._http = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(SANDBOX_CLIENT_DEFAULT_TIMEOUT),
            headers=headers,
        )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._http.aclose()

    # -- Command Execution --

    async def exec(self, request: ExecRequest) -> ExecResult:
        """Execute a command in the sandbox. Returns structured result."""
        resp = await self._http.post("/exec", json=asdict(request), timeout=request.timeout + 10)
        resp.raise_for_status()
        data = resp.json()
        return ExecResult(
            stdout=data["stdout"],
            stderr=data["stderr"],
            exit_code=data["exit_code"],
        )

    # -- Claude SDK Sessions --

    async def start_session(self, options: dict) -> str:
        """Start a Claude SDK session in the sandbox. Returns session_id."""
        resp = await self._http.post("/session/start", json=options)
        resp.raise_for_status()
        return resp.json()["session_id"]

    async def stream_events(self, session_id: str) -> AsyncIterator[dict]:
        """Stream SSE events from a sandbox session."""
        async with self._http.stream(
            "GET", f"/session/{session_id}/events",
            timeout=None,
        ) as resp:
            resp.raise_for_status()
            buffer = ""
            async for chunk in resp.aiter_text():
                buffer += chunk
                while "\n\n" in buffer:
                    event_str, buffer = buffer.split("\n\n", 1)
                    event = _parse_sse_event(event_str)
                    if event:
                        yield event

    async def send_message(self, session_id: str, text: str) -> None:
        """Send a follow-up message to the sandbox session."""
        resp = await self._http.post(
            f"/session/{session_id}/message",
            json={"text": text},
        )
        resp.raise_for_status()

    async def stop_session(self, session_id: str) -> None:
        """Stop a running sandbox session."""
        resp = await self._http.post(f"/session/{session_id}/stop")
        resp.raise_for_status()

    async def interrupt_session(self, session_id: str) -> None:
        """Interrupt the current response in a sandbox session."""
        resp = await self._http.post(f"/session/{session_id}/interrupt")
        resp.raise_for_status()

    # -- Health --

    async def health(self) -> dict:
        """Check sandbox health."""
        resp = await self._http.get("/health", timeout=self._health_timeout)
        resp.raise_for_status()
        return resp.json()


def _parse_sse_event(raw: str) -> dict | None:
    """Parse a single SSE event block into a dict."""
    event_type = "message"
    data_lines: list[str] = []

    for line in raw.strip().split("\n"):
        if line.startswith("event:"):
            event_type = line[6:].strip()
        elif line.startswith("data:"):
            data_lines.append(line[5:].strip())
        elif line.startswith("id:"):
            pass  # ignored for now

    if not data_lines:
        return None

    data_str = "\n".join(data_lines)
    try:
        data = json.loads(data_str)
    except json.JSONDecodeError:
        log.warning("Malformed SSE JSON: %s", data_str[:200])
        data = {"raw": data_str}

    return {"event": event_type, "data": data}
