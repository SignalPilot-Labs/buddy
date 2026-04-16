"""HTTP client for reporting sandbox events back to the agent.

Sandbox does NOT hold DB credentials. Tool-call and audit events are
POSTed to the agent's /events/* endpoints; the agent is the only
writer to Postgres. Auth uses SANDBOX_INTERNAL_SECRET, which is
distinct from the dashboard↔agent secret — a compromised sandbox
cannot forge control-plane requests (/start, /stop, etc.).
"""

import logging
import os

import httpx

from constants import (
    AGENT_CALLBACK_URL_ENV_VAR,
    INTERNAL_SECRET_ENV_VAR,
    INTERNAL_SECRET_HEADER,
)

log = logging.getLogger("sandbox.agent_events")

# Short enough that a stuck agent doesn't back-pressure the SDK loop; long
# enough that normal DB writes (a few ms) complete comfortably.
_EVENT_POST_TIMEOUT_SEC = 5

# The sandbox server pops SANDBOX_INTERNAL_SECRET out of os.environ at
# startup so it can't leak into subprocess envs. We cache it here at
# import time — before the pop — so post_event() can still authenticate.
# AGENT_CALLBACK_URL is not secret and can stay in os.environ.
_SANDBOX_SECRET = os.environ.get(INTERNAL_SECRET_ENV_VAR, "")


def _config() -> tuple[str, str]:
    """Return (agent callback base URL, sandbox secret).

    Fail-fast if either is missing — sandbox cannot report events.
    """
    url = os.environ.get(AGENT_CALLBACK_URL_ENV_VAR, "")
    if not url:
        raise RuntimeError(
            f"{AGENT_CALLBACK_URL_ENV_VAR} not set — sandbox cannot report events",
        )
    if not _SANDBOX_SECRET:
        raise RuntimeError(
            f"{INTERNAL_SECRET_ENV_VAR} not set — sandbox cannot authenticate to agent",
        )
    return url.rstrip("/"), _SANDBOX_SECRET


async def post_event(path: str, body: dict) -> None:
    """POST an event to the agent's /events/<path> endpoint.

    Errors are logged but do not raise — event reporting is best-effort
    from the sandbox's perspective; missing audit rows must never crash
    a run. Callers do not need to handle exceptions.
    """
    try:
        url_base, secret = _config()
    except RuntimeError as exc:
        log.warning("Cannot post event: %s", exc)
        return
    url = f"{url_base}/events/{path}"
    headers = {INTERNAL_SECRET_HEADER: secret}
    try:
        async with httpx.AsyncClient(timeout=_EVENT_POST_TIMEOUT_SEC) as client:
            resp = await client.post(url, json=body, headers=headers)
            if resp.status_code >= 400:
                log.warning(
                    "Agent /events/%s returned %d: %s",
                    path, resp.status_code, resp.text[:200],
                )
    except httpx.HTTPError as exc:
        log.warning("Failed to post event to agent /events/%s: %s", path, exc)
