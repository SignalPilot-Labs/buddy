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

import asyncio
import logging

from lifecycle.bootstrap import BootstrapResult
from memory.metadata import MetadataStore
from user.inbox import UserInbox
from prompts.orchestrator import RoundContext, build_round_system_prompt
from prompts.subagent import build_agent_defs
from sandbox_client.client import SandboxClient
from agent_session.runner import RoundRunner
from agent_session.time_lock import TimeLock
from utils import db
from utils.constants import (
    MAX_ROUNDS,
    SESSION_ERROR_BASE_BACKOFF_SEC,
    SESSION_ERROR_MAX_RETRIES,
)
from utils.models import RoundResult, RunContext

log = logging.getLogger("lifecycle.round_loop")


async def run_rounds(
    sandbox: SandboxClient,
    bootstrap: BootstrapResult,
    exec_timeout: int,
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

    runner = RoundRunner(sandbox, run, inbox, time_lock)
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
        try:
            user_activity = await db.get_user_activity(run.run_id)
        except Exception as exc:
            log.warning("[%s] Failed to load user activity: %s", rid, exc)
            user_activity = []

        round_context = RoundContext(
            round_number=round_number,
            duration_minutes=run.duration_minutes,
            time_remaining_minutes=time_lock.remaining_minutes(),
            metadata=prior_metadata,
            previous_round_reports=prior_reports,
            user_activity=user_activity,
        )
        system_prompt = build_round_system_prompt(round_context)

        options = dict(bootstrap.base_session_options)
        options["agents"] = build_agent_defs(
            round_number=round_number,
            duration_minutes=run.duration_minutes,
            time_remaining_minutes=time_lock.remaining_minutes(),
        )
        options["system_prompt"] = {
            "type": system_prompt["type"],
            "preset": system_prompt["preset"],
            "append": system_prompt.get("append", ""),
        }
        initial_prompt = _build_initial_prompt(round_number, bootstrap.task)

        result = await runner.run(options, initial_prompt, round_number)

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
            )
        if terminal is not None:
            await db.log_audit(
                run.run_id,
                "run_ended",
                {
                    "status": terminal,
                    "elapsed_minutes": round(time_lock.elapsed_minutes(), 1),
                },
            )
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
) -> tuple[str | None, int]:
    """Apply the round result. Returns (terminal status or None, error counter)."""
    rid = run.run_id[:8]

    if result.status == "error":
        log.error("[%s] Round %d errored: %s", rid, round_number, result.error)
        return "error", 0

    if result.status == "session_error":
        consecutive_session_errors += 1
        backoff_sec = SESSION_ERROR_BASE_BACKOFF_SEC * (
            2 ** (consecutive_session_errors - 1)
        )
        log.warning(
            "[%s] Round %d session error (%d/%d): %s — retrying in %ds",
            rid,
            round_number,
            consecutive_session_errors,
            SESSION_ERROR_MAX_RETRIES,
            result.error,
            backoff_sec,
        )
        await db.log_audit(
            run.run_id,
            "session_error",
            {
                "round_number": round_number,
                "error": result.error,
                "attempt": consecutive_session_errors,
                "backoff_sec": backoff_sec,
            },
        )
        if consecutive_session_errors >= SESSION_ERROR_MAX_RETRIES:
            log.error(
                "[%s] %d consecutive session errors — giving up",
                rid,
                consecutive_session_errors,
            )
            return "error", consecutive_session_errors
        await asyncio.sleep(backoff_sec)
        return None, consecutive_session_errors

    # Any non-error round resets the counter.
    consecutive_session_errors = 0

    if result.status == "stopped":
        log.info("[%s] Round %d stopped by user", rid, round_number)
        await db.log_audit(
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
        return "stopped", 0

    if result.status == "paused":
        log.info("[%s] Round %d paused — awaiting resume", rid, round_number)
        await db.log_audit(
            run.run_id,
            "pause_requested",
            {
                "round_number": round_number,
            },
        )
        await db.update_run_status(run.run_id, "paused")
        resumed = await _await_resume(inbox)
        if not resumed:
            log.info("[%s] Stopped during pause", rid)
            return "stopped", 0
        await db.update_run_status(run.run_id, "running")
        await db.log_audit(run.run_id, "session_resumed", {})
        return None, 0

    # status in ("complete", "ended")
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
        return "completed", 0

    if time_lock.is_expired():
        log.info("[%s] Time lock expired after round %d — finishing", rid, round_number)
        return "completed", 0

    if round_number >= MAX_ROUNDS:
        log.info(
            "[%s] Round cap reached (%d) — finishing",
            rid,
            MAX_ROUNDS,
        )
        await db.log_audit(
            run.run_id,
            "max_rounds_reached",
            {"round_number": round_number, "cap": MAX_ROUNDS},
        )
        return "completed", 0

    if inbox.has_stop():
        return "stopped", 0

    return None, 0


# ── Commit + push ────────────────────────────────────────────────────


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
        await db.log_audit(
            run.run_id,
            "push_failed",
            {
                "round_number": round_number,
                "error": result.push_error,
            },
        )
        return

    await db.log_audit(
        run.run_id,
        "round_ended",
        {
            "round_number": round_number,
            "summary": summary,
            "message": message,
            "total_cost_usd": run.total_cost,
        },
    )


# ── Pause helpers ────────────────────────────────────────────────────


async def _await_resume(inbox: UserInbox) -> bool:
    """Block until resume or stop arrives. Returns True on resume."""
    event = await inbox.wait_for_resume_or_stop()
    return event.kind == "resume"


# ── Prompt shim ──────────────────────────────────────────────────────


def _build_initial_prompt(round_number: int, task: str) -> str:
    """Short per-round kickoff message paired with the round system prompt."""
    header = f"Round {round_number} is starting.\n\nTask:\n{task.strip()}"
    if round_number == 1:
        return f"{header}\n\nComplete the first-round setup before beginning work."
    return (
        f"{header}\n\nRead prior-round context from /tmp/round-*/ as needed, "
        "then continue."
    )
