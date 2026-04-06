"""Dashboard API endpoints — Cloudflare tunnel management.

Proxies tunnel operations to the agent container, which has Docker socket access.
The dashboard itself must NOT have Docker socket access (it is internet-facing).
"""

import time

from fastapi import APIRouter, Depends, HTTPException

from backend import auth
from backend.utils import agent_request

router = APIRouter(prefix="/api", dependencies=[Depends(auth.verify_api_key)])

TUNNEL_TIMEOUT = 15

TUNNEL_RATE_LIMIT_MAX = 5
TUNNEL_RATE_LIMIT_WINDOW_SEC = 60.0
_tunnel_timestamps: list[float] = []


def _check_tunnel_rate_limit() -> None:
    """Sliding-window rate limiter for tunnel start/stop operations."""
    now = time.monotonic()
    _tunnel_timestamps[:] = [t for t in _tunnel_timestamps if now - t < TUNNEL_RATE_LIMIT_WINDOW_SEC]
    if len(_tunnel_timestamps) >= TUNNEL_RATE_LIMIT_MAX:
        raise HTTPException(status_code=429, detail="Too many tunnel requests. Max 5 per minute.")
    _tunnel_timestamps.append(now)


@router.get("/tunnel/status")
async def tunnel_status() -> dict:
    """Get tunnel container status and URL."""
    return await agent_request("GET", "/tunnel/status", TUNNEL_TIMEOUT, None, None, {
        "status": "not_found", "url": None,
    })


@router.post("/tunnel/start")
async def tunnel_start() -> dict:
    """Start the tunnel container."""
    _check_tunnel_rate_limit()
    return await agent_request("POST", "/tunnel/start", TUNNEL_TIMEOUT, None, None, None)


@router.post("/tunnel/stop")
async def tunnel_stop() -> dict:
    """Stop the tunnel container."""
    _check_tunnel_rate_limit()
    return await agent_request("POST", "/tunnel/stop", TUNNEL_TIMEOUT, None, None, None)
