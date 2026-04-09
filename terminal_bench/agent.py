"""AutoFyn Harbor agent — BaseInstalledAgent for Terminal-Bench 2.0.

Usage:
    harbor run -d terminal-bench/terminal-bench-2 \\
        --agent-import-path terminal_bench.agent:AutoFynAgent \\
        -m anthropic/claude-opus-4-6 \\
        --tasks dna-assembly,gpt2-codegolf,...
"""

import logging
import os
from typing import Any, ClassVar

from harbor.agents.installed.base import BaseInstalledAgent
from harbor.agents.base import AgentContext
from harbor.environments.base import BaseEnvironment

from terminal_bench.constants import AGENT_TIMEOUT_SEC, DEFAULT_MAX_TURNS, DEFAULT_MODEL, TASK_CWD
from terminal_bench.orchestrator import build_cli_command, parse_stream_output

log = logging.getLogger("terminal_bench.agent")


class AutoFynAgent(BaseInstalledAgent):
    """AutoFyn multi-subagent orchestrator running inside Harbor's task container."""

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
        """Install Claude Code CLI inside the task container."""
        await self.exec_as_root(
            environment,
            "if command -v apk &>/dev/null; then"
            "  apk add --no-cache curl bash nodejs npm;"
            " elif command -v apt-get &>/dev/null; then"
            "  apt-get update -qq && apt-get install -y -q curl;"
            " fi",
            env={"DEBIAN_FRONTEND": "noninteractive"},
            timeout_sec=120,
        )
        await self.exec_as_agent(
            environment,
            'if command -v apk &>/dev/null; then'
            '  npm install -g @anthropic-ai/claude-code;'
            ' else'
            '  curl -fsSL https://claude.ai/install.sh | bash;'
            ' fi'
            ' && export PATH="$HOME/.local/bin:$PATH"'
            ' && claude --version',
            timeout_sec=300,
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

        # Inline token as a shell export so it's set regardless of Docker env passing
        token_export = f'export CLAUDE_CODE_OAUTH_TOKEN="{token}"; ' if token else ""
        # Tee to file so we can read the full output; absorb claude's exit code
        # since non-zero can mean task failure, not infra failure.
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

        # Persist raw stream-json for debugging
        stream_path = self.logs_dir / "claude-stream.jsonl"
        stream_path.write_text(stdout, encoding="utf-8")

        self._summary = parse_stream_output(stdout, events_path)

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
