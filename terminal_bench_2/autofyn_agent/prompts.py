"""Prompt loader for the terminal_bench package."""

from claude_agent_sdk.types import SystemPromptPreset

from terminal_bench.constants import PROMPTS_DIR


def load_system_prompt() -> SystemPromptPreset:
    """Load the terminal_bench system prompt as a claude_code preset.

    Retained for rollback to multi-subagent mode. Not called in single-session path.
    """
    text = (PROMPTS_DIR / "system.md").read_text(encoding="utf-8").strip()
    return SystemPromptPreset(type="preset", preset="claude_code", append=text)
