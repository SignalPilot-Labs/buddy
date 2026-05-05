"""Database utilities for the agent — wraps the shared db/ package with SQLAlchemy ORM.

All audit/tool logging functions use the @swallow_errors decorator to
prevent DB failures from crashing the agent. Errors are logged via the
standard logging module, never silently swallowed.
"""

import logging
from collections.abc import Callable
from datetime import datetime, timezone

from sqlalchemy import func, select, update

from db.connection import connect, close, get_session_factory
from db.constants import (
    ACTIVE_RUN_STATUSES,
    RUN_STATUS_CRASHED,
    RUN_STATUS_RATE_LIMITED,
    RUN_STATUS_RUNNING,
    RUN_STATUS_STARTING,
)
from db.models import AuditLog, ControlSignal, Run, Setting, ToolCall
from utils.db_helpers import swallow_errors
from utils.models import UserAction

log = logging.getLogger("agent.db")


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
                status=RUN_STATUS_STARTING,
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
                status=RUN_STATUS_RUNNING,
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
        rows = (
            await s.execute(
                select(Run.id).where(
                    Run.status.in_(ACTIVE_RUN_STATUSES | {RUN_STATUS_RATE_LIMITED})
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
                status=RUN_STATUS_CRASHED,
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


async def get_setting_value(key: str) -> str | None:
    """Read a single setting value by key. Returns None if not found."""
    async with get_session_factory()() as s:
        setting = await s.get(Setting, key)
        if setting is None:
            return None
        return setting.value


async def update_run_sandbox_id(run_id: str, sandbox_id: str) -> None:
    """Link a run to a remote sandbox config."""
    async with get_session_factory()() as s:
        await s.execute(
            update(Run).where(Run.id == run_id).values(sandbox_id=sandbox_id)
        )
        await s.commit()


async def update_run_sandbox_backend_id(run_id: str, sandbox_backend_id: str) -> None:
    """Set sandbox_backend_id once the remote job is queued/assigned."""
    async with get_session_factory()() as s:
        await s.execute(
            update(Run)
            .where(Run.id == run_id)
            .values(sandbox_backend_id=sandbox_backend_id)
        )
        await s.commit()
