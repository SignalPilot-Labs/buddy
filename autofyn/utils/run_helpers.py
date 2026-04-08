"""Pure run-management helper functions with no framework dependencies.

These functions contain the core logic extracted from server.py and endpoints.py.
Callers (server.py) are responsible for translating CapacityError / RunLookupError
into framework-specific HTTP exceptions.
"""

import logging

from utils.constants import ACTIVE_RUN_STATUSES, ENV_KEY_CLAUDE_TOKEN, ENV_KEY_GIT_TOKEN
from utils.models import ActiveRun

log = logging.getLogger("server")


class CapacityError(Exception):
    """Raised when the server is at max concurrent run capacity."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class RunLookupError(Exception):
    """Raised when a run cannot be found or no run is in progress."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def merge_tokens_into_env(
    env: dict[str, str] | None,
    claude_token: str | None,
    git_token: str | None,
) -> dict[str, str] | None:
    """Merge per-run tokens into the env dict without touching os.environ."""
    if not claude_token and not git_token:
        return env
    merged: dict[str, str] = dict(env) if env is not None else {}
    if claude_token:
        merged[ENV_KEY_CLAUDE_TOKEN] = claude_token
    if git_token:
        merged[ENV_KEY_GIT_TOKEN] = git_token
    return merged


def active_count(runs: dict[str, ActiveRun]) -> int:
    """Count non-terminal runs (including paused — they still hold sandbox resources)."""
    return sum(1 for r in runs.values() if r.status in ACTIVE_RUN_STATUSES)


def check_capacity(runs: dict[str, ActiveRun], max_concurrent: int) -> None:
    """Raise CapacityError if max concurrent runs reached."""
    if active_count(runs) >= max_concurrent:
        raise CapacityError(
            status_code=409,
            detail=f"Max concurrent runs ({max_concurrent}) reached",
        )


def get_run_or_first(runs: dict[str, ActiveRun], run_id: str | None) -> ActiveRun:
    """Get specific run by id, or first running run. Raises RunLookupError if none."""
    if run_id:
        run = runs.get(run_id)
        if not run:
            raise RunLookupError(status_code=404, detail="Run not found")
        return run
    for r in runs.values():
        if r.status == "running" and r.events:
            log.warning("_get_run_or_first called without run_id — falling back to first active run")
            return r
    raise RunLookupError(status_code=409, detail="No run in progress")
