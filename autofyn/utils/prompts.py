"""Prompt management — loads prompts from markdown files.

PromptLoader resolves prompt directories and loads templates.
"""

from claude_agent_sdk.types import SystemPromptPreset

from utils.constants import PROMPTS_DIR, PROMPTS_FALLBACK_DIR


class PromptLoader:
    """Loads prompt markdown files from the prompts/ directory."""

    def _load(self, name: str) -> str:
        """Load a prompt markdown file by name (path relative to prompts/)."""
        for d in (PROMPTS_DIR, PROMPTS_FALLBACK_DIR):
            path = d / f"{name}.md"
            if path.exists():
                return path.read_text(encoding="utf-8").strip()
        raise FileNotFoundError(f"Prompt file not found: {name}.md")

    def build_system_prompt(
        self, custom_focus: str | None, duration_minutes: float
    ) -> SystemPromptPreset:
        """Build the system prompt from markdown files."""
        parts = [self._load("system")]

        if duration_minutes > 0:
            if duration_minutes >= 60:
                h = int(duration_minutes // 60)
                m = int(duration_minutes % 60)
                dur = f"{h}h {m}m" if m else f"{h}h"
            else:
                dur = f"{int(duration_minutes)}m"
            parts.append(self._load("timed-session").replace("{duration}", dur))

        if custom_focus:
            parts.append(f"## Additional Focus\n{custom_focus}")

        return SystemPromptPreset(
            type="preset", preset="claude_code", append="\n\n".join(parts)
        )

    def build_initial_prompt(self) -> str:
        """Load the initial prompt for a new run."""
        return self._load("query/initial")

    def build_continuation_prompt(self) -> str:
        """Load the continuation prompt."""
        return self._load("query/continue")

    def build_stop_prompt(self, reason: str) -> str:
        """Load the stop prompt, optionally prefixed with a reason."""
        base = self._load("query/stop")
        if reason:
            return f"Stop reason: {reason}\n\n{base}"
        return base

    def build_idle_nudge(self, idle_seconds: int) -> str:
        """Load the idle nudge prompt, formatted with the actual timeout."""
        minutes = idle_seconds // 60
        idle_timeout = f"{minutes} minute{'s' if minutes != 1 else ''}"
        return self._load("query/idle_nudge").replace("{idle_timeout}", idle_timeout)

    def load_subagent_prompt(self, name: str) -> str:
        """Load a subagent system prompt with shared rules appended.

        Git rules are appended to all subagents.
        Verification rules are only appended to build and review phase agents.
        """
        agent = self._load(f"subagents/{name}")
        git = self._load("git-rules")
        agents_with_verification = (
            "build/backend-dev",
            "build/frontend-dev",
            "review/code-reviewer",
        )
        if name in agents_with_verification:
            verification = self._load("verification-rules")
            return f"{agent}\n\n{git}\n\n{verification}"
        return f"{agent}\n\n{git}"
