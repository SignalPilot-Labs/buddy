"""Dashboard API endpoints — Cloudflare tunnel management via Docker."""

import re
import logging

import docker
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

_docker_client: docker.DockerClient | None = None
_TUNNEL_URL_RE = re.compile(TUNNEL_URL_PATTERN)


def _get_docker() -> docker.DockerClient:
    global _docker_client
    if _docker_client is None:
        _docker_client = docker.from_env()
    return _docker_client


def _parse_tunnel_url(container: docker.models.containers.Container) -> str | None:
    """Extract the tunnel URL from the container logs."""
    logs = container.logs(tail=TUNNEL_LOG_TAIL_LINES).decode("utf-8", errors="replace")
    matches = _TUNNEL_URL_RE.findall(logs)
    return matches[-1] if matches else None


@router.get("/tunnel/status")
async def tunnel_status() -> dict:
    """Get current Cloudflare tunnel status and URL."""
    try:
        container = _get_docker().containers.get(TUNNEL_CONTAINER)
        url = _parse_tunnel_url(container) if container.status == "running" else None
        return {
            "status": container.status,
            "url": url,
            "container_id": container.short_id,
        }
    except docker.errors.NotFound:
        return {"status": "not_found", "url": None}
    except docker.errors.APIError as e:
        raise HTTPException(status_code=502, detail=str(e))


def _start_existing_container(container: docker.models.containers.Container) -> dict:
    """Start a stopped container and return status."""
    if container.status == "running":
        return {"ok": True, "message": "already running"}
    container.start()
    return {"ok": True}


def _create_tunnel_container(client: docker.DockerClient) -> dict:
    """Create and start a new tunnel container."""
    client.containers.run(
        TUNNEL_IMAGE,
        command=TUNNEL_COMMAND,
        name=TUNNEL_CONTAINER,
        network_mode=f"container:{TUNNEL_NETWORK_TARGET}",
        detach=True,
        restart_policy={"Name": "no"},
    )
    return {"ok": True, "message": "created"}


@router.post("/tunnel/start")
async def tunnel_start() -> dict:
    """Start or create the Cloudflare tunnel container."""
    client = _get_docker()
    try:
        container = client.containers.get(TUNNEL_CONTAINER)
        return _start_existing_container(container)
    except docker.errors.NotFound:
        return _create_tunnel_container(client)
    except docker.errors.APIError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/tunnel/stop")
async def tunnel_stop() -> dict:
    """Stop the Cloudflare tunnel container."""
    try:
        container = _get_docker().containers.get(TUNNEL_CONTAINER)
        container.stop(timeout=TUNNEL_STOP_TIMEOUT)
        return {"ok": True}
    except docker.errors.NotFound:
        raise HTTPException(status_code=404, detail="Tunnel container not found")
    except docker.errors.APIError as e:
        raise HTTPException(status_code=502, detail=str(e))
