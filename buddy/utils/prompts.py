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

    def build_planner_message(
        self,
        round_num: int,
        elapsed_minutes: float,
        duration_minutes: float,
        tool_summary: str,
        files_changed: str,
        commits: str,
        cost_so_far: float,
        round_summary: str,
        original_prompt: str,
        last_plan: str,
        last_review: str,
        operator_messages: list[tuple[str, str]],
    ) -> str:
        """Build the message sent to the planner subagent each round."""
        if duration_minutes > 0:
            pct = min(100, int((elapsed_minutes / duration_minutes) * 100))
            elapsed_str = f"{int(elapsed_minutes)}m"
            duration_str = f"{int(duration_minutes)}m"
        else:
            pct = 0
            elapsed_str = f"{int(elapsed_minutes)}m"
            duration_str = "unlimited"

        last_plan_section = "## Last Plan\n\n(none)"
        if last_plan:
            last_plan_section = f"## Last Plan\n\n{last_plan}"

        review_section = "## Last Review Results\n\n(none)"
        if last_review:
            review_section = f"## Last Review Results\n\n{last_review}"

        operator_section = "## Operator Messages\n\n(none)"
        if operator_messages:
            msgs = "\n".join(f"- [{ts}] {msg}" for ts, msg in operator_messages)
            operator_section = f"## Operator Messages\n\nLatest takes priority.\n\n{msgs}"

        template = self._load("query/planner")
        return template.format(
            round_num=round_num,
            elapsed=elapsed_str,
            duration=duration_str,
            pct_complete=pct,
            tool_summary=tool_summary or "none",
            files_changed=files_changed or "none",
            commits=commits or "none",
            cost_so_far=f"{cost_so_far:.2f}",
            round_summary=round_summary or "No summary available.",
            original_prompt=original_prompt or "General improvement pass.",
            last_plan_section=last_plan_section,
            review_section=review_section,
            operator_section=operator_section,
        )

    def build_reviewer_message(self, extra_context: str) -> str:
        """Build the message sent to the reviewer subagent."""
        template = self._load("query/reviewer")
        return template.format(
            extra_context=extra_context or "",
        )

    def build_stop_prompt(self, reason: str) -> str:
        """Load the stop prompt, optionally prefixed with a reason."""
        base = self._load("query/stop")
        if reason:
            return f"Stop reason: {reason}\n\n{base}"
        return base

    def load_subagent_prompt(self, name: str) -> str:
        """Load a subagent system prompt from prompts/subagents/{name}.md."""
        return self._load(f"subagents/{name}")
