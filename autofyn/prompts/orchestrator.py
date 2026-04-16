"""Orchestrator prompt builder — per-round system prompt assembly.

Each round gets a fresh Claude SDK session. `build_round_system_prompt`
loads the static `system.md` template, substitutes `{ROUND_NUMBER}`, and
appends dynamic context blocks (time status when time-locked, prior
rounds summary, prior-round file index, user messages).
"""

from claude_agent_sdk.types import SystemPromptPreset

from prompts.loader import load_markdown, render_environment, render_time_status
from utils.constants import TOOL_CALL_TIMEOUT_SEC
from utils.models import RoundContext, RoundsMetadata, UserAction


def build_round_system_prompt(context: RoundContext) -> SystemPromptPreset:
    """Build the system prompt for a single round's orchestrator session."""
    template = load_markdown("system")
    body = _apply_placeholders(template, context)

    env_block = render_environment(
        round_number=context.round_number,
        tool_call_timeout_min=TOOL_CALL_TIMEOUT_SEC // 60,
        host_mounts=context.host_mounts,
    )
    sections: list[str] = [body, env_block, load_markdown("query/git-rules")]

    if context.duration_minutes > 0:
        sections.append(
            render_time_status(
                context.duration_minutes,
                context.time_remaining_minutes,
            )
        )

    if context.metadata.rounds:
        sections.append(_prior_rounds_block(context.metadata))

    if context.previous_round_reports:
        sections.append(
            _prior_reports_block(
                context.round_number - 1,
                context.previous_round_reports,
            )
        )

    if context.user_activity:
        sections.append(_user_activity_block(context.user_activity))

    return SystemPromptPreset(
        type="preset",
        preset="claude_code",
        append="\n\n".join(sections),
    )


# ── Placeholder substitution ─────────────────────────────────────────


def _apply_placeholders(template: str, context: RoundContext) -> str:
    """Replace `{ROUND_NUMBER}` in the template with the current round."""
    return template.replace("{ROUND_NUMBER}", str(context.round_number))


# ── Dynamic context blocks ───────────────────────────────────────────


def _prior_rounds_block(metadata: RoundsMetadata) -> str:
    """Summarize what previous rounds accomplished."""
    lines = ["## Previous rounds"]
    for entry in metadata.rounds:
        lines.append(f"- Round {entry.n}: {entry.summary}")
    return "\n".join(lines)


def _prior_reports_block(prior_round: int, files: list[str]) -> str:
    """Index of files produced in the immediately previous round."""
    lines = [
        f"## Prior round reports (round {prior_round})",
        "Read these on demand — do not dump them into subagent prompts wholesale.",
    ]
    for name in files:
        lines.append(f"- /tmp/round-{prior_round}/{name}")
    return "\n".join(lines)


def _user_activity_block(activity: list[UserAction]) -> str:
    """Chronological timeline of user actions across the entire run."""
    lines = ["## User activity (chronological)"]
    for action in activity:
        timestamp = action.timestamp[:19].replace("T", " ")
        if action.kind == "task":
            lines.append(f'- [{timestamp}] Task started: "{action.text}"')
        elif action.kind == "message":
            lines.append(f'- [{timestamp}] User message: "{action.text}"')
        else:
            lines.append(f"- [{timestamp}] {action.text}")
    lines.append(
        "The latest user message takes priority over previous plans.",
    )
    return "\n".join(lines)
