"""AutoFyn orchestrator for Terminal-Bench — builds the claude CLI invocation.

The agent runs claude CLI *inside* Harbor's container via exec_as_agent().
This module builds the command and parses the stream-json output into
JSONL events and AgentContext fields.
"""

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
    agents_json = json.dumps(_build_agents_dict())

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


def parse_stream_output(stdout: str, events_path: str) -> dict[str, Any]:
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


def _build_agents_dict() -> dict[str, Any]:
    """Build the agents JSON passed to --agents flag."""
    return {
        "planner": {
            "description": "Analyze progress and plan the next step. Call between build rounds.",
            "prompt": load_subagent_prompt("planner"),
            "model": "claude-opus-4-6",
            "tools": ["Read", "Write", "Glob", "Grep", "Bash", "WebSearch", "WebFetch"],
        },
        "builder": {
            "description": "Write code, implement features, create files. Use for all code generation tasks.",
            "prompt": load_subagent_prompt("builder"),
            "model": "claude-sonnet-4-6",
            "tools": ["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
        },
        "reviewer": {
            "description": "Review code, run tests, report bugs and quality issues. Call after every build.",
            "prompt": load_subagent_prompt("reviewer"),
            "model": "claude-opus-4-6",
            "tools": ["Read", "Write", "Glob", "Grep", "Bash", "WebSearch", "WebFetch"],
        },
        "explorer": {
            "description": "Explore files, find patterns, read external docs. Read-only research.",
            "prompt": load_subagent_prompt("explorer"),
            "model": "claude-sonnet-4-6",
            "tools": ["Read", "Glob", "Grep", "Bash", "WebSearch", "WebFetch"],
        },
    }


def _truncate(value: Any, limit: int = 500) -> Any:
    """Truncate large strings in tool inputs/outputs for JSONL storage."""
    if isinstance(value, str) and len(value) > limit:
        return value[:limit] + "..."
    if isinstance(value, dict):
        return {k: _truncate(v, limit) for k, v in value.items()}
    return value
