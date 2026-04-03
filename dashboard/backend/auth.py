"""API key authentication for the dashboard.

Desktop access has no auth when no API key is configured (onboarding).
Tunnel access is gated by nginx (rejects if no X-API-Key header),
then validated here against the dashboard API key or tunnel token.
"""

import hmac
import logging

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from backend import crypto
from backend.constants import MASTER_KEY_PATH, TUNNEL_TOKEN_DB_KEY
from backend.utils import session
from db.models import Setting

log = logging.getLogger("backend.auth")

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

_cached_key: str | None = None
_cache_loaded: bool = False
_cached_tunnel_token: str | None = None
_tunnel_cache_loaded: bool = False


async def _load_api_key() -> str | None:
    """Load the dashboard API key from DB. Returns None if not configured."""
    global _cached_key, _cache_loaded
    if _cache_loaded:
        return _cached_key
    try:
        async with session() as s:
            setting = await s.get(Setting, "dashboard_api_key")
            if setting and setting.value:
                _cached_key = crypto.decrypt(setting.value, MASTER_KEY_PATH) if setting.encrypted else setting.value
            else:
                _cached_key = None
        _cache_loaded = True
    except Exception:
        log.warning("Could not load API key from DB — will retry on next request")
        _cached_key = None
    return _cached_key


async def _load_tunnel_token() -> str | None:
    """Load the ephemeral tunnel token from DB."""
    global _cached_tunnel_token, _tunnel_cache_loaded
    if _tunnel_cache_loaded:
        return _cached_tunnel_token
    try:
        async with session() as s:
            setting = await s.get(Setting, TUNNEL_TOKEN_DB_KEY)
            if setting and setting.value:
                _cached_tunnel_token = crypto.decrypt(setting.value, MASTER_KEY_PATH) if setting.encrypted else setting.value
            else:
                _cached_tunnel_token = None
        _tunnel_cache_loaded = True
    except Exception:
        log.warning("Could not load tunnel token from DB — will retry on next request")
        _cached_tunnel_token = None
    return _cached_tunnel_token


def clear_cache() -> None:
    """Clear the cached API key (call after settings update)."""
    global _cached_key, _cache_loaded
    _cached_key = None
    _cache_loaded = False


async def is_auth_enabled() -> bool:
    """Return True if an API key is configured in the DB."""
    return await _load_api_key() is not None


async def verify_api_key(api_key: str | None = Security(_api_key_header)) -> None:
    """FastAPI dependency — accepts dashboard API key or tunnel token.

    When no API key is configured, allows unauthenticated access (onboarding).
    """
    expected = await _load_api_key()
    if expected is None:
        return  # Auth not configured — allow all (onboarding)

    if api_key:
        if hmac.compare_digest(api_key, expected):
            return
        tunnel_token = await _load_tunnel_token()
        if tunnel_token and hmac.compare_digest(api_key, tunnel_token):
            return

    raise HTTPException(status_code=401, detail="Invalid or missing API key")
