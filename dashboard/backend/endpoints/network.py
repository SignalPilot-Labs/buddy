"""Dashboard API endpoint — local network IP for mobile QR code access."""

import socket

from fastapi import APIRouter, Depends

from backend import auth
from backend.constants import DOCKER_HOST_INTERNAL, UI_PORT

router = APIRouter(prefix="/api", dependencies=[Depends(auth.verify_api_key)])


def _get_host_ip() -> str | None:
    """Resolve the Docker host's LAN IP via host.docker.internal."""
    try:
        return socket.gethostbyname(DOCKER_HOST_INTERNAL)
    except OSError:
        return None


@router.get("/network-info")
async def get_network_info() -> dict:
    """Return the local network URL for mobile QR code access."""
    ip = _get_host_ip()
    url = f"http://{ip}:{UI_PORT}" if ip else None
    return {"url": url, "ip": ip, "port": UI_PORT}
