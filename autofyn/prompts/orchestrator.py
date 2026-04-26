"""Orchestrator prompt builder — per-round system prompt assembly.

Each round gets a fresh Claude SDK session. `build_round_system_prompt`
loads the static `system.md` template, substitutes `{ROUND_NUMBER}`, and
appends dynamic context blocks (time status when time-locked, prior
rounds summary, prior-round file index, user messages).
"""

from claude_agent_sdk.types import SystemPromptPreset

from prompts.loader import load_markdown, render_environment, render_time_status
from utils.models import RoundContext, UserAction


def build_round_system_prompt(
    context: RoundContext,
    tool_call_timeout_sec: int,
) -> SystemPromptPreset:
    """Build the system prompt for a single round's orchestrator session."""
    template = load_markdown("system")
    body = _apply_placeholders(template, context)

    env_block = render_environment(
        round_number=context.round_number,
        tool_call_timeout_min=tool_call_timeout_sec // 60,
        host_mounts=context.host_mounts,
        user_env_keys=context.user_env_keys,
        base_branch=context.base_branch,
    )
    sections: list[str] = [body, env_block, load_markdown("query/git-rules")]

    if context.duration_minutes > 0:
        sections.append(
            render_time_status(
                context.duration_minutes,
                context.time_remaining_minutes,
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
        "Priority: The user's latest message takes highest priority.",
    )
    return "\n".join(lines)


def build_initial_prompt(round_number: int, task: str, is_grace_round: bool) -> str:
    """Short per-round kickoff message paired with the round system prompt."""
    prompt = f"Round {round_number} is starting.\n\nTask:\n{task.strip()}"
    if is_grace_round:
        prompt += "\n\nTime lock has expired. This is your final round. Wrap up, ship it, call end_session."
    return prompt
