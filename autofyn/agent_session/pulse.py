"""PulseWatchdog — periodic stuck-subagent and tool-timeout detection.

Runs as a background asyncio task (via `asyncio.create_task`) and is
cancelled externally when the round ends. Each cycle checks for stuck
subagents and timed-out tool calls, interrupting the session and
injecting context so the orchestrator can recover.
"""

import asyncio
import logging

from prompts.loader import render_stuck_recovery, render_tool_timeout
from sandbox_client.client import SandboxClient
from user.inbox import UserInbox
from agent_session.tracker import SubagentTracker
from utils import db
from utils.constants import pulse_check_interval_sec
from utils.run_config import RunAgentConfig

log = logging.getLogger("session.pulse")


class PulseWatchdog:
    """Periodic watchdog for stuck subagents and timed-out tool calls.

    Two checks each cycle:
    1. Stuck subagents (idle > subagent_idle_kill_sec) — interrupt + inject recovery.
    2. Timed-out tool calls (running > tool_call_timeout_sec) — interrupt + inject timeout.

    Only one recovery is triggered per cycle to avoid double-interrupting.
    """

    def __init__(
        self,
        sandbox: SandboxClient,
        run_id: str,
        rid: str,
        inbox: UserInbox,
        run_config: RunAgentConfig,
    ) -> None:
        self._sandbox = sandbox
        self._run_id = run_id
        self._rid = rid
        self._inbox = inbox
        self._run_config = run_config

    async def run(self, tracker: SubagentTracker, session_id: str) -> None:
        """Infinite loop — meant to be wrapped in asyncio.create_task and cancelled externally."""
        while True:
            await asyncio.sleep(pulse_check_interval_sec())
            if await self._check_stuck_subagents(tracker, session_id):
                continue
            await self._check_timed_out_tools(tracker, session_id)

    async def _check_stuck_subagents(
        self,
        tracker: SubagentTracker,
        session_id: str,
    ) -> bool:
        """Interrupt stuck subagents and notify the orchestrator.

        Returns True if any recovery was triggered.
        """
        stuck = tracker.stuck_subagents()
        if not stuck:
            return False
        descriptions = [
            f"{s.agent_type} ({s.agent_id[:8]}, idle {s.idle_seconds}s)"
            for s in stuck
        ]
        log.warning(
            "[%s] Stuck subagent(s) — interrupting: %s",
            self._rid,
            ", ".join(descriptions),
        )
        await db.log_audit(
            self._run_id,
            "stuck_recovery",
            {
                "stuck": [
                    {
                        "agent_id": s.agent_id,
                        "agent_type": s.agent_type,
                        "idle_seconds": s.idle_seconds,
                        "total_seconds": s.total_seconds,
                    }
                    for s in stuck
                ],
            },
        )
        for s in stuck:
            tracker.record_stop(s.agent_id)
        await self._sandbox.session.interrupt(session_id)
        agent_names = ", ".join(s.agent_type for s in stuck)
        self._inbox.push(
            "inject",
            render_stuck_recovery(agent_names, self._run_config.subagent_idle_kill_sec // 60),
        )
        return True

    async def _check_timed_out_tools(
        self,
        tracker: SubagentTracker,
        session_id: str,
    ) -> None:
        """Interrupt tool calls that exceeded tool_call_timeout_sec."""
        timed_out = tracker.timed_out_tools()
        if not timed_out:
            return
        for key, elapsed in timed_out:
            log.warning(
                "[%s] Tool call timed out (%s, %ds) — interrupting",
                self._rid,
                key[:8],
                elapsed,
            )
            await db.log_audit(
                self._run_id,
                "tool_timeout",
                {"agent_key": key, "elapsed_seconds": elapsed},
            )
        for key, _ in timed_out:
            tracker.clear_tool_state(key)
        max_elapsed = max(e for _, e in timed_out)
        await self._sandbox.session.interrupt(session_id)
        self._inbox.push(
            "inject",
            render_tool_timeout(max_elapsed // 60),
        )
