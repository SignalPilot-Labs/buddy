"""Database utilities for the agent — wraps the shared db/ package with SQLAlchemy ORM.

All audit/tool logging functions use the @swallow_errors decorator to
prevent DB failures from crashing the agent. Errors are logged via the
standard logging module, never silently swallowed.
"""

import functools
import logging
from collections.abc import Callable, Coroutine
from datetime import datetime, timezone
from typing import Any, TypeVar

from sqlalchemy import func, select, update

from db.connection import connect, close, get_session_factory
from db.models import AuditLog, ControlSignal, Run, ToolCall
from utils.models import UserAction

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
    model_name: str | None,
) -> None:
    """Create a run record with status 'starting'. Called at /start time."""
    async with get_session_factory()() as s:
        s.add(
            Run(
                id=run_id,
                branch_name=None,
                status="starting",
                custom_prompt=custom_prompt,
                duration_minutes=duration_minutes,
                base_branch=base_branch,
                github_repo=github_repo,
                model_name=model_name,
            )
        )
        await s.commit()


async def update_run_branch(run_id: str, branch_name: str) -> None:
    """Set the branch name once git setup completes."""
    async with get_session_factory()() as s:
        await s.execute(
            update(Run)
            .where(Run.id == run_id)
            .values(
                branch_name=branch_name,
                status="running",
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
            "github_repo": run.github_repo,
            "total_cost_usd": run.total_cost_usd,
            "total_input_tokens": run.total_input_tokens,
            "total_output_tokens": run.total_output_tokens,
            "cache_creation_input_tokens": run.cache_creation_input_tokens,
            "cache_read_input_tokens": run.cache_read_input_tokens,
            "model_name": run.model_name,
        }


async def get_run_base_branch(run_id: str) -> str | None:
    """Get the base branch for a run."""
    async with get_session_factory()() as s:
        run = await s.get(Run, run_id)
        if not run:
            return None
        return run.base_branch


async def get_run_branch_name(run_id: str) -> str | None:
    """Get the working branch name for a run (set after bootstrap)."""
    async with get_session_factory()() as s:
        run = await s.get(Run, run_id)
        if not run:
            return None
        return run.branch_name


_USER_FACING_SIGNALS = ("inject", "pause", "resume", "stop", "unlock")

_SIGNAL_RENDERERS: dict[str, Callable[[str | None], tuple[str, str]]] = {
    "inject": lambda p: ("message", p or ""),
    "pause": lambda _: ("pause", "Paused"),
    "resume": lambda _: ("resume", "Resumed"),
    "stop": lambda p: ("stop", f"Stopped: {p}" if p else "Stopped"),
    "unlock": lambda _: ("unlock", "Time gate unlocked"),
}


async def get_user_activity(run_id: str) -> list[UserAction]:
    """Build the full user activity timeline for a run.

    Includes the initial task (from runs.custom_prompt) followed by all
    user-facing control signals (inject, pause, resume, stop) ordered
    chronologically.
    """
    async with get_session_factory()() as s:
        run = await s.get(Run, run_id)
        if not run:
            return []

        actions: list[UserAction] = []
        if run.custom_prompt:
            actions.append(UserAction(
                timestamp=run.started_at.isoformat() if run.started_at else "",
                kind="task",
                text=run.custom_prompt,
            ))

        rows = (
            await s.execute(
                select(ControlSignal.ts, ControlSignal.signal, ControlSignal.payload)
                .where(
                    ControlSignal.run_id == run_id,
                    ControlSignal.signal.in_(_USER_FACING_SIGNALS),
                )
                .order_by(ControlSignal.ts)
            )
        ).all()

        for row in rows:
            renderer = _SIGNAL_RENDERERS[row.signal]
            kind, text = renderer(row.payload)
            actions.append(UserAction(
                timestamp=row.ts.isoformat(),
                kind=kind,
                text=text,
            ))

        return actions


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
    cache_creation_input_tokens: int,
    cache_read_input_tokens: int,
) -> None:
    """Mark a run as finished with final stats."""
    async with get_session_factory()() as s:
        tool_count = (
            await s.execute(
                select(func.count())
                .select_from(ToolCall)
                .where(ToolCall.run_id == run_id, ToolCall.phase == "pre")
            )
        ).scalar_one()

        await s.execute(
            update(Run)
            .where(Run.id == run_id)
            .values(
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
                cache_creation_input_tokens=cache_creation_input_tokens,
                cache_read_input_tokens=cache_read_input_tokens,
            )
        )
        await s.commit()


