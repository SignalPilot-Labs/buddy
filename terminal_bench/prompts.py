"""Prompt loader for the terminal_bench package."""

from claude_agent_sdk.types import SystemPromptPreset

from terminal_bench.constants import PROMPTS_DIR, SUBAGENTS_DIR


def load_system_prompt() -> SystemPromptPreset:
    """Load the terminal_bench system prompt as a claude_code preset."""
    text = (PROMPTS_DIR / "system.md").read_text(encoding="utf-8").strip()
    return SystemPromptPreset(type="preset", preset="claude_code", append=text)


def load_subagent_prompt(name: str) -> str:
    """Load a subagent prompt from terminal_bench/prompts/subagents/."""
    path = SUBAGENTS_DIR / f"{name}.md"
    return path.read_text(encoding="utf-8").strip()
