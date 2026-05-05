"""Ephemeral SSE token store.

Short-lived opaque tokens issued to the frontend before opening an
EventSource connection. Prevents the full API key from appearing in
server access logs (EventSource cannot send custom headers).

Tokens are kept in-memory only. If the process restarts all tokens are
invalidated — the frontend SSE reconnect logic will simply request a new
token on the next connect attempt.
"""

import secrets
import time

from backend.constants import SSE_TOKEN_BYTES, SSE_TOKEN_LIFETIME_SEC

_tokens: dict[str, float] = {}


def create_sse_token() -> str:
    """Generate an ephemeral SSE token, store it, prune expired entries, return it."""
    token = secrets.token_urlsafe(SSE_TOKEN_BYTES)
    expiry = time.time() + SSE_TOKEN_LIFETIME_SEC
    _tokens[token] = expiry
    _prune_expired()
    return token


def validate_sse_token(token: str) -> bool:
    """Return True if the token exists and has not expired; False otherwise.

    Prunes the token from the store if it is expired.
    """
    expiry = _tokens.get(token)
    if expiry is None:
        return False
    if time.time() > expiry:
        del _tokens[token]
        return False
    return True


def _prune_expired() -> None:
    """Remove all expired entries from the in-memory token store."""
    now = time.time()
    expired = [tok for tok, exp in _tokens.items() if now > exp]
    for tok in expired:
        del _tokens[tok]
