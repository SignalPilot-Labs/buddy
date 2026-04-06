"""Agent loop: round iteration and between-round decisions.

AgentLoop iterates rounds, delegates stream processing to StreamProcessor,
and decides whether to continue or stop. The SDK session runs in the sandbox —
the loop communicates via SandboxClient.
"""

import asyncio
import logging
import os
from datetime import datetime, timezone

from utils import db
from utils.constants import (
    FILES_CHANGED_LIMIT,
    LOG_PREVIEW_LIMIT,
    MAX_OPERATOR_MESSAGES,
    MAX_ROUNDS,
    ROUND_SUMMARY_AUDIT_LIMIT,
    ROUND_SUMMARY_LIMIT,
    WORK_DIR,
)
from utils.models import RoundResult, RunContext
from utils.prompts import PromptLoader
from sandbox_manager.client import SandboxClient
from sandbox_manager.repo_ops import RepoOps
from core.event_bus import EventBus
from core.stream import StreamProcessor
from tools.subagent_tracker import SubagentTracker
from tools.session import SessionGate

log = logging.getLogger("core.loop")


class AgentLoop:
    """Iterates rounds, handles between-round events, delegates stream processing.

    Public API:
        execute(session_options, run_context, session, events, initial_prompt, custom_prompt, exec_timeout) -> str
    """

    def __init__(self, repo_ops: RepoOps, sandbox: SandboxClient, prompts: PromptLoader) -> None:
        self._repo_ops = repo_ops
        self._sandbox = sandbox
        self._prompts = prompts

    async def execute(
        self, session_options: dict, run_context: RunContext,
        session: SessionGate, events: EventBus, tracker: SubagentTracker,
        initial_prompt: str, custom_prompt: str | None,
        exec_timeout: int,
    ) -> str:
        """Run the agent loop. Returns final status string."""
        model = session_options.get("model", os.environ.get("AGENT_MODEL", "opus"))
        fallback_model = session_options.get("fallback_model")
        status = "completed"
        pending_inject: str | None = None
        self._operator_messages = []
        sandbox_session_id: str | None = None

        try:
            sandbox_session_id = await self._start_session(session_options, initial_prompt)

            stream = StreamProcessor(
                self._sandbox, sandbox_session_id,
                run_context, session, tracker,
                events, self._prompts,
                model, fallback_model,
            )

            status = await self._run_rounds(
                stream, sandbox_session_id, run_context, session, events,
                custom_prompt, exec_timeout, pending_inject,
            )

        except asyncio.CancelledError:
            status = "killed"
            await db.log_audit(run_context.run_id, "killed", {
                "elapsed_minutes": round(session.elapsed_minutes(), 1),
            })
        except Exception as e:
            log.error("Fatal error: %s", e, exc_info=True)
            status = "error"
            await db.log_audit(run_context.run_id, "fatal_error", {"error": str(e)})
        finally:
            await self._cleanup_session(sandbox_session_id)

        return status

    async def _start_session(self, session_options: dict, initial_prompt: str) -> str:
        """Start a sandbox SDK session. Returns session_id."""
        session_options["initial_prompt"] = initial_prompt
        return await self._sandbox.start_session(session_options)

    async def _cleanup_session(self, sandbox_session_id: str | None) -> None:
        """Stop the sandbox session if one was started."""
        if sandbox_session_id is None:
            return
        try:
            await self._sandbox.stop_session(sandbox_session_id)
        except Exception as e:
            log.warning("Failed to stop sandbox session %s: %s", sandbox_session_id, e)

    async def _run_rounds(
        self, stream: StreamProcessor, sandbox_session_id: str,
        run_context: RunContext, session: SessionGate, events: EventBus,
        custom_prompt: str | None, exec_timeout: int,
        pending_inject: str | None,
    ) -> str:
        """Execute the round loop. Returns final status."""
        status = "completed"

        for round_num in range(MAX_ROUNDS):
            log.info(
                "Round %d | Elapsed: %.0fm | Remaining: %s",
                round_num + 1,
                session.elapsed_minutes(), session.time_remaining_str(),
            )

            result = await stream.process(round_num, False)

            if result.should_stop:
                return result.final_status or "stopped"
            if result.session_ended:
                return status

            pending_inject = self._merge_injects(result, pending_inject)

            action = await self._check_between_round_event(
                events, sandbox_session_id, stream, run_context, session,
            )
            if action == "stop":
                return "stopped"
            if action == "continue":
                continue
            if action and action.startswith("inject:"):
                pending_inject = action[7:]

            await self._auto_commit_and_push(run_context, round_num, exec_timeout)

            if pending_inject:
                await self._deliver_inject(pending_inject, sandbox_session_id, run_context)
                pending_inject = None
                continue

            if session.is_unlocked():
                break

            await self._invoke_planner(
                sandbox_session_id, run_context, session, result, round_num,
                custom_prompt, exec_timeout,
            )

        return status

    def _merge_injects(
        self, result: RoundResult, pending_inject: str | None,
    ) -> str | None:
        """Merge pending injects from the round result."""
        if not result.pending_injects:
            return pending_inject
        if pending_inject:
            result.pending_injects.insert(0, pending_inject)
        if len(result.pending_injects) == 1:
            return result.pending_injects[0]
        return "\n\n".join(
            f"{i+1}. {msg}" for i, msg in enumerate(result.pending_injects)
        )

    async def _check_between_round_event(
        self, events: EventBus, sandbox_session_id: str,
        stream: StreamProcessor, run_context: RunContext, session: SessionGate,
    ) -> str | None:
        """Check and handle between-round events."""
        event = await events.drain()
        if not event:
            return None
        return await self._handle_between_round_event(
            event, sandbox_session_id, stream, run_context, session, events,
        )

    async def _deliver_inject(
        self, inject: str, sandbox_session_id: str, run_context: RunContext,
    ) -> None:
        """Record and deliver a pending inject message."""
        ts = datetime.now(timezone.utc).strftime("%H:%M")
        self._operator_messages.append((ts, inject))
        self._operator_messages = self._operator_messages[-MAX_OPERATOR_MESSAGES:]
        await db.log_audit(run_context.run_id, "prompt_injected", {"prompt": inject})
        await self._sandbox.send_message(
            sandbox_session_id, f"Operator message: {inject}",
        )

    async def _invoke_planner(
        self, sandbox_session_id: str, run_context: RunContext,
        session: SessionGate, result: RoundResult,
        round_num: int, custom_prompt: str | None,
        exec_timeout: int,
    ) -> None:
        """Build and send planner message to the sandbox session."""
        planner_msg, planner_meta = await self._build_planner_message(
            run_context, session, result, round_num, custom_prompt, exec_timeout,
        )
        await db.log_audit(run_context.run_id, "planner_invoked", planner_meta)
        await self._sandbox.send_message(
            sandbox_session_id,
            f"Call the planner subagent with this context:\n\n{planner_msg}",
        )

    async def _handle_between_round_event(
        self, event: dict, sandbox_session_id: str,
        stream: StreamProcessor, run_context: RunContext,
        session: SessionGate, events: EventBus,
    ) -> str | None:
        """Handle an event between rounds."""
        kind = event["event"]

        if kind == "stop":
            await self._sandbox.send_message(
                sandbox_session_id,
                self._prompts.build_stop_prompt(event.get("payload", "")),
            )
            await stream.process(0, False)
            return "stop"
        elif kind == "pause":
            result = await events.handle_pause(run_context.run_id)
            if result == "stop":
                return "stop"
            if result.startswith("inject:"):
                await self._sandbox.send_message(sandbox_session_id, result[7:])
                return "continue"
            if result == "unlock":
                session.force_unlock()
                await db.log_audit(run_context.run_id, "session_unlocked", {})
        elif kind == "inject":
            await db.log_audit(run_context.run_id, "prompt_injected", {
                "prompt": event.get("payload", ""), "delivery": "queued",
            })
            return f"inject:{event.get('payload', '')}"
        elif kind == "unlock":
            session.force_unlock()
            await db.log_audit(run_context.run_id, "session_unlocked", {})
        elif kind == "stuck_recovery":
            payload = event.get("payload", "")
            log.warning("Stuck subagent recovery between rounds: %s", payload[:LOG_PREVIEW_LIMIT])
            await db.log_audit(run_context.run_id, "stuck_recovery", {
                "agents": payload[:ROUND_SUMMARY_AUDIT_LIMIT],
            })
            return f"inject:A stuck subagent was detected. Recovery info: {payload}"

        return None

    async def _auto_commit_and_push(
        self, run_context: RunContext, round_num: int, exec_timeout: int,
    ) -> None:
        """Auto-commit uncommitted changes and push between rounds."""
        committed = False
        if await self._repo_ops.has_changes(exec_timeout):
            try:
                await self._repo_ops.run_git(["add", "."], exec_timeout, WORK_DIR)
                await self._repo_ops.run_git(
                    ["commit", "-m", f"Round {round_num + 1}"], exec_timeout, WORK_DIR,
                )
                committed = True
                log.info("Auto-committed round %d changes", round_num + 1)
            except RuntimeError as e:
                log.warning("Auto-commit failed: %s", e)
        if committed:
            try:
                await self._repo_ops.push_branch(run_context.branch_name, exec_timeout)
                log.info("Pushed branch %s", run_context.branch_name)
            except RuntimeError as e:
                log.warning("Push failed between rounds: %s", e)
                await db.log_audit(run_context.run_id, "push_failed", {"error": str(e)})

    async def _build_planner_message(
        self, run_context: RunContext, session: SessionGate,
        result: RoundResult, round_num: int, custom_prompt: str | None,
        exec_timeout: int,
    ) -> tuple[str, dict]:
        """Build the message sent to the planner subagent."""
        tool_summary = _summarize_tools(result.round_tools)
        files_changed = await self._git_files_changed(exec_timeout)
        commits = await self._git_recent_commits(exec_timeout)

        round_summary = "\n".join(result.round_text_chunks)[-ROUND_SUMMARY_LIMIT:] or "Agent worked silently."

        message = self._prompts.build_planner_message(
            round_num=round_num + 1,
            elapsed_minutes=session.elapsed_minutes(),
            duration_minutes=run_context.duration_minutes,
            tool_summary=tool_summary,
            files_changed=files_changed,
            commits=commits,
            cost_so_far=run_context.total_cost,
            round_summary=round_summary,
            original_prompt=custom_prompt or "General improvement pass.",
            operator_messages=self._operator_messages,
        )

        meta = {
            "round": round_num + 1,
            "tool_summary": tool_summary,
            "files_changed": files_changed[:FILES_CHANGED_LIMIT],
            "round_summary": round_summary[:ROUND_SUMMARY_AUDIT_LIMIT],
        }

        return message, meta

    async def _git_files_changed(self, exec_timeout: int) -> str:
        """Get list of changed files from git status."""
        try:
            return await self._repo_ops.run_git(
                ["diff", "--name-only", "HEAD~5"], exec_timeout, WORK_DIR,
            )
        except RuntimeError:
            return "(no git history)"

    async def _git_recent_commits(self, exec_timeout: int) -> str:
        """Get recent commit log summaries."""
        try:
            return await self._repo_ops.run_git(
                ["log", "--oneline", "-5"], exec_timeout, WORK_DIR,
            )
        except RuntimeError:
            return "(no commits yet)"


def _summarize_tools(round_tools: list[str]) -> str:
    """Summarize tool usage counts into a compact string."""
    tool_counts: dict[str, int] = {}
    for t in round_tools:
        tool_counts[t] = tool_counts.get(t, 0) + 1
    return ", ".join(
        f"{t} x{c}" for t, c in sorted(tool_counts.items(), key=lambda x: -x[1])[:10]
    )
