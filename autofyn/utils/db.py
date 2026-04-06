"""Database utilities for the agent — wraps the shared db/ package with SQLAlchemy ORM.

All audit/tool logging functions use the @swallow_errors decorator to
prevent DB failures from crashing the agent. Errors are logged via the
standard logging module, never silently swallowed.
"""

import functools
import logging
import os
from datetime import datetime, timezone

from sqlalchemy import func, select, update

from db.connection import connect, close, get_session_factory
from db.models import AuditLog, Run, ToolCall

log = logging.getLogger("agent.db")


def swallow_errors(fn):
    """Decorator: catch and log exceptions instead of raising them.

    Use this on non-critical DB operations (audit logging, tool call logging)
    where a failure should not crash the agent.
    """
    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except Exception:
            log.warning("DB operation %s failed", fn.__name__, exc_info=True)
            return None
    return wrapper


async def init_db() -> None:
    """Connect to PostgreSQL via the shared db/ connection pool."""
    await connect()


async def close_db() -> None:
    """Close the database connection pool."""
    await close()


async def create_run_starting(
    run_id: str,
    custom_prompt: str | None,
    duration_minutes: float,
    base_branch: str,
    github_repo: str | None,
) -> None:
    """Create a run record with status 'starting'. Called at /start time."""
    repo = github_repo or os.environ.get("GITHUB_REPO") or None
    async with get_session_factory()() as s:
        s.add(Run(
            id=run_id,
            branch_name="pending",
            status="starting",
            custom_prompt=custom_prompt,
            duration_minutes=duration_minutes,
            base_branch=base_branch,
            github_repo=repo,
        ))
        await s.commit()


async def update_run_branch(run_id: str, branch_name: str) -> None:
    """Set the branch name once git setup completes."""
    async with get_session_factory()() as s:
        await s.execute(
            update(Run).where(Run.id == run_id).values(
                branch_name=branch_name, status="running",
            )
        )
        await s.commit()


@swallow_errors
async def save_rate_limit_reset(run_id: str, resets_at: int) -> None:
    """Save the rate limit reset timestamp."""
    async with get_session_factory()() as s:
        await s.execute(
            update(Run).where(Run.id == run_id).values(rate_limit_resets_at=resets_at)
        )
        await s.commit()


@swallow_errors
async def save_session_id(run_id: str, session_id: str) -> None:
    """Save the SDK session ID so we can resume later."""
    async with get_session_factory()() as s:
        await s.execute(
            update(Run).where(Run.id == run_id).values(sdk_session_id=session_id)
        )
        await s.commit()


async def get_run_for_resume(run_id: str) -> dict | None:
    """Get run info needed to resume a session."""
    async with get_session_factory()() as s:
        run = await s.get(Run, run_id)
        if not run:
            return None
        return {
            "id": run.id,
            "branch_name": run.branch_name,
            "status": run.status,
            "sdk_session_id": run.sdk_session_id,
            "custom_prompt": run.custom_prompt,
            "duration_minutes": run.duration_minutes,
            "base_branch": run.base_branch,
            "total_cost_usd": run.total_cost_usd,
            "total_input_tokens": run.total_input_tokens,
            "total_output_tokens": run.total_output_tokens,
        }


async def get_run_base_branch(run_id: str) -> str | None:
    """Get the base branch for a run."""
    async with get_session_factory()() as s:
        run = await s.get(Run, run_id)
        if not run:
            return None
        return run.base_branch


async def finish_run(
    run_id: str,
    status: str,
    pr_url: str | None,
    total_cost_usd: float | None,
    total_input_tokens: int | None,
    total_output_tokens: int | None,
    error_message: str | None,
    rate_limit_info: dict | None,
    diff_stats: list | None,
) -> None:
    """Mark a run as finished with final stats."""
    async with get_session_factory()() as s:
        tool_count = (await s.execute(
            select(func.count()).select_from(ToolCall)
            .where(ToolCall.run_id == run_id, ToolCall.phase == "pre")
        )).scalar_one()

        await s.execute(
            update(Run).where(Run.id == run_id).values(
                ended_at=datetime.now(timezone.utc),
                status=status,
                pr_url=pr_url,
                total_cost_usd=total_cost_usd,
                total_input_tokens=total_input_tokens,
                total_output_tokens=total_output_tokens,
                error_message=error_message,
                rate_limit_info=rate_limit_info,
                diff_stats=diff_stats,
                total_tool_calls=tool_count,
            )
        )
        await s.commit()


@swallow_errors
async def log_audit(run_id: str, event_type: str, details: dict | None) -> None:
    """Log an audit event."""
    async with get_session_factory()() as s:
        s.add(AuditLog(
            run_id=run_id,
            event_type=event_type,
            details=details or {},
        ))
        await s.commit()


@swallow_errors
async def update_run_status(run_id: str, status: str) -> None:
    """Update the run status (e.g. to 'paused')."""
    async with get_session_factory()() as s:
        await s.execute(
            update(Run).where(Run.id == run_id).values(status=status)
        )
        await s.commit()


async def mark_crashed_runs() -> int:
    """Mark any 'running' or 'paused' runs as 'crashed' on startup."""
    async with get_session_factory()() as s:
        result = await s.execute(
            update(Run)
            .where(Run.status.in_(["running", "paused", "rate_limited"]))
            .values(
                status="crashed",
                ended_at=datetime.now(timezone.utc),
                error_message="Agent container restarted while run was in progress",
            )
        )
        await s.commit()
        return result.rowcount  # type: ignore[attr-defined]  # SQLAlchemy CursorResult
