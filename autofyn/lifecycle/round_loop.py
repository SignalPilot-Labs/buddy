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
    rate_limited  : back off (if fallback missing and wait < 10m), then loop
    error         : log and tear down
"""

import asyncio
import logging
import time

from lifecycle.bootstrap import BootstrapResult
from memory.metadata import MetadataStore
from user.inbox import UserInbox
from prompts.orchestrator import RoundContext, build_round_system_prompt
from prompts.subagent import build_agent_defs
from sandbox_client.client import SandboxClient
from session.runner import RoundRunner
from session.time_lock import TimeLock
from utils import db
from utils.constants import RATE_LIMIT_MAX_WAIT_SEC, RATE_LIMIT_SLEEP_BUFFER_SEC
from utils.models import RoundResult, RunContext

log = logging.getLogger("lifecycle.round_loop")


async def run_rounds(
    sandbox: SandboxClient,
    bootstrap: BootstrapResult,
    exec_timeout: int,
) -> str:
    """Run rounds until the orchestrator or user says stop.

    Returns the terminal run status: "completed", "stopped", "rate_limited",
    or "error".
    """
    run = bootstrap.run
    inbox = bootstrap.inbox
    time_lock = bootstrap.time_lock
    reports = bootstrap.reports
    metadata_store = bootstrap.metadata
    rid = run.run_id[:8]

    runner = RoundRunner(sandbox, run, inbox, time_lock)
    metadata_for_commit = metadata_store

    round_number = 0
    while True:
        round_number += 1
        log.info("[%s] ── Round %d begin ──", rid, round_number)

        await reports.ensure_round_directory(round_number)

        prior_metadata = await metadata_store.load()
        prior_reports = (
            await reports.list_round(round_number - 1) if round_number > 1 else []
        )
        user_messages = inbox.take_pending_messages()

        round_ctx = RoundContext(
            round_number=round_number,
            duration_minutes=run.duration_minutes,
            time_remaining_minutes=time_lock.remaining_minutes(),
            metadata=prior_metadata,
            previous_round_reports=prior_reports,
            user_messages=user_messages,
        )
        system_prompt = build_round_system_prompt(round_ctx)

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

        terminal = await _handle_round_outcome(
            result=result,
            round_number=round_number,
            sandbox=sandbox,
            run=run,
            inbox=inbox,
            time_lock=time_lock,
            metadata_store=metadata_for_commit,
            exec_timeout=exec_timeout,
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
) -> str | None:
    """Apply the round result. Returns a terminal run status or None to loop."""
    rid = run.run_id[:8]

    if result.status == "error":
        log.error("[%s] Round %d errored: %s", rid, round_number, result.error)
        return "error"

    if result.status == "stopped":
        log.info("[%s] Round %d stopped by user", rid, round_number)
        await _commit_and_push_round(
            sandbox,
            run,
            round_number,
            metadata_store,
            result.round_summary,
            exec_timeout,
        )
        return "stopped"

    if result.status == "rate_limited":
        backed_off = await _handle_rate_limit(
            rid,
            result,
            inbox,
        )
        if not backed_off:
            return "rate_limited"
        return None

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
            return "stopped"
        await db.update_run_status(run.run_id, "running")
        await db.log_audit(run.run_id, "resumed", {})
        return None

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
        return "completed"

    if time_lock.is_expired():
        log.info("[%s] Time lock expired after round %d — finishing", rid, round_number)
        return "completed"

    if inbox.has_stop():
        return "stopped"

    return None


# ── Commit + push ────────────────────────────────────────────────────


async def _commit_and_push_round(
    sandbox: SandboxClient,
    run: RunContext,
    round_number: int,
    metadata_store: MetadataStore,
    end_round_summary: str | None,
    exec_timeout: int,
) -> None:
    """Commit the round. Prefers the `end_round` tool summary; falls back
    to `/tmp/rounds.json` if the orchestrator exited without calling it."""
    if end_round_summary:
        summary = end_round_summary
    else:
        metadata = await metadata_store.load()
        entry = next(
            (r for r in metadata.rounds if r.n == round_number),
            None,
        )
        summary = entry.summary if entry else "(no summary)"
    message = f"[Round {round_number}] {summary}"

    if not await sandbox.repo.has_changes(exec_timeout):
        log.info("Round %d made no file changes", round_number)
    committed = await sandbox.repo.commit(message, exec_timeout)
    if not committed:
        log.info("Round %d produced no commit", round_number)
        return

    try:
        await sandbox.repo.push(exec_timeout)
    except Exception as exc:
        log.warning("Round %d push failed: %s", round_number, exc)
        await db.log_audit(
            run.run_id,
            "push_failed",
            {
                "round_number": round_number,
                "error": str(exc),
            },
        )
        return

    await db.log_audit(
        run.run_id,
        "round_committed",
        {
            "round_number": round_number,
            "message": message,
        },
    )


# ── Rate limit + pause helpers ───────────────────────────────────────


async def _handle_rate_limit(
    rid: str,
    result: RoundResult,
    inbox: UserInbox,
) -> bool:
    """Block until the rate limit resets. Returns True if the loop should retry."""
    resets_at = result.rate_limit_resets_at
    if not resets_at:
        log.warning("[%s] Rate limit without resets_at — aborting", rid)
        return False

    wait_sec = max(0, resets_at - int(time.time()))
    if wait_sec > RATE_LIMIT_MAX_WAIT_SEC:
        log.info("[%s] Rate limit waits %ds > cap — aborting", rid, wait_sec)
        return False

    log.info("[%s] Rate limit — sleeping %ds", rid, wait_sec)
    sleep_task = asyncio.create_task(
        asyncio.sleep(wait_sec + RATE_LIMIT_SLEEP_BUFFER_SEC),
    )
    event_task = asyncio.create_task(inbox.next_event())
    try:
        done, _ = await asyncio.wait(
            {sleep_task, event_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if event_task in done:
            event = event_task.result()
            if event.kind == "stop":
                inbox.mark_stopped()
                return False
            inbox.push(event.kind, event.payload)
    finally:
        sleep_task.cancel()
        event_task.cancel()

    return True


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
