"""Orchestrator prompt builder — per-round system prompt assembly.

Each round gets a fresh Claude SDK session. `build_round_system_prompt`
loads the static `system.md` template, substitutes `{ROUND_NUMBER}`, and
appends dynamic context blocks (time status when time-locked, prior
rounds summary, prior-round file index, user messages).
"""

from claude_agent_sdk.types import SystemPromptPreset

from prompts.loader import load_markdown, render_time_status
from utils.models import RoundContext, RoundsMetadata


def build_round_system_prompt(ctx: RoundContext) -> SystemPromptPreset:
    """Build the system prompt for a single round's orchestrator session."""
    template = load_markdown("system")
    body = _apply_placeholders(template, ctx)

    sections: list[str] = [body]

    if ctx.duration_minutes > 0:
        sections.append(
            render_time_status(
                ctx.duration_minutes,
                ctx.time_remaining_minutes,
            )
        )

    if ctx.metadata.rounds:
        sections.append(_prior_rounds_block(ctx.metadata))

    if ctx.previous_round_reports:
        sections.append(
            _prior_reports_block(
                ctx.round_number - 1,
                ctx.previous_round_reports,
            )
        )

    if ctx.user_messages:
        sections.append(_user_messages_block(ctx.user_messages))

    return SystemPromptPreset(
        type="preset",
        preset="claude_code",
        append="\n\n".join(sections),
    )


# ── Placeholder substitution ─────────────────────────────────────────


def _apply_placeholders(template: str, ctx: RoundContext) -> str:
    """Replace `{ROUND_NUMBER}` in the template with the current round."""
    return template.replace("{ROUND_NUMBER}", str(ctx.round_number))


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


def _user_messages_block(messages: list[str]) -> str:
    """Inline messages the user sent since the previous round."""
    lines = ["## User messages (newest last)"]
    for msg in messages:
        lines.append(f"- {msg}")
    lines.append(
        "The latest user message takes priority over previous plans.",
    )
    return "\n".join(lines)
