"""Dashboard API endpoints — Cloudflare tunnel management via Docker."""

import logging
import re

from docker import DockerClient, from_env
from docker.errors import APIError, NotFound
from docker.models.containers import Container
from fastapi import APIRouter, Depends, HTTPException

from backend import auth
from backend.constants import (
    TUNNEL_COMMAND,
    TUNNEL_CONTAINER,
    TUNNEL_IMAGE,
    TUNNEL_LOG_TAIL_LINES,
    TUNNEL_NETWORK_TARGET,
    TUNNEL_STOP_TIMEOUT,
    TUNNEL_URL_PATTERN,
)

log = logging.getLogger("dashboard.tunnel")

router = APIRouter(prefix="/api", dependencies=[Depends(auth.verify_api_key)])

_docker_client: DockerClient | None = None
_TUNNEL_URL_RE = re.compile(TUNNEL_URL_PATTERN)


def _get_docker() -> DockerClient:
    """Return a cached Docker client singleton."""
    global _docker_client
    if _docker_client is None:
        _docker_client = from_env()
    return _docker_client


def _parse_tunnel_url(container: Container) -> str | None:
    """Extract the tunnel URL from the container logs."""
    raw = container.logs(tail=TUNNEL_LOG_TAIL_LINES)
    text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
    matches = _TUNNEL_URL_RE.findall(text)
    return matches[-1] if matches else None


@router.get("/tunnel/status")
async def tunnel_status() -> dict:
    """Get current Cloudflare tunnel status and URL."""
    try:
        container: Container = _get_docker().containers.get(TUNNEL_CONTAINER)
        url = _parse_tunnel_url(container) if container.status == "running" else None
        return {
            "status": container.status,
            "url": url,
            "container_id": container.short_id,
        }
    except NotFound:
        return {"status": "not_found", "url": None}
    except APIError as e:
        raise HTTPException(status_code=502, detail=str(e))


def _start_existing_container(container: Container) -> dict:
    """Start a stopped container and return status."""
    if container.status == "running":
        return {"ok": True, "message": "already running"}
    container.start()
    return {"ok": True}


def _create_tunnel_container(client: DockerClient) -> dict:
    """Create and start a new tunnel container.

    No restart_policy needed — Docker defaults to "no" (never restart).
    """
    client.containers.run(
        TUNNEL_IMAGE,
        command=TUNNEL_COMMAND,
        name=TUNNEL_CONTAINER,
        network_mode=f"container:{TUNNEL_NETWORK_TARGET}",
        detach=True,
    )
    return {"ok": True, "message": "created"}


@router.post("/tunnel/start")
async def tunnel_start() -> dict:
    """Start or create the Cloudflare tunnel container."""
    client = _get_docker()
    try:
        container: Container = client.containers.get(TUNNEL_CONTAINER)
        return _start_existing_container(container)
    except NotFound:
        return _create_tunnel_container(client)
    except APIError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/tunnel/stop")
async def tunnel_stop() -> dict:
    """Stop the Cloudflare tunnel container."""
    try:
        container: Container = _get_docker().containers.get(TUNNEL_CONTAINER)
        container.stop(timeout=TUNNEL_STOP_TIMEOUT)
        return {"ok": True}
    except NotFound:
        raise HTTPException(status_code=404, detail="Tunnel container not found")
    except APIError as e:
        raise HTTPException(status_code=502, detail=str(e))
