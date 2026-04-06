"""Dashboard API endpoints — Cloudflare tunnel management."""

import re
import time

from fastapi import APIRouter, Depends, HTTPException

from backend import auth

router = APIRouter(prefix="/api", dependencies=[Depends(auth.verify_api_key)])

TUNNEL_CONTAINER = "buddy-tunnel"
TUNNEL_URL_RE = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")

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


def _get_docker():
    import docker
    return docker.from_env()


def _parse_tunnel_url(container) -> str | None:
    """Extract the most recent Cloudflare tunnel URL from container logs."""
    try:
        logs = container.logs(tail=50).decode("utf-8", errors="replace")
        matches = TUNNEL_URL_RE.findall(logs)
        return matches[-1] if matches else None
    except Exception:
        return None


@router.get("/tunnel/status")
async def tunnel_status() -> dict:
    """Get tunnel container status and URL."""
    try:
        docker_client = _get_docker()
        container = docker_client.containers.get(TUNNEL_CONTAINER)
        url = _parse_tunnel_url(container) if container.status == "running" else None
        return {"status": container.status, "url": url, "container_id": container.short_id}
    except Exception as e:
        if "NotFound" in type(e).__name__:
            return {"status": "not_found", "url": None}
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/tunnel/start")
async def tunnel_start() -> dict:
    """Start the tunnel container."""
    _check_tunnel_rate_limit()
    try:
        docker_client = _get_docker()
        container = docker_client.containers.get(TUNNEL_CONTAINER)
        if container.status == "running":
            return {"ok": True, "message": "already running"}
        container.start()
        return {"ok": True}
    except Exception as e:
        if "NotFound" in type(e).__name__:
            raise HTTPException(status_code=404, detail="Tunnel container not found")
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/tunnel/stop")
async def tunnel_stop() -> dict:
    """Stop the tunnel container."""
    _check_tunnel_rate_limit()
    try:
        docker_client = _get_docker()
        container = docker_client.containers.get(TUNNEL_CONTAINER)
        container.stop(timeout=5)
        return {"ok": True}
    except Exception as e:
        if "NotFound" in type(e).__name__:
            raise HTTPException(status_code=404, detail="Tunnel container not found")
        raise HTTPException(status_code=502, detail=str(e))
