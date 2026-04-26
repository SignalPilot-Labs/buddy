"""Round loop — Python drives a fresh orchestrator session per round.

This is the real long-running thing. The Claude SDK session only lives
for one round. When a round ends, Python reads `/tmp/rounds.json` for the
summary, commits with `[Round N] <summary>`, pushes, and decides whether
to start another round.

Round terminal states and what the loop does with them:

    complete      : read metadata, commit, push, loop again
    ended         : orchestrator called end_session — commit, push, stop
    paused        : await resume/stop on the user inbox
    stopped       : user stopped — tear down
    session_error : API/SDK error — retry up to 3× with exponential backoff (2/4/8s)
    error         : log and tear down
"""

import logging

from lifecycle.bootstrap import BootstrapResult
from lifecycle.round_handlers import (
    handle_complete_or_ended,
    handle_paused,
    handle_session_error,
    handle_stopped,
)
from memory.metadata import MetadataStore
from user.inbox import UserInbox
from prompts.orchestrator import RoundContext, build_initial_prompt, build_round_system_prompt
from prompts.subagent import build_agent_defs
from sandbox_client.client import SandboxClient
from agent_session.runner import RoundRunner
from agent_session.time_lock import TimeLock
from utils import db
from utils.db_reconcile import reconcile_orphaned_agent_calls
from db.constants import (
    RUN_STATUS_ERROR,
    RUN_STATUS_PAUSED,
    RUN_STATUS_STOPPED,
)
from utils.models import RoundResult, RunContext

log = logging.getLogger("lifecycle.round_loop")


async def run_rounds(
    sandbox: SandboxClient,
    bootstrap: BootstrapResult,
    exec_timeout: int,
    host_mounts: list[dict[str, str]] | None,
    user_env_keys: list[str],
) -> str:
    """Run rounds until the orchestrator or user says stop.

    Returns the terminal run status: "completed", "stopped", or "error".
    """
    run = bootstrap.run
    inbox = bootstrap.inbox
    time_lock = bootstrap.time_lock
    reports = bootstrap.reports
    metadata_store = bootstrap.metadata
    archiver = bootstrap.archiver
    rid = run.run_id[:8]

    runner = RoundRunner(sandbox, run, inbox, time_lock, bootstrap.run_config)
    metadata_for_commit = metadata_store
    consecutive_session_errors = 0

    # Fresh run: 0 → first round is 1. Resumed run: starting_round is
    # the highest archived round; we pick up at starting_round + 1.
    round_number = bootstrap.starting_round
    while True:
        round_number += 1
        log.info("[%s] ── Round %d begin ──", rid, round_number)

        await reports.ensure_round_directory(round_number)

        prior_metadata = await metadata_store.load()
        prior_reports = (
            await reports.list_round(round_number - 1) if round_number > 1 else []
        )
        # Drain in-memory inbox so buffered messages don't re-deliver
        # via send_message at the next subagent boundary. The DB is now
        # the source of truth for the full user activity timeline.
        inbox.take_pending_messages()
        user_activity = await db.get_user_activity(run.run_id)

        round_context = RoundContext(
            round_number=round_number,
            duration_minutes=run.duration_minutes,
            time_remaining_minutes=time_lock.remaining_minutes(),
            metadata=prior_metadata,
            previous_round_reports=prior_reports,
            user_activity=user_activity,
            host_mounts=host_mounts,
            user_env_keys=user_env_keys,
            base_branch=run.base_branch,
        )
        tool_call_timeout_sec = bootstrap.run_config.tool_call_timeout_sec
        system_prompt = build_round_system_prompt(round_context, tool_call_timeout_sec)

        options = dict(bootstrap.base_session_options)
        options["agents"] = build_agent_defs(
            round_number=round_number,
            host_mounts=host_mounts,
            user_env_keys=user_env_keys,
            user_model=options["model"],
            tool_call_timeout_sec=tool_call_timeout_sec,
            base_branch=run.base_branch,
        )
        options["system_prompt"] = {
            "type": system_prompt["type"],
            "preset": system_prompt["preset"],
            "append": system_prompt.get("append", ""),
        }
        initial_prompt = build_initial_prompt(
            round_number, bootstrap.task, time_lock.grace_round_used
        )

        result = await runner.run(options, initial_prompt, round_number)
        await reconcile_orphaned_agent_calls(run.run_id)

        terminal, consecutive_session_errors = await _handle_round_outcome(
            result=result,
            round_number=round_number,
            sandbox=sandbox,
            run=run,
            inbox=inbox,
            time_lock=time_lock,
            metadata_store=metadata_for_commit,
            exec_timeout=exec_timeout,
            consecutive_session_errors=consecutive_session_errors,
            max_rounds=bootstrap.run_config.max_rounds,
        )

        # Archive after outcome handling so the persisted rounds.json
        # reflects record_round(N) from _commit_and_push_round — file
        # and metadata snapshots stay consistent on resume.
        try:
            await archiver.archive_round(round_number)
        except Exception as exc:
            log.warning(
                "[%s] archive_round(%d) failed: %s",
                rid,
                round_number,
                exc,
                exc_info=True,
            )
        if terminal is not None:
            return terminal


# ── Outcome handling ─────────────────────────────────────────────────


async def _handle_round_outcome(
    result: RoundResult,
    round_number: int,
    sandbox: SandboxClient,
    run: RunContext,
    inbox: UserInbox,
    time_lock: TimeLock,
    metadata_store: MetadataStore,
    exec_timeout: int,
    consecutive_session_errors: int,
    max_rounds: int,
) -> tuple[str | None, int]:
    """Apply the round result. Returns (terminal status or None, error counter)."""
    rid = run.run_id[:8]

    if result.status == RUN_STATUS_ERROR:
        log.error("[%s] Round %d errored: %s", rid, round_number, result.error)
        return RUN_STATUS_ERROR, 0

    if result.status == "session_error":
        return await handle_session_error(
            result, round_number, run, consecutive_session_errors
        )

    # Any non-error round resets the counter.
    consecutive_session_errors = 0

    if result.status == RUN_STATUS_STOPPED:
        await handle_stopped(
            round_number, sandbox, run, metadata_store, result, exec_timeout
        )
        return RUN_STATUS_STOPPED, 0

    if result.status == RUN_STATUS_PAUSED:
        terminal = await handle_paused(round_number, run, inbox)
        return terminal, 0

    # status in ("complete", "ended")
    terminal = await handle_complete_or_ended(
        result, round_number, sandbox, run, metadata_store, exec_timeout,
        time_lock, inbox, max_rounds,
    )
    return terminal, 0
