"""Agent loop: round iteration and between-round decisions.

AgentLoop iterates rounds, delegates stream processing to StreamProcessor,
and decides whether to continue or stop. The main agent (orchestrator)
handles planner/builder/reviewer delegation via subagents — the loop
just keeps it running and handles control events between rounds.
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

from utils import db
from utils.constants import COMMIT_MSG_PATH, FALLBACK_COMMIT_MSG, FILES_CHANGED_LIMIT, LOG_PREVIEW_LIMIT, MAX_OPERATOR_MESSAGES, MAX_ROUNDS, ROUND_SUMMARY_AUDIT_LIMIT, ROUND_SUMMARY_LIMIT
from utils.git import GitWorkspace
from utils.models import RoundResult, RunContext
from utils.prompts import PromptLoader
from core.event_bus import EventBus
from core.stream import StreamProcessor
from tools.session import SessionGate

log = logging.getLogger("core.loop")


class AgentLoop:
    """Iterates rounds, handles between-round events, delegates stream processing.

    Public API:
        execute(options, ctx, session, events, initial_prompt, custom_prompt) -> str
    """

    def __init__(self, git: GitWorkspace, prompts: PromptLoader):
        self._git = git
        self._prompts = prompts
        self._operator_messages: list[tuple[str, str]] = []  # (timestamp, message)

    async def execute(
        self, options: ClaudeAgentOptions, ctx: RunContext,
        session: SessionGate, events: EventBus,
        initial_prompt: str, custom_prompt: str | None,
    ) -> str:
        """Run the agent loop. Returns final status string."""
        model = options.model or os.environ.get("AGENT_MODEL", "opus")
        fallback_model = options.fallback_model
        status = "completed"
        pending_inject: str | None = None

        try:
            async with ClaudeSDKClient(options=options) as client:
                stream = StreamProcessor(client, ctx, session, events, self._prompts, model, fallback_model)
                await client.query(initial_prompt)

                for round_num in range(MAX_ROUNDS):
                    log.info("Round %d | Elapsed: %.0fm | Remaining: %s",
                             round_num + 1,
                             session.elapsed_minutes(), session.time_remaining_str())

                    result = await stream.process(round_num, False)

                    if result.should_stop:
                        status = result.final_status or "stopped"
                        break
                    if result.session_ended:
                        break

                    # Pick up injects from mid-round
                    if result.pending_injects:
                        if pending_inject:
                            result.pending_injects.insert(0, pending_inject)
                        if len(result.pending_injects) == 1:
                            pending_inject = result.pending_injects[0]
                        else:
                            pending_inject = "\n\n".join(
                                f"{i+1}. {msg}" for i, msg in enumerate(result.pending_injects)
                            )

                    # Between-round event check
                    event = await events.drain()
                    if event:
                        action = await self._handle_between_round_event(event, client, stream, ctx, session, events)
                        if action == "stop":
                            status = "stopped"
                            break
                        if action == "continue":
                            continue
                        if action and action.startswith("inject:"):
                            pending_inject = action[7:]

                    # Commit and push between rounds
                    await self._commit_and_push(ctx, round_num)

                    # Decide whether to continue
                    if session.is_unlocked():
                        if pending_inject:
                            await db.log_audit(ctx.run_id, "prompt_injected", {"prompt": pending_inject})
                            await client.query(f"Operator message: {pending_inject}")
                            pending_inject = None
                            continue
                        break
                    else:
                        # Time-locked: call planner subagent for next step
                        if pending_inject:
                            ts = datetime.now(timezone.utc).strftime("%H:%M")
                            self._operator_messages.append((ts, pending_inject))
                            self._operator_messages = self._operator_messages[-MAX_OPERATOR_MESSAGES:]
                            await db.log_audit(ctx.run_id, "prompt_injected", {"prompt": pending_inject})
                            pending_inject = None
                        planner_msg, planner_meta = self._build_planner_message(ctx, session, result, round_num, custom_prompt)
                        await db.log_audit(ctx.run_id, "planner_invoked", planner_meta)
                        await client.query(f"Call the planner subagent with this context:\n\n{planner_msg}")

        except asyncio.CancelledError:
            status = "killed"
            await db.log_audit(ctx.run_id, "killed", {"elapsed_minutes": round(session.elapsed_minutes(), 1)})
        except Exception as e:
            log.error("Fatal error: %s", e, exc_info=True)
            status = "error"
            await db.log_audit(ctx.run_id, "fatal_error", {"error": str(e)})

        return status

    async def _commit_and_push(self, ctx: RunContext, round_num: int) -> None:
        """Commit any changes and push between rounds."""
        if not self._git.has_changes():
            return
        msg = self._read_commit_message(round_num + 1)
        try:
            self._git.run_git(["add", "-u"])
            self._git.run_git(["commit", "-m", msg])
            await db.log_audit(ctx.run_id, "auto_commit", {"round": round_num + 1, "message": msg})
            log.info("Committed round %d: %s", round_num + 1, msg)
        except RuntimeError as e:
            log.warning("Commit failed between rounds: %s", e)
            return
        try:
            self._git.push_branch(ctx.branch_name)
            log.info("Pushed branch %s", ctx.branch_name)
        except Exception as e:
            log.warning("Push failed between rounds: %s", e)
            await db.log_audit(ctx.run_id, "push_failed", {"error": str(e)})

    def _read_commit_message(self, round_num: int) -> str:
        """Read commit message from /tmp/commit-msg.txt, fall back to 'Round N'."""
        path = Path(COMMIT_MSG_PATH)
        if path.is_file():
            msg = path.read_text().strip()
            path.unlink()
            if msg:
                return msg
        return FALLBACK_COMMIT_MSG.format(round_num=round_num)

    async def _handle_between_round_event(
        self, event: dict, client, stream: StreamProcessor,
        ctx: RunContext, session: SessionGate, events: EventBus,
    ) -> str | None:
        """Handle an event between rounds."""
        kind = event["event"]

        if kind == "stop":
            await client.query(self._prompts.build_stop_prompt(event.get("payload", "")))
            await stream.process(0, False)
            return "stop"
        elif kind == "pause":
            result = await events.handle_pause(ctx.run_id)
            if result == "stop":
                return "stop"
            if result.startswith("inject:"):
                await client.query(result[7:])
                return "continue"
            if result == "unlock":
                session.force_unlock()
                await db.log_audit(ctx.run_id, "session_unlocked", {})
        elif kind == "inject":
            await db.log_audit(ctx.run_id, "prompt_injected", {
                "prompt": event.get("payload", ""), "delivery": "queued",
            })
            return f"inject:{event.get('payload', '')}"
        elif kind == "unlock":
            session.force_unlock()
            await db.log_audit(ctx.run_id, "session_unlocked", {})
        elif kind == "stuck_recovery":
            payload = event.get("payload", "")
            log.warning("Stuck subagent recovery triggered between rounds: %s", payload[:LOG_PREVIEW_LIMIT])
            await db.log_audit(ctx.run_id, "stuck_recovery", {"agents": payload[:ROUND_SUMMARY_AUDIT_LIMIT]})
            # Inject recovery instructions into next round
            return f"inject:A stuck subagent was detected. Recovery info: {payload}"

        return None

    def _build_planner_message(
        self, ctx: RunContext, session: SessionGate,
        result: RoundResult, round_num: int, custom_prompt: str | None,
    ) -> tuple[str, dict]:
        """Build the message sent to the planner subagent. Returns (message, audit_meta)."""
        work_dir = self._git.get_work_dir()

        tool_counts: dict[str, int] = {}
        for t in result.round_tools:
            tool_counts[t] = tool_counts.get(t, 0) + 1
        tool_summary = ", ".join(
            f"{t} x{c}" for t, c in sorted(tool_counts.items(), key=lambda x: -x[1])[:10]
        )

        try:
            files_changed = self._git.run_git(["diff", "--name-only", "HEAD~5..HEAD"], cwd=work_dir)
        except Exception:
            files_changed = "(unable to determine)"
        try:
            commits = self._git.run_git(["log", "--oneline", "-5"], cwd=work_dir)
        except Exception:
            commits = "(none yet)"

        round_summary = "\n".join(result.round_text_chunks)[-ROUND_SUMMARY_LIMIT:] or "Agent worked silently."

        message = self._prompts.build_planner_message(
            round_num=round_num + 1,
            elapsed_minutes=session.elapsed_minutes(),
            duration_minutes=ctx.duration_minutes,
            tool_summary=tool_summary,
            files_changed=files_changed,
            commits=commits,
            cost_so_far=ctx.total_cost,
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