@swallow_errors
async def update_run_cost(
    run_id: str,
    total_cost_usd: float,
    total_input_tokens: int,
    total_output_tokens: int,
    cache_creation_input_tokens: int,
    cache_read_input_tokens: int,
    context_tokens: int,
) -> None:
    """Persist current cost/token values mid-run. Called at each SDK round boundary."""
    async with get_session_factory()() as s:
        await s.execute(
            update(Run)
            .where(Run.id == run_id)
            .values(
                total_cost_usd=total_cost_usd,
                total_input_tokens=total_input_tokens,
                total_output_tokens=total_output_tokens,
                cache_creation_input_tokens=cache_creation_input_tokens,
                cache_read_input_tokens=cache_read_input_tokens,
                context_tokens=context_tokens,
            )
        )
        await s.commit()


@swallow_errors
async def log_audit(run_id: str, event_type: str, details: dict | None) -> None:
    """Log an audit event."""
    async with get_session_factory()() as s:
        s.add(
            AuditLog(
                run_id=run_id,
                event_type=event_type,
                details=details or {},
            )
        )
        await s.commit()


@swallow_errors
async def log_tool_call(
    run_id: str,
    phase: str,
    tool_name: str,
    input_data: dict | None,
    output_data: dict | None,
    duration_ms: int | None,
    permitted: bool,
    deny_reason: str | None,
    agent_role: str,
    tool_use_id: str | None,
    session_id: str | None,
    agent_id: str | None,
) -> None:
    """Log a tool call event on behalf of the sandbox."""
    async with get_session_factory()() as s:
        s.add(
            ToolCall(
                run_id=run_id,
                phase=phase,
                tool_name=tool_name,
                input_data=input_data,
                output_data=output_data,
                duration_ms=duration_ms,
                permitted=permitted,
                deny_reason=deny_reason,
                agent_role=agent_role,
                tool_use_id=tool_use_id,
                session_id=session_id,
                agent_id=agent_id,
            )
        )
        await s.commit()


@swallow_errors
async def update_run_status(run_id: str, status: str) -> None:
    """Update the run status (e.g. to 'paused')."""
    async with get_session_factory()() as s:
        await s.execute(update(Run).where(Run.id == run_id).values(status=status))
        await s.commit()


async def mark_crashed_runs() -> int:
    """Mark any 'running' or 'paused' runs as 'crashed' on startup.

    Also emits an agent_restarted audit event per crashed run so the
    error appears in the dashboard feed, not just the run sidebar.
    """
    error_msg = "Agent container restarted while run was in progress"
    async with get_session_factory()() as s:
        # Find affected run IDs first so we can emit audit events.
        rows = (
            await s.execute(
                select(Run.id).where(
                    Run.status.in_(["starting", "running", "paused", "rate_limited"])
                )
            )
        ).all()
        if not rows:
            return 0

        run_ids = [row[0] for row in rows]
        await s.execute(
            update(Run)
            .where(Run.id.in_(run_ids))
            .values(
                status="crashed",
                ended_at=datetime.now(timezone.utc),
                error_message=error_msg,
            )
        )
        for rid in run_ids:
            s.add(
                AuditLog(
                    run_id=rid,
                    event_type="agent_restarted",
                    details={"error": error_msg},
                )
            )
        await s.commit()
        return len(run_ids)
