"""Harbor-compatible agent adapter for AutoFyn forks.

This module provides a harbor.BaseInstalledAgent wrapper that delegates to
the fork's orchestrator.build_cli_command().

It is loaded via --agent-import-path in the harbor run command.
PYTHONPATH is set to the fork's parent directory so that
`terminal_bench.orchestrator`, `terminal_bench.constants`, and
`terminal_bench.prompts` resolve to the correct fork's modules.

This adapter is infrastructure glue — not fork code. It bridges the
fork's business logic with harbor's agent API, since the Round 1
terminal-bench port removed harbor compatibility.
"""

import json
import logging
import os
from typing import Any, ClassVar

from harbor.agents.base import AgentContext
from harbor.agents.installed.base import BaseInstalledAgent
from harbor.environments.base import BaseEnvironment

from terminal_bench.constants import DEFAULT_MAX_TURNS, DEFAULT_MODEL, TASK_CWD
from terminal_bench.orchestrator import build_cli_command

log = logging.getLogger("terminal_bench.agent")

# Agent run timeout: 1 hour matches the historical harbor run configuration
AGENT_TIMEOUT_SEC: int = 60 * 60


class AutoFynAgent(BaseInstalledAgent):
    """Harbor-compatible AutoFyn agent that delegates to the fork's orchestrator."""

    CLI_FLAGS: ClassVar[list] = []
    ENV_VARS: ClassVar[list] = []

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._summary: dict[str, Any] | None = None

    @staticmethod
    def name() -> str:
        return "autofyn"

    def version(self) -> str | None:
        return "0.1.0"

    async def install(self, environment: BaseEnvironment) -> None:
        """Verify Claude Code CLI is available (pre-baked in the task container)."""
        await self.exec_as_agent(
            environment,
            'export PATH="$HOME/.local/bin:$PATH" && claude --version',
        )

    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        """Run the AutoFyn orchestrator on the given task instruction."""
        raw_model = self.model_name or os.environ.get("AUTOFYN_MODEL", DEFAULT_MODEL)
        model = raw_model.removeprefix("anthropic/")
        max_turns_str = os.environ.get("AUTOFYN_MAX_TURNS", "")
        max_turns = int(max_turns_str) if max_turns_str else DEFAULT_MAX_TURNS

        token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "")
        events_path = str(self.logs_dir / "events.jsonl")

        run_log = "/tmp/autofyn-run.jsonl"
        claude_bin = await self._find_claude_bin(environment)
        claude_cmd = build_cli_command(instruction, model, max_turns, claude_bin)

        token_export = f'export CLAUDE_CODE_OAUTH_TOKEN="{token}"; ' if token else ""
        cmd = (
            f'export PATH="$HOME/.local/bin:$PATH"; '
            f'export IS_SANDBOX=1; '
            f'export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1; '
            f'{token_export}'
            f'{claude_cmd} 2>&1 | tee {run_log} || true'
        )
        await self.exec_as_agent(
            environment,
            cmd,
            cwd=TASK_CWD,
            timeout_sec=AGENT_TIMEOUT_SEC,
        )
        read_result = await self.exec_as_agent(environment, f"cat {run_log}")
        stdout = read_result.stdout or ""

        stream_path = self.logs_dir / "claude-stream.jsonl"
        stream_path.write_text(stdout, encoding="utf-8")

        self._summary = _parse_stream_output(stdout, events_path)

    async def _find_claude_bin(self, environment: BaseEnvironment) -> str:
        """Return the full path to the claude CLI binary inside the container."""
        result = await self.exec_as_agent(
            environment,
            'export PATH="$HOME/.local/bin:$PATH"'
            '; p=$(which claude 2>/dev/null)'
            '; [ -z "$p" ] && p=$(find /root /home /usr/local/bin /usr/bin -name claude -type f 2>/dev/null | head -1)'
            '; [ -z "$p" ] && p=$(find / -maxdepth 8 -name claude -type f 2>/dev/null | head -1)'
            '; echo "${p:-claude}"',
        )
        stdout = (result.stdout or "").strip()
        return stdout.splitlines()[0] if stdout else "claude"

    def populate_context_post_run(self, context: AgentContext) -> None:
        """Report token usage and cost to Harbor's AgentContext."""
        if self._summary is None:
            return
        summary = self._summary
        if summary.get("input_tokens") is not None:
            context.n_input_tokens = summary["input_tokens"]
        if summary.get("output_tokens") is not None:
            context.n_output_tokens = summary["output_tokens"]
        if summary.get("total_cost_usd") is not None:
            context.cost_usd = summary["total_cost_usd"]


def _truncate(value: Any, limit: int = 500) -> Any:
    """Truncate large strings in tool inputs/outputs for JSONL storage."""
    if isinstance(value, str) and len(value) > limit:
        return value[:limit] + "..."
    if isinstance(value, dict):
        return {k: _truncate(v, limit) for k, v in value.items()}
    return value


def _parse_stream_output(stdout: str, events_path: str) -> dict[str, Any]:
    """Parse claude stream-json output into JSONL events and summary dict."""
    summary: dict[str, Any] = {
        "total_cost_usd": None,
        "num_turns": None,
        "input_tokens": None,
        "output_tokens": None,
    }

    with open(events_path, "a", encoding="utf-8") as f:
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            event_type = event.get("type", "")

            if event_type == "assistant":
                msg = event.get("message", {})
                for block in msg.get("content", []):
                    if block.get("type") == "tool_use":
                        f.write(json.dumps({
                            "event": "tool_use",
                            "tool": block.get("name"),
                            "input": _truncate(block.get("input", {})),
                        }) + "\n")

            elif event_type == "tool_result":
                f.write(json.dumps({
                    "event": "tool_result",
                    "tool_use_id": event.get("tool_use_id"),
                    "content": _truncate(event.get("content")),
                }) + "\n")

            elif event_type == "result":
                usage = event.get("usage", {})
                summary["total_cost_usd"] = event.get("total_cost_usd")
                summary["num_turns"] = event.get("num_turns")
                summary["input_tokens"] = usage.get("input_tokens")
                summary["output_tokens"] = usage.get("output_tokens")
                f.write(json.dumps({"event": "session_complete", **summary}) + "\n")

    return summary
