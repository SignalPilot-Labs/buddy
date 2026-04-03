"""API key authentication for the dashboard.

Auth is always enforced. Valid credentials:
- The dashboard API key (user-configured, persistent)
- The ephemeral tunnel token (auto-generated, rotates on restart)
- Requests from localhost (desktop access, same machine)
"""

import hmac
import logging

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader

from backend import crypto
from backend.constants import LOCALHOST_HOSTS, MASTER_KEY_PATH, TUNNEL_TOKEN_DB_KEY
from backend.utils import session
from db.models import Setting

log = logging.getLogger("backend.auth")

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

class AuthCache:
    """Caches the dashboard API key and tunnel token loaded from the DB."""

    def __init__(self) -> None:
        self._api_key: str | None = None
        self._api_key_loaded: bool = False
        self._tunnel_token: str | None = None
        self._tunnel_token_loaded: bool = False

    async def load_api_key(self) -> str | None:
        """Load the dashboard API key from DB. Returns None if not configured."""
        if self._api_key_loaded:
            return self._api_key
        try:
            async with session() as s:
                setting = await s.get(Setting, "dashboard_api_key")
                if setting and setting.value:
                    self._api_key = crypto.decrypt(setting.value, MASTER_KEY_PATH) if setting.encrypted else setting.value
                else:
                    self._api_key = None
            self._api_key_loaded = True
        except Exception:
            log.warning("Could not load API key from DB — will retry on next request")
            self._api_key = None
        return self._api_key

    async def load_tunnel_token(self) -> str | None:
        """Load the ephemeral tunnel token from DB. Returns None if not generated yet."""
        if self._tunnel_token_loaded:
            return self._tunnel_token
        try:
            async with session() as s:
                setting = await s.get(Setting, TUNNEL_TOKEN_DB_KEY)
                if setting and setting.value:
                    self._tunnel_token = crypto.decrypt(setting.value, MASTER_KEY_PATH) if setting.encrypted else setting.value
                else:
                    self._tunnel_token = None
            self._tunnel_token_loaded = True
        except Exception:
            log.warning("Could not load tunnel token from DB — will retry on next request")
            self._tunnel_token = None
        return self._tunnel_token

    def clear_api_key(self) -> None:
        """Clear the cached API key (call after settings update)."""
        self._api_key = None
        self._api_key_loaded = False

    def clear_tunnel_token(self) -> None:
        """Clear the cached tunnel token (call after token rotation)."""
        self._tunnel_token = None
        self._tunnel_token_loaded = False


_cache = AuthCache()


def clear_cache() -> None:
    """Clear the cached API key (call after settings update)."""
    _cache.clear_api_key()


async def verify_api_key(
    request: Request,
    api_key: str | None = Security(_api_key_header),
) -> None:
    """FastAPI dependency — always enforced.

    Allows access if any of these are true:
    1. Request is from localhost (desktop / same Docker network)
    2. X-API-Key matches the dashboard API key
    3. X-API-Key matches the ephemeral tunnel token
    """
    client_host = request.client.host if request.client else None
    if client_host in LOCALHOST_HOSTS:
        return

    if api_key:
        api_key_val = await _cache.load_api_key()
        if api_key_val and hmac.compare_digest(api_key, api_key_val):
            return

        tunnel_token = await _cache.load_tunnel_token()
        if tunnel_token and hmac.compare_digest(api_key, tunnel_token):
            return

    raise HTTPException(status_code=401, detail="Invalid or missing API key")
