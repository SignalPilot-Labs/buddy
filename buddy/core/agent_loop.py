"""Agent loop: round iteration and between-round decisions.

AgentLoop iterates rounds, delegates stream processing to StreamProcessor,
and decides whether to continue or stop. The main agent (orchestrator)
handles planner/builder/reviewer delegation via subagents — the loop
just keeps it running and handles control events between rounds.
"""

import asyncio
import logging
import os

from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

from utils import db
from utils.constants import MAX_ROUNDS, ROUND_SUMMARY_LIMIT, ROUND_SUMMARY_AUDIT_LIMIT, FILES_CHANGED_LIMIT
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
                    is_planning = ctx.agent_role == "planner"
                    log.info("Round %d [%s] | Elapsed: %.0fm | Remaining: %s",
                             round_num + 1, ctx.agent_role.upper(),
                             session.elapsed_minutes(), session.time_remaining_str())

                    result = await stream.process(round_num, False)

                    # Reset to worker after planner round
                    if is_planning:
                        ctx.agent_role = "worker"

                    if result.should_stop:
                        status = result.final_status or "stopped"
                        break
                    if result.session_ended:
                        break

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

                    # Push commits between rounds
                    try:
                        self._git.push_branch(ctx.branch_name)
                    except Exception:
                        pass

                    # Decide whether to continue
                    if session.is_unlocked():
                        if pending_inject:
                            await db.log_audit(ctx.run_id, "prompt_injected", {"prompt": pending_inject})
                            await client.query(f"Operator message: {pending_inject}")
                            pending_inject = None
                            continue
                        break
                    else:
                        # Time-locked: switch to planner mode, send round context
                        ctx.agent_role = "planner"
                        planner_prompt, planner_meta = self._build_planner_prompt(ctx, session, result, round_num, custom_prompt)
                        if pending_inject:
                            planner_prompt += f"\n\nOperator message: {pending_inject}"
                            await db.log_audit(ctx.run_id, "prompt_injected", {"prompt": pending_inject})
                            pending_inject = None
                        await db.log_audit(ctx.run_id, "planner_invoked", planner_meta)
                        await client.query(planner_prompt)

        except asyncio.CancelledError:
            status = "killed"
            await db.log_audit(ctx.run_id, "killed", {"elapsed_minutes": round(session.elapsed_minutes(), 1)})
        except Exception as e:
            log.error("Fatal error: %s", e, exc_info=True)
            status = "error"
            await db.log_audit(ctx.run_id, "fatal_error", {"error": str(e)})

        return status

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

        return None

    def _build_planner_prompt(
        self, ctx: RunContext, session: SessionGate,
        result: RoundResult, round_num: int, custom_prompt: str | None,
    ) -> tuple[str, dict]:
        """Build the planner query prompt with round context. Returns (prompt, audit_meta)."""
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

        prompt = self._prompts.build_planner_prompt(
            round_num=round_num + 1,
            elapsed_minutes=session.elapsed_minutes(),
            duration_minutes=ctx.duration_minutes,
            tool_summary=tool_summary,
            files_changed=files_changed,
            commits=commits,
            cost_so_far=ctx.total_cost,
            round_summary=round_summary,
            original_prompt=custom_prompt or "General self-improvement pass.",
        )

        meta = {
            "round": round_num + 1,
            "tool_summary": tool_summary,
            "files_changed": files_changed[:FILES_CHANGED_LIMIT],
            "round_summary": round_summary[:ROUND_SUMMARY_AUDIT_LIMIT],
        }

        return prompt, meta
