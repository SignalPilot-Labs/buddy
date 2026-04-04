"""Dashboard API endpoint — local network IP for mobile QR code access."""

import os

from fastapi import APIRouter, Depends

from backend import auth
from backend.constants import HOST_IP_ENV, UI_PORT

router = APIRouter(prefix="/api", dependencies=[Depends(auth.verify_api_key)])


@router.get("/network-info")
async def get_network_info() -> dict:
    """Return the local network URL for mobile QR code access."""
    ip = os.environ.get(HOST_IP_ENV) or None
    url = f"http://{ip}:{UI_PORT}" if ip else None
    return {"url": url, "ip": ip, "port": UI_PORT}
