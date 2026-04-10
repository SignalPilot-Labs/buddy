"""Prompt file loader.

One function: read a markdown file from the prompts directory and return
its contents. The orchestrator / subagent builders layer on top of this.
"""

from utils.constants import PROMPTS_DIR, PROMPTS_FALLBACK_DIR


def load_markdown(name: str) -> str:
    """Load a markdown file by name (path relative to prompts/).

    Raises FileNotFoundError if the file does not exist in either
    `PROMPTS_DIR` (the runtime install location) or
    `PROMPTS_FALLBACK_DIR` (the sibling path during local dev).
    """
    for root in (PROMPTS_DIR, PROMPTS_FALLBACK_DIR):
        path = root / f"{name}.md"
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
    raise FileNotFoundError(f"prompt file not found: {name}.md")
