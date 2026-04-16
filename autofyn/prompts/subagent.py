"""Subagent registry — names, phases, models, tools, and prompt loading.

Each subagent is a `SubagentDef` describing its phase and capabilities.
`build_agent_defs()` loads the markdown system prompts and returns the
plain dict the sandbox session endpoint expects under `options.agents`.

The orchestrator calls these subagents by name via the SDK's Agent tool.
SubagentDef itself is defined in `utils.models`.
"""

from prompts.loader import load_markdown, render_environment
from utils.constants import MODEL_OPUS, MODEL_SONNET, TOOL_CALL_TIMEOUT_SEC
from utils.models import SubagentDef

# ── Tool sets (shared across subagents with matching capabilities) ──

TOOLS_READ_ONLY = ["Read", "Glob", "Grep", "Bash"]
TOOLS_RESEARCH = ["Read", "Write", "Glob", "Grep", "Bash", "WebSearch", "WebFetch"]
TOOLS_BUILD = ["Read", "Write", "Edit", "Bash", "Glob", "Grep"]
TOOLS_REVIEW = ["Read", "Write", "Glob", "Grep", "Bash"]
TOOLS_REVIEW_FULL = ["Read", "Write", "Glob", "Grep", "Bash", "WebSearch", "WebFetch"]

# Which subagents need the verification rules appended to their prompt.
AGENTS_WITH_VERIFICATION: tuple[str, ...] = (
    "build/backend-dev",
    "build/frontend-dev",
    "review/code-reviewer",
    "review/ui-reviewer",
    "review/security-reviewer",
)

# Which subagents should see prior-round reports (only when round > 1).
# Builders and code-explorer work off the CURRENT round only. Planners
# need prior context to avoid re-diagnosing or re-planning shipped work;
# reviewers benefit from calibration lessons and prior findings.
AGENTS_WITH_PRIOR_CONTEXT: tuple[str, ...] = (
    "plan/architect",
    "plan/debugger",
    "review/spec-reviewer",
    "review/code-reviewer",
    "review/ui-reviewer",
    "review/security-reviewer",
)


SUBAGENT_DEFS: tuple[SubagentDef, ...] = (
    # ── Explore phase ──
    SubagentDef(
        name="code-explorer",
        phase="explore",
        description=(
            "Maps codebase structure, traces dependencies, finds implementations."
            " Call when you need to understand how code is organized or where"
            " something lives. Be targeted — tell it what to look for."
        ),
        model=MODEL_SONNET,
        tools=TOOLS_RESEARCH,
    ),
    # ── Plan phase ──
    SubagentDef(
        name="debugger",
        phase="plan",
        description=(
            "Debugging planner. Reproduces the bug, traces the root cause,"
            " and writes a fix spec a dev can implement. Call when something"
            " is broken."
        ),
        model=MODEL_OPUS,
        tools=TOOLS_RESEARCH,
    ),
    SubagentDef(
        name="architect",
        phase="plan",
        description=(
            "Designs the next unit of work. Analyzes current state, makes"
            " structural decisions, writes the round's spec. Call at the start"
            " of each round, and again to re-plan on RETHINK."
        ),
        model=MODEL_OPUS,
        tools=TOOLS_RESEARCH,
    ),
    # ── Build phase ──
    SubagentDef(
        name="backend-dev",
        phase="build",
        description=(
            "Implements Python, APIs, database, and infrastructure code from"
            " the architect's spec. Never use for React/Next.js/CSS/UI work."
        ),
        model=MODEL_SONNET,
        tools=TOOLS_BUILD,
    ),
    SubagentDef(
        name="frontend-dev",
        phase="build",
        description=(
            "Implements React, Next.js, TypeScript UI, CSS, and styling from"
            " the architect's spec. Never use for Python/backend work."
        ),
        model=MODEL_SONNET,
        tools=TOOLS_BUILD,
    ),
    # ── Review phase ──
    SubagentDef(
        name="spec-reviewer",
        phase="review",
        description=(
            "Reviews architect or debugger specs BEFORE any code is written."
            " Checks design quality, file placement, coupling, simplicity,"
            " and CLAUDE.md compliance. Call on every spec marked"
            " `Spec review: required`."
        ),
        model=MODEL_OPUS,
        tools=TOOLS_REVIEW,
    ),
    SubagentDef(
        name="code-reviewer",
        phase="review",
        description=(
            "Reviews code post-build for correctness, design, spec compliance,"
            " and quality. Runs tests, linter, typechecker. Call after every"
            " build."
        ),
        model=MODEL_OPUS,
        tools=TOOLS_REVIEW_FULL,
    ),
    SubagentDef(
        name="ui-reviewer",
        phase="review",
        description=(
            "Reviews frontend for visual consistency, spacing, hierarchy,"
            " accessibility, and AI slop. Call alongside code-reviewer whenever"
            " frontend-dev made changes."
        ),
        model=MODEL_OPUS,
        tools=TOOLS_REVIEW,
    ),
    SubagentDef(
        name="security-reviewer",
        phase="review",
        description=(
            "Audits code for security vulnerabilities: injection, auth gaps,"
            " leaked secrets, unsafe config. Call when changes touch auth,"
            " user input, APIs, or secrets."
        ),
        model=MODEL_OPUS,
        tools=TOOLS_REVIEW,
    ),
)


def build_agent_defs(
    round_number: int,
    host_mounts: list[dict[str, str]] | None,
) -> dict[str, dict]:
    """Build subagent definitions for a single round.

    Placeholders (`{ROUND_NUMBER}`, `{PRIOR_ROUND_NUMBER}`) in subagent
    markdown are substituted with the live values. `query/environment` is
    prepended to every subagent. `query/prior-round-context` is appended
    for rounds > 1 to agents in `AGENTS_WITH_PRIOR_CONTEXT` so they can
    read the previous round. Subagents never receive `query/time-status`
    — only the orchestrator acts on time.
    """
    prior_round_number = max(round_number - 1, 0)
    environment = render_environment(
        round_number=round_number,
        tool_call_timeout_min=TOOL_CALL_TIMEOUT_SEC // 60,
        host_mounts=host_mounts,
    )
    git_rules = load_markdown("query/git-rules")
    dispatch_rules = load_markdown("query/dispatch-rules")
    verification_rules = load_markdown("query/verification-rules")
    prior_context = (
        _substitute(
            load_markdown("query/prior-round-context"),
            round_number,
            prior_round_number,
        )
        if round_number > 1
        else None
    )
    result: dict[str, dict] = {}
    for defn in SUBAGENT_DEFS:
        path = f"{defn.phase}/{defn.name}"
        agent_body = _substitute(
            load_markdown(f"subagents/{path}"),
            round_number,
            prior_round_number,
        )
        prompt_parts = [agent_body, environment, git_rules, dispatch_rules]
        if path in AGENTS_WITH_VERIFICATION:
            prompt_parts.append(verification_rules)
        if prior_context and path in AGENTS_WITH_PRIOR_CONTEXT:
            prompt_parts.append(prior_context)
        result[defn.name] = {
            "description": defn.description,
            "prompt": "\n\n".join(prompt_parts),
            "model": defn.model,
            "tools": defn.tools,
        }
    return result


def _substitute(text: str, round_number: int, prior_round_number: int) -> str:
    """Replace `{ROUND_NUMBER}` and `{PRIOR_ROUND_NUMBER}` in a subagent prompt."""
    return text.replace("{ROUND_NUMBER}", str(round_number)).replace(
        "{PRIOR_ROUND_NUMBER}", str(prior_round_number)
    )
