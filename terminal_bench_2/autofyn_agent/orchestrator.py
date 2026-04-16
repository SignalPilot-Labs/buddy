"""AutoFyn orchestrator for Terminal-Bench — builds the claude CLI invocation (single-session mode)."""

import logging
import shlex

from terminal_bench.constants import PROMPTS_DIR

log = logging.getLogger("terminal_bench.orchestrator")


def build_cli_command(instruction: str, model: str, max_turns: int, claude_bin: str) -> str:
    """Return the full claude CLI command for single-session mode.

    Omits --agents entirely. The combined single_session.md prompt covers
    planning, building, and verification without subagent delegation.
    """
    single_session_prompt = (PROMPTS_DIR / "single_session.md").read_text(encoding="utf-8").strip()

    parts = [
        claude_bin,
        "--verbose",
        "-p", shlex.quote(instruction),
        "--append-system-prompt", shlex.quote(single_session_prompt),
        "--permission-mode", "bypassPermissions",
        "--output-format", "stream-json",
        "--max-turns", str(max_turns),
        "--model", model,
    ]
    return " ".join(parts)
