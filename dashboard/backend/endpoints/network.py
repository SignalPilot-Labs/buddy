"""Dashboard API endpoint — local network IP for mobile QR code access."""

import os

from fastapi import APIRouter, Depends

from backend import auth
from backend.constants import UI_PORT

router = APIRouter(prefix="/api", dependencies=[Depends(auth.verify_api_key)])

_HOST_IP_ENV = "HOST_IP"


def _get_host_ip() -> str | None:
    """Return the host machine's LAN IP from HOST_IP env var."""
    return os.environ.get(_HOST_IP_ENV) or None


@router.get("/network-info")
async def get_network_info() -> dict:
    """Return the local network URL for mobile QR code access."""
    ip = _get_host_ip()
    url = f"http://{ip}:{UI_PORT}" if ip else None
    return {"url": url, "ip": ip, "port": UI_PORT}
