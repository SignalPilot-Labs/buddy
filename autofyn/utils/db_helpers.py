"""Shared helpers for database utility modules.

Contains the swallow_errors decorator used by db_logging, db_reconcile,
and db itself. Extracted here to avoid circular imports.
"""

import functools
import logging
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

log = logging.getLogger("agent.db")

T = TypeVar("T")


def swallow_errors(
    fn: Callable[..., Coroutine[Any, Any, T]],
) -> Callable[..., Coroutine[Any, Any, T | None]]:
    """Decorator: catch and log exceptions instead of raising them.

    Use this on non-critical DB operations (audit logging, tool call logging)
    where a failure should not crash the agent. The exception is logged with
    a full traceback so it never disappears silently. Returns a coroutine
    (not just an awaitable) so callers can pass it to `asyncio.create_task`.
    """

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> T | None:
        try:
            return await fn(*args, **kwargs)
        except Exception:
            log.warning("DB operation %s failed", fn.__name__, exc_info=True)
            return None

    return wrapper
