"""Prompt loader for the terminal_bench package."""

import json
import re
from pathlib import Path

from claude_agent_sdk.types import SystemPromptPreset

from terminal_bench.constants import (
    CAVEMAN_PLUGIN_KEY,
    CAVEMAN_SKILL_RELATIVE,
    CLAUDE_PLUGINS_JSON,
    PROMPTS_DIR,
    SUBAGENTS_DIR,
)

_YAML_FRONTMATTER = re.compile(r"^---\n.*?\n---\n", re.DOTALL)


def load_system_prompt() -> SystemPromptPreset:
    """Load the terminal_bench system prompt as a claude_code preset."""
    text = (PROMPTS_DIR / "system.md").read_text(encoding="utf-8").strip()
    return SystemPromptPreset(type="preset", preset="claude_code", append=text)


def load_subagent_prompt(name: str) -> str:
    """Load a subagent prompt from terminal_bench/prompts/subagents/."""
    path = SUBAGENTS_DIR / f"{name}.md"
    return path.read_text(encoding="utf-8").strip()


def load_caveman_skill() -> str:
    """Load caveman SKILL.md from the installed Claude plugin, stripping YAML frontmatter."""
    plugins = json.loads(CLAUDE_PLUGINS_JSON.read_text(encoding="utf-8"))
    installs = plugins["plugins"][CAVEMAN_PLUGIN_KEY]
    install_path = Path(installs[0]["installPath"])
    skill_text = (install_path / CAVEMAN_SKILL_RELATIVE).read_text(encoding="utf-8")
    return _YAML_FRONTMATTER.sub("", skill_text).strip()
