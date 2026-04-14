"""AutoFyn orchestrator for Terminal-Bench — builds the claude CLI invocation (single-session mode)."""

import logging
import shlex

from terminal_bench.constants import PROMPTS_DIR

log = logging.getLogger("terminal_bench.orchestrator")


def build_cli_command(instruction: str, model: str, max_turns: int, claude_bin: str) -> str:
    """Return a claude CLI command for single-session mode (no subagents).

    Bypasses the multi-subagent orchestrator entirely by omitting --agents.
    The combined single_session.md prompt covers planning, building, and verification.
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


def build_single_session_command(instruction: str, model: str, max_turns: int, claude_bin: str) -> str:
    """Alias for build_cli_command — both use single_session.md prompt."""
    return build_cli_command(instruction, model, max_turns, claude_bin)
