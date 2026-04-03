"""Dashboard API endpoint — local network IP for mobile QR code access."""

import socket

from fastapi import APIRouter, Depends

from backend import auth
from backend.constants import UI_PORT

router = APIRouter(prefix="/api", dependencies=[Depends(auth.verify_api_key)])


def _get_local_ip() -> str | None:
    """Return the machine's LAN IP by connecting to a public DNS address."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return None


@router.get("/network-info")
async def get_network_info() -> dict:
    """Return the local network URL for mobile QR code access."""
    ip = _get_local_ip()
    url = f"http://{ip}:{UI_PORT}" if ip else None
    return {"url": url, "ip": ip, "port": UI_PORT}
