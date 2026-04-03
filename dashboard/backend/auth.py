"""API key authentication for the dashboard."""

import hmac
import logging
from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from backend import crypto
from backend.constants import MASTER_KEY_PATH
from backend.utils import session
from db.models import Setting

log = logging.getLogger("backend.auth")

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

_cached_key: str | None = None
_cache_loaded: bool = False


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


def clear_cache() -> None:
    """Clear the cached API key (call after settings update)."""
    global _cached_key, _cache_loaded
    _cached_key = None
    _cache_loaded = False


async def is_auth_enabled() -> bool:
    """Return True if an API key is configured in the DB."""
    return await _load_api_key() is not None


async def verify_api_key(api_key: str | None = Security(_api_key_header)) -> None:
    """FastAPI dependency that enforces API key auth when configured."""
    expected = await _load_api_key()
    if expected is None:
        return  # Auth not configured — allow all
    if not api_key or not hmac.compare_digest(api_key, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
