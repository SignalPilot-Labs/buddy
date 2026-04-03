"""Dashboard API endpoint — tunnel URL and pairing code for mobile access."""

import re

from fastapi import APIRouter, Depends, Request

from backend import auth
from backend.constants import TUNNEL_URL_FILE, TUNNEL_URL_PATTERN

router = APIRouter(prefix="/api", dependencies=[Depends(auth.verify_api_key)])

_TUNNEL_URL_RE = re.compile(TUNNEL_URL_PATTERN)


def _read_tunnel_url() -> str | None:
    """Read and validate the tunnel URL from the shared volume file."""
    try:
        raw = TUNNEL_URL_FILE.read_text().strip()
        if _TUNNEL_URL_RE.fullmatch(raw):
            return raw
        return None
    except FileNotFoundError:
        return None


@router.get("/tunnel-url")
async def get_tunnel_url(request: Request) -> dict:
    """Return the tunnel URL and pairing code for mobile access."""
    url = _read_tunnel_url()
    token: str | None = getattr(request.app.state, "tunnel_token", None)
    return {"url": url, "token": token}
