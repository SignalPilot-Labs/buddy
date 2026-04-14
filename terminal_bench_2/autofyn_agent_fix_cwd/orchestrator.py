"""AutoFyn orchestrator for Terminal-Bench — builds the claude CLI invocation."""

import json
import logging
import shlex
from typing import Any

from terminal_bench.constants import PROMPTS_DIR
from terminal_bench.prompts import load_caveman_skill, load_subagent_prompt

log = logging.getLogger("terminal_bench.orchestrator")


def build_cli_command(instruction: str, model: str, max_turns: int, claude_bin: str = "claude") -> str:
    """Return the full claude CLI command to run inside the container."""
    caveman = load_caveman_skill()
    system_prompt = (PROMPTS_DIR / "system.md").read_text(encoding="utf-8").strip()
    agents_json = json.dumps(_build_agents_dict(caveman))

    parts = [
        claude_bin,
        "--verbose",
        "-p", shlex.quote(instruction),
        "--append-system-prompt", shlex.quote(f"{system_prompt}\n\n{caveman}"),
        "--agents", shlex.quote(agents_json),
        "--permission-mode", "bypassPermissions",
        "--output-format", "stream-json",
        "--max-turns", str(max_turns),
        "--model", model,
    ]
    return " ".join(parts)


def _build_agents_dict(caveman: str) -> dict[str, Any]:
    """Build the agents JSON passed to --agents flag."""
    def prompt(name: str) -> str:
        return f"{load_subagent_prompt(name)}\n\n{caveman}"

    return {
        "planner": {
            "description": "Analyze progress and plan the next step. Call between build rounds.",
            "prompt": prompt("planner"),
            "model": "claude-opus-4-6",
            "tools": ["Read", "Write", "Glob", "Grep", "Bash", "WebSearch", "WebFetch"],
        },
        "builder": {
            "description": "Write code, implement features, create files. Use for all code generation tasks.",
            "prompt": prompt("builder"),
            "model": "claude-sonnet-4-6",
            "tools": ["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
        },
        "reviewer": {
            "description": "Review code, run tests, report bugs and quality issues. Call after every build.",
            "prompt": prompt("reviewer"),
            "model": "claude-opus-4-6",
            "tools": ["Read", "Write", "Glob", "Grep", "Bash", "WebSearch", "WebFetch"],
        },
        "explorer": {
            "description": "Explore files, find patterns, read external docs. Read-only research.",
            "prompt": prompt("explorer"),
            "model": "claude-sonnet-4-6",
            "tools": ["Read", "Glob", "Grep", "Bash", "WebSearch", "WebFetch"],
        },
    }
