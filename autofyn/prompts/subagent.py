"""Subagent registry — names, phases, models, tools, and prompt loading.

Each subagent is a `SubagentDef` describing its phase and capabilities.
`build_agent_defs()` loads the markdown system prompts and returns the
plain dict the sandbox session endpoint expects under `options.agents`.

The orchestrator calls these subagents by name via the SDK's Agent tool.
SubagentDef itself is defined in `utils.models`.
"""

from prompts.loader import load_markdown, render_environment
from db.constants import SUPPORTED_SONNET
from utils.constants import TIER_OPUS, TIER_SONNET
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

# All subagents except code-explorer get run_state.md context for round > 1.
# Explorer gets its context from the orchestrator's dispatch prompt — it
# doesn't need cross-round state.
AGENTS_WITHOUT_RUN_STATE: tuple[str, ...] = ("explore/code-explorer",)


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
        model=TIER_SONNET,
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
        model=TIER_OPUS,
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
        model=TIER_OPUS,
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
        model=TIER_SONNET,
        tools=TOOLS_BUILD,
    ),
    SubagentDef(
        name="frontend-dev",
        phase="build",
        description=(
            "Implements React, Next.js, TypeScript UI, CSS, and styling from"
            " the architect's spec. Never use for Python/backend work."
        ),
        model=TIER_SONNET,
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
        model=TIER_OPUS,
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
        model=TIER_OPUS,
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
        model=TIER_OPUS,
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
        model=TIER_OPUS,
        tools=TOOLS_REVIEW,
    ),
)


def _resolve_subagent_model(tier: str, user_model: str) -> str:
    """Resolve a subagent tier to a concrete model ID based on user selection.

    - User picks an opus model → opus-tier subagents get that model,
      sonnet-tier subagents get SUPPORTED_SONNET.
    - User picks a sonnet model → ALL subagents (including opus-tier) get
      that sonnet model. Sonnet runs are cost-conscious — no opus anywhere.
    """
    is_sonnet_run = "sonnet" in user_model
    if is_sonnet_run:
        return user_model
    if tier == TIER_OPUS:
        return user_model
    return SUPPORTED_SONNET


def build_agent_defs(
    round_number: int,
    host_mounts: list[dict[str, str]] | None,
    user_env_keys: list[str],
    user_model: str,
    tool_call_timeout_sec: int,
    base_branch: str,
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
    env_block = render_environment(
        round_number=round_number,
        tool_call_timeout_min=tool_call_timeout_sec // 60,
        host_mounts=host_mounts,
        user_env_keys=user_env_keys,
        base_branch=base_branch,
    )
    git_rules = load_markdown("query/git-rules")
    dispatch_rules = load_markdown("query/dispatch-rules")
    verification_rules = load_markdown("query/verification-rules")
    run_state_context = (
        load_markdown("query/prior-round-context")
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
            base_branch,
        )
        prompt_parts = [agent_body, env_block, git_rules, dispatch_rules]
        if path in AGENTS_WITH_VERIFICATION:
            prompt_parts.append(verification_rules)
        if run_state_context and path not in AGENTS_WITHOUT_RUN_STATE:
            prompt_parts.append(run_state_context)
        result[defn.name] = {
            "description": defn.description,
            "prompt": "\n\n".join(prompt_parts),
            "model": _resolve_subagent_model(defn.model, user_model),
            "tools": defn.tools,
        }
    return result


def _substitute(text: str, round_number: int, prior_round_number: int, base_branch: str) -> str:
    """Replace placeholders in a subagent prompt."""
    return (
        text
        .replace("{ROUND_NUMBER}", str(round_number))
        .replace("{PRIOR_ROUND_NUMBER}", str(prior_round_number))
        .replace("{BASE_BRANCH}", base_branch)
    )
