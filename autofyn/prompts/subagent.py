"""Subagent registry — names, phases, models, tools, and prompt loading.

Each subagent is a `SubagentDef` describing its phase and capabilities.
`build_agent_defs()` loads the markdown system prompts and returns the
plain dict the sandbox session endpoint expects under `options.agents`.

The orchestrator calls these subagents by name via the SDK's Agent tool.
SubagentDef itself is defined in `utils.models`.
"""

from prompts.loader import load_markdown
from utils.constants import MODEL_OPUS, MODEL_SONNET
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
# Builders, debugger, code-explorer, and security-reviewer work off the
# CURRENT round only. The architect plans the next step off prior rounds,
# and code/ui reviewers benefit from catching repeated issues.
AGENTS_WITH_PRIOR_CONTEXT: tuple[str, ...] = (
    "plan/architect",
    "review/code-reviewer",
    "review/ui-reviewer",
)


SUBAGENT_DEFS: tuple[SubagentDef, ...] = (
    # ── Explore phase ──
    SubagentDef(
        name="code-explorer",
        phase="explore",
        description=(
            "Map codebase structure, find implementations, trace dependencies."
            " Call when you need to understand how code is organized or where"
            " something lives. Read-only — writes findings to"
            " /tmp/explore/round-N-code-explorer.md."
        ),
        model=MODEL_SONNET,
        tools=TOOLS_RESEARCH,
    ),
    SubagentDef(
        name="debugger",
        phase="explore",
        description=(
            "Diagnose bugs and failures. Find root causes, read logs, reproduce"
            " issues. Call when something is broken and you need to find why."
            " Writes findings to /tmp/explore/round-N-debugger.md."
        ),
        model=MODEL_SONNET,
        tools=TOOLS_REVIEW,
    ),
    # ── Plan phase ──
    SubagentDef(
        name="architect",
        phase="plan",
        description=(
            "Design the next unit of work. Analyze current state, make structural"
            " decisions, write spec to /tmp/plan/round-N-architect.md."
            " Call to plan before building."
        ),
        model=MODEL_OPUS,
        tools=TOOLS_RESEARCH,
    ),
    # ── Build phase ──
    SubagentDef(
        name="backend-dev",
        phase="build",
        description=(
            "Implement Python, APIs, database, infrastructure code. Reads spec"
            " from /tmp/plan/round-N-architect.md, writes build report to"
            " /tmp/build/round-N-backend-dev.md."
            " Never use for React/Next.js/CSS/UI work."
        ),
        model=MODEL_SONNET,
        tools=TOOLS_BUILD,
    ),
    SubagentDef(
        name="frontend-dev",
        phase="build",
        description=(
            "Implement React, Next.js, TypeScript UI, CSS, styling. Reads spec"
            " from /tmp/plan/round-N-architect.md, writes build report to"
            " /tmp/build/round-N-frontend-dev.md."
            " Never use for Python/backend work."
        ),
        model=MODEL_SONNET,
        tools=TOOLS_BUILD,
    ),
    # ── Review phase ──
    SubagentDef(
        name="code-reviewer",
        phase="review",
        description=(
            "Review code for correctness, security, and quality. Runs tests,"
            " typechecker, linter. Writes verdict to"
            " /tmp/review/round-N-code-reviewer.md. Call after every build."
        ),
        model=MODEL_SONNET,
        tools=TOOLS_REVIEW_FULL,
    ),
    SubagentDef(
        name="ui-reviewer",
        phase="review",
        description=(
            "Review frontend for visual consistency, spacing, hierarchy,"
            " accessibility, and AI slop. Writes to"
            " /tmp/review/round-N-ui-reviewer.md."
            " Call alongside code-reviewer when frontend-dev made changes."
        ),
        model=MODEL_SONNET,
        tools=TOOLS_REVIEW,
    ),
    SubagentDef(
        name="security-reviewer",
        phase="review",
        description=(
            "Audit code for security vulnerabilities: injection, auth gaps,"
            " leaked secrets, unsafe config. Writes to"
            " /tmp/review/round-N-security-reviewer.md."
            " Call when changes touch auth, user input, APIs, or secrets."
        ),
        model=MODEL_SONNET,
        tools=TOOLS_REVIEW,
    ),
)


def build_agent_defs(round_number: int) -> dict[str, dict]:
    """Build subagent definitions for a single round.

    `{ROUND_NUMBER}` and `{PRIOR_ROUND_NUMBER}` placeholders in subagent
    markdown are substituted with the live values so each round's session
    sees concrete file paths. The prior-round-context query is appended
    (only for rounds > 1) to agents listed in `AGENTS_WITH_PRIOR_CONTEXT`.
    """
    prior_round_number = max(round_number - 1, 0)
    git_rules = load_markdown("query/git-rules")
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
        prompt_parts = [agent_body, git_rules]
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
    return (
        text
        .replace("{ROUND_NUMBER}", str(round_number))
        .replace("{PRIOR_ROUND_NUMBER}", str(prior_round_number))
    )
