"""Orphaned agent call reconciliation.

Synthesizes 'post' records for Agent tool calls that have a 'pre' event
but no matching 'post' event. Called at the end of each round to recover
from transient network/DB failures in the sandbox→agent HTTP logging chain.
"""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_session_factory
from db.models import ToolCall
from utils.constants import AGENT_TOOL_NAME
from utils.db_helpers import swallow_errors

log = logging.getLogger("agent.db")


async def _fetch_tool_use_ids(
    session: AsyncSession,
    run_id: str,
    tool_name: str,
    phase: str,
) -> set[str]:
    """Query tool_use_ids matching run/tool/phase from ToolCall."""
    rows = (
        await session.execute(
            select(ToolCall.tool_use_id).where(
                ToolCall.run_id == run_id,
                ToolCall.tool_name == tool_name,
                ToolCall.phase == phase,
                ToolCall.tool_use_id.isnot(None),
            )
        )
    ).all()
    return {row[0] for row in rows}


async def _synthesize_post_records(
    session: AsyncSession,
    run_id: str,
    tool_name: str,
    orphan_tuids: set[str],
) -> int:
    """Fetch orphan pre-records and create synthetic post ToolCall objects.

    Returns the count of synthetic records added to the session.
    """
    orphans = (
        await session.execute(
            select(ToolCall).where(
                ToolCall.run_id == run_id,
                ToolCall.tool_name == tool_name,
                ToolCall.phase == "pre",
                ToolCall.tool_use_id.in_(orphan_tuids),
            )
        )
    ).scalars().all()

    for orphan in orphans:
        session.add(
            ToolCall(
                run_id=run_id,
                phase="post",
                tool_name=orphan.tool_name,
                tool_use_id=orphan.tool_use_id,
                session_id=orphan.session_id,
                agent_id=orphan.agent_id,
                agent_role=orphan.agent_role,
                output_data={"reconciled": True},
                input_data=None,
                duration_ms=None,
                permitted=True,
                deny_reason=None,
            )
        )
    return len(orphans)


@swallow_errors
async def reconcile_orphaned_agent_calls(run_id: str) -> int:
    """Synthesize 'post' records for Agent tool calls missing their completion.

    Scans tool_calls for Agent tools with phase='pre' but no matching
    phase='post' by tool_use_id. Writes a synthetic post record with
    output_data={"reconciled": true} so the frontend shows them as done.

    Called at the end of each round to catch events lost due to transient
    network/DB failures in the sandbox→agent HTTP logging chain.

    Returns the number of orphans reconciled.
    """
    async with get_session_factory()() as s:
        pre_tuids = await _fetch_tool_use_ids(s, run_id, AGENT_TOOL_NAME, "pre")
        if not pre_tuids:
            return 0

        post_tuids = await _fetch_tool_use_ids(s, run_id, AGENT_TOOL_NAME, "post")
        orphan_tuids = pre_tuids - post_tuids
        if not orphan_tuids:
            return 0

        count = await _synthesize_post_records(s, run_id, AGENT_TOOL_NAME, orphan_tuids)
        log.info(
            "Reconciled %d orphaned Agent tool call(s) for run %s",
            count,
            run_id[:8],
        )
        await s.commit()
        return count
