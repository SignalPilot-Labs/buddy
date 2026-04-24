"""Round outcome handlers — one function per terminal/transient round state."""

import asyncio
import logging

from db.constants import (
    RUN_STATUS_COMPLETED,
    RUN_STATUS_ERROR,
    RUN_STATUS_PAUSED,
    RUN_STATUS_RUNNING,
    RUN_STATUS_STOPPED,
)
from memory.metadata import MetadataStore
from sandbox_client.client import SandboxClient
from agent_session.time_lock import TimeLock
from user.inbox import UserInbox
from utils import db
from utils.db_logging import log_audit
from utils.constants import (
    session_error_base_backoff_sec,
    session_error_max_retries,
)
from utils.models import RoundResult, RunContext

log = logging.getLogger("lifecycle.round_handlers")


async def handle_session_error(
    result: RoundResult,
    round_number: int,
    run: RunContext,
    consecutive_session_errors: int,
) -> tuple[str | None, int]:
    """Handle a session_error result. Returns (terminal status or None, new_error_count)."""
    rid = run.run_id[:8]
    consecutive_session_errors += 1
    backoff_sec = session_error_base_backoff_sec() * (
        2 ** (consecutive_session_errors - 1)
    )
    log.warning(
        "[%s] Round %d session error (%d/%d): %s — retrying in %ds",
        rid,
        round_number,
        consecutive_session_errors,
        session_error_max_retries(),
        result.error,
        backoff_sec,
    )
    await log_audit(
        run.run_id,
        "session_error",
        {
            "round_number": round_number,
            "error": result.error,
            "attempt": consecutive_session_errors,
            "backoff_sec": backoff_sec,
        },
    )
    if consecutive_session_errors >= session_error_max_retries():
        log.error(
            "[%s] %d consecutive session errors — giving up",
            rid,
            consecutive_session_errors,
        )
        return RUN_STATUS_ERROR, consecutive_session_errors
    await asyncio.sleep(backoff_sec)
    return None, consecutive_session_errors


async def handle_stopped(
    round_number: int,
    sandbox: SandboxClient,
    run: RunContext,
    metadata_store: MetadataStore,
    result: RoundResult,
    exec_timeout: int,
) -> None:
    """Handle a stopped round: log, audit, commit+push."""
    rid = run.run_id[:8]
    log.info("[%s] Round %d stopped by user", rid, round_number)
    await log_audit(
        run.run_id,
        "stop_requested",
        {"round_number": round_number},
    )
    await _commit_and_push_round(
        sandbox,
        run,
        round_number,
        metadata_store,
        result.round_summary,
        exec_timeout,
    )


async def handle_paused(
    round_number: int,
    run: RunContext,
    inbox: UserInbox,
) -> str | None:
    """Handle a paused round. Returns terminal status or None to continue."""
    rid = run.run_id[:8]
    log.info("[%s] Round %d paused — awaiting resume", rid, round_number)
    await log_audit(
        run.run_id,
        "pause_requested",
        {"round_number": round_number},
    )
    await db.update_run_status(run.run_id, RUN_STATUS_PAUSED)
    resumed = await _await_resume(inbox)
    if not resumed:
        log.info("[%s] Stopped during pause", rid)
        return RUN_STATUS_STOPPED
    await db.update_run_status(run.run_id, RUN_STATUS_RUNNING)
    await log_audit(run.run_id, "run_resumed", {})
    return None


async def handle_complete_or_ended(
    result: RoundResult,
    round_number: int,
    sandbox: SandboxClient,
    run: RunContext,
    metadata_store: MetadataStore,
    exec_timeout: int,
    time_lock: TimeLock,
    inbox: UserInbox,
    max_rounds: int,
) -> str | None:
    """Handle complete/ended round. Returns terminal status or None to continue."""
    rid = run.run_id[:8]
    await _commit_and_push_round(
        sandbox,
        run,
        round_number,
        metadata_store,
        result.round_summary,
        exec_timeout,
    )

    if result.status == "ended":
        log.info("[%s] Orchestrator ended the run after round %d", rid, round_number)
        return RUN_STATUS_COMPLETED

    if time_lock.is_expired():
        if time_lock.grace_round_used:
            log.info(
                "[%s] Grace round finished after round %d — finishing",
                rid,
                round_number,
            )
            return RUN_STATUS_COMPLETED
        log.info(
            "[%s] Time lock expired after round %d — allowing one grace round",
            rid,
            round_number,
        )
        time_lock.grace_round_used = True
        return None

    if round_number >= max_rounds:
        log.info(
            "[%s] Round cap reached (%d) — finishing",
            rid,
            max_rounds,
        )
        await log_audit(
            run.run_id,
            "max_rounds_reached",
            {"round_number": round_number, "cap": max_rounds},
        )
        return RUN_STATUS_COMPLETED

    if inbox.has_stop():
        return RUN_STATUS_STOPPED

    return None


# ── Private helpers ──────────────────────────────────────────────────


async def _commit_and_push_round(
    sandbox: SandboxClient,
    run: RunContext,
    round_number: int,
    metadata_store: MetadataStore,
    end_round_summary: str | None,
    exec_timeout: int,
) -> None:
    """Commit the round. Uses the end_round/end_session summary if the
    orchestrator called one; otherwise autocommits and the loop continues
    into the next round."""
    summary = end_round_summary or " ended without summary -- autocommit"
    message = f"[Round {round_number}] {summary}"

    result = await sandbox.repo.save(message, exec_timeout)

    if not result.committed:
        log.info("Round %d produced no commit", round_number)
        return

    # Append the round entry to /tmp/rounds.json. The orchestrator prompt
    # promises Python does this on its behalf ("Python appends your round
    # entry automatically when you call end_round"), so it must actually
    # happen — otherwise rounds[] stays empty and teardown has no history
    # to build the final PR body from.
    await metadata_store.record_round(
        n=round_number,
        summary=summary,
        pr_title=None,
        pr_description=None,
    )

    if not result.pushed:
        log.warning(
            "Round %d push failed: %s",
            round_number,
            result.push_error,
        )
        await log_audit(
            run.run_id,
            "push_failed",
            {
                "round_number": round_number,
                "error": result.push_error,
            },
        )
        return

    await log_audit(
        run.run_id,
        "round_ended",
        {
            "round_number": round_number,
            "summary": summary,
            "message": message,
            "total_cost_usd": run.total_cost,
        },
    )


async def _await_resume(inbox: UserInbox) -> bool:
    """Block until resume or stop arrives. Returns True on resume."""
    event = await inbox.wait_for_resume_or_stop()
    return event.kind == "resume"
