"""Session handler — Claude SDK session lifecycle in the sandbox.

Start a session, stream its SSE events back to the agent, send follow-up
messages, interrupt, stop. The actual ClaudeSDKClient lives inside the
sandbox container — this class only shuttles HTTP requests.
"""

import json
import logging
from collections.abc import AsyncGenerator

import httpx

log = logging.getLogger("sandbox_client.session")

HTTP_503_SERVICE_UNAVAILABLE = 503


class SessionNotReadyError(Exception):
    """Raised when the sandbox session's SDK client is not yet initialized."""


class Session:
    """Handler for sandbox `/session/*` HTTP endpoints.

    Public API:
        start(options)              -> session_id
        stream_events(session_id)   -> AsyncIterator[dict]
        send_message(session_id, t) -> None
        interrupt(session_id)       -> None
        stop(session_id)            -> None
    """

    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    async def start(self, options: dict) -> str:
        """Start a Claude SDK session in the sandbox. Returns session_id."""
        resp = await self._http.post("/session/start", json=options)
        resp.raise_for_status()
        return resp.json()["session_id"]

    async def stream_events(self, session_id: str) -> AsyncGenerator[dict, None]:
        """Stream SSE events from a sandbox session."""
        async with self._http.stream(
            "GET", f"/session/{session_id}/events", timeout=None,
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
        """Send a follow-up message to a running sandbox session."""
        resp = await self._http.post(
            f"/session/{session_id}/message", json={"text": text},
        )
        if resp.status_code == HTTP_503_SERVICE_UNAVAILABLE:
            raise SessionNotReadyError(f"Session {session_id} client not ready")
        resp.raise_for_status()

    async def interrupt(self, session_id: str) -> None:
        """Interrupt the current response in a sandbox session."""
        resp = await self._http.post(f"/session/{session_id}/interrupt")
        if resp.status_code == HTTP_503_SERVICE_UNAVAILABLE:
            raise SessionNotReadyError(f"Session {session_id} client not ready")
        resp.raise_for_status()

    async def stop(self, session_id: str) -> None:
        """Stop a running sandbox session."""
        resp = await self._http.post(f"/session/{session_id}/stop")
        resp.raise_for_status()

    async def unlock(self, session_id: str) -> None:
        """Force-unlock the session time gate in the sandbox."""
        resp = await self._http.post(f"/session/{session_id}/unlock")
        resp.raise_for_status()


def _parse_sse_event(raw: str) -> dict | None:
    """Parse a single SSE event block into a {event, data} dict."""
    event_type = "message"
    data_lines: list[str] = []

    for line in raw.strip().split("\n"):
        if line.startswith("event:"):
            event_type = line[6:].strip()
        elif line.startswith("data:"):
            data_lines.append(line[5:].strip())

    if not data_lines:
        return None

    data_str = "\n".join(data_lines)
    try:
        data = json.loads(data_str)
    except json.JSONDecodeError:
        log.warning("Malformed SSE JSON: %s", data_str[:200])
        data = {"raw": data_str}

    return {"event": event_type, "data": data}
