"""API key authentication for the dashboard.

All endpoints require a valid X-API-Key header matching the
DASHBOARD_API_KEY environment variable. SSE endpoints also accept
the key via ?api_key= query parameter (EventSource can't send headers).
"""

import hmac
import os

from fastapi import HTTPException, Query, Security
from fastapi.security import APIKeyHeader

from backend.constants import DASHBOARD_API_KEY_ENV, DEFAULT_DASHBOARD_API_KEY

_api_key = os.environ.get(DASHBOARD_API_KEY_ENV, DEFAULT_DASHBOARD_API_KEY)
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def _check(key: str | None) -> None:
    """Raise 401 if the key is missing or wrong."""
    if not key or not hmac.compare_digest(key, _api_key):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


async def verify_api_key(api_key: str | None = Security(_api_key_header)) -> None:
    """FastAPI dependency — check X-API-Key header."""
    _check(api_key)


async def verify_api_key_or_query(
    api_key: str | None = Security(_api_key_header),
    api_key_query: str | None = Query(default=None, alias="api_key"),
) -> None:
    """FastAPI dependency — accept key from header OR query param (for SSE)."""
    _check(api_key or api_key_query)
