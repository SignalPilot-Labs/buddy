"""AutoFyn agent (verify) — AbstractInstalledAgent for Terminal-Bench 2.0."""

import os
import shlex
from pathlib import Path

from terminal_bench.agents.installed_agents.abstract_installed_agent import AbstractInstalledAgent
from terminal_bench.terminal.models import TerminalCommand

from terminal_bench.constants import DEFAULT_MAX_TURNS, DEFAULT_MODEL, TASK_CWD
from terminal_bench.orchestrator import build_cli_command


class AutoFynAgent(AbstractInstalledAgent):
    """AutoFyn multi-subagent orchestrator running inside the task container."""

    def __init__(self, model_name: str | None = None, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._model_name = model_name

    @staticmethod
    def name() -> str:
        return "autofyn"

    @property
    def _env(self) -> dict[str, str]:
        env: dict[str, str] = {
            "CLAUDE_CODE_OAUTH_TOKEN": os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", ""),
            "IS_SANDBOX": "1",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        }
        if self._model_name:
            env["ANTHROPIC_MODEL"] = self._model_name.removeprefix("anthropic/")
        autofyn_model = os.environ.get("AUTOFYN_MODEL")
        if autofyn_model:
            env["AUTOFYN_MODEL"] = autofyn_model
        autofyn_max_turns = os.environ.get("AUTOFYN_MAX_TURNS")
        if autofyn_max_turns:
            env["AUTOFYN_MAX_TURNS"] = autofyn_max_turns
        return env

    @property
    def _install_agent_script_path(self) -> Path:
        return self._get_templated_script_path("setup.sh.j2")

    def _run_agent_commands(self, instruction: str) -> list[TerminalCommand]:
        raw_model = self._model_name or os.environ.get("AUTOFYN_MODEL") or DEFAULT_MODEL
        model = raw_model.removeprefix("anthropic/")
        max_turns_str = os.environ.get("AUTOFYN_MAX_TURNS")
        max_turns = int(max_turns_str) if max_turns_str else DEFAULT_MAX_TURNS

        claude_cmd = build_cli_command(instruction, model, max_turns, "claude")
        cmd = f'export PATH="$HOME/.local/bin:$PATH"; cd {shlex.quote(TASK_CWD)}; {claude_cmd} || true'
        return [
            TerminalCommand(
                command=cmd,
                block=True,
                max_timeout_sec=float("inf"),
                min_timeout_sec=0.0,
                append_enter=True,
            )
        ]
