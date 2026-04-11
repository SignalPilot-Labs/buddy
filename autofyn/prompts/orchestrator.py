"""Orchestrator prompt builder — per-round system prompt assembly.

Each round gets a fresh Claude SDK session. `build_round_system_prompt`
loads the static `system.md` template, substitutes `{ROUND_NUMBER}` and
friends, and appends dynamic context blocks (prior rounds, prior-round
reports, operator messages). Round-1 runs also get
`query/initial_setup.md` appended, and time-locked runs get a time
remaining block appended.

Placeholders substituted in the template:

    {ROUND_NUMBER}         — current round (int)
    {PRIOR_ROUND_NUMBER}   — current round minus one
    {BRANCH_NAME}          — the working branch
    {BASE_BRANCH}          — the PR base branch
"""

from claude_agent_sdk.types import SystemPromptPreset

from prompts.loader import load_markdown
from utils.models import RoundContext, RoundsMetadata


def build_round_system_prompt(ctx: RoundContext) -> SystemPromptPreset:
    """Build the system prompt for a single round's orchestrator session."""
    template = load_markdown("system")
    body = _apply_placeholders(template, ctx)

    sections: list[str] = [body]

    if ctx.duration_minutes > 0:
        sections.append(_time_status_block(ctx))

    if ctx.metadata.rounds:
        sections.append(_prior_rounds_block(ctx.metadata))

    if ctx.previous_round_reports:
        sections.append(_prior_reports_block(
            ctx.round_number - 1, ctx.previous_round_reports,
        ))

    if ctx.operator_messages:
        sections.append(_operator_messages_block(ctx.operator_messages))

    return SystemPromptPreset(
        type="preset",
        preset="claude_code",
        append="\n\n".join(sections),
    )


# ── Placeholder substitution ─────────────────────────────────────────


def _apply_placeholders(template: str, ctx: RoundContext) -> str:
    """Replace every `{KEY}` in `template` with the matching RoundContext value."""
    replacements: dict[str, str] = {
        "{ROUND_NUMBER}": str(ctx.round_number),
        "{PRIOR_ROUND_NUMBER}": str(max(ctx.round_number - 1, 0)),
        "{BRANCH_NAME}": ctx.branch_name,
        "{BASE_BRANCH}": ctx.base_branch,
    }
    text = template
    for key, value in replacements.items():
        text = text.replace(key, value)
    return text


# ── Dynamic context blocks ───────────────────────────────────────────


def _time_status_block(ctx: RoundContext) -> str:
    """Time remaining block — only appended when the run is time-locked."""
    remaining = max(int(ctx.time_remaining_minutes), 0)
    total = int(ctx.duration_minutes)
    return (
        "## Time remaining\n"
        f"{remaining} of {total} minutes remain. `end_session` is denied while "
        "more than 5 minutes remain; a denial means keep working."
    )


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


def _operator_messages_block(messages: list[str]) -> str:
    """Inline messages the operator sent since the previous round."""
    lines = ["## Operator messages (newest last)"]
    for msg in messages:
        lines.append(f"- {msg}")
    lines.append(
        "The latest operator message takes priority over previous plans.",
    )
    return "\n".join(lines)
