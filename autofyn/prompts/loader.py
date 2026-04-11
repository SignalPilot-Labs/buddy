"""Prompt file loader and shared query renderers.

`load_markdown` reads a markdown file from the prompts directory.
`render_time_status` renders the time-status query with concrete minute
values — used by both the orchestrator prompt builder and the subagent
prompt builder so there is one source of truth for the wording.
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


def render_time_status(
    duration_minutes: float,
    time_remaining_minutes: float,
) -> str:
    """Render `query/time-status.md` with concrete minute values."""
    template = load_markdown("query/time-status")
    return (
        template
        .replace("{TIME_REMAINING_MINUTES}", str(max(int(time_remaining_minutes), 0)))
        .replace("{DURATION_MINUTES}", str(int(duration_minutes)))
    )
