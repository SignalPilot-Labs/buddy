"""Subagent definitions — data-driven registry of all agent subagents.

Each subagent has a name, phase, description, model, tools, and prompt path.
Bootstrap reads this registry and builds the SDK agent definitions.
"""

from dataclasses import dataclass

from utils.constants import MODEL_OPUS, MODEL_SONNET
from utils.prompts import PromptLoader

# ── Tool sets (shared across subagents with same capabilities) ──

TOOLS_READ_ONLY = ["Read", "Glob", "Grep", "Bash"]
TOOLS_RESEARCH = ["Read", "Write", "Glob", "Grep", "Bash", "WebSearch", "WebFetch"]
TOOLS_BUILD = ["Read", "Write", "Edit", "Bash", "Glob", "Grep"]
TOOLS_REVIEW = ["Read", "Write", "Glob", "Grep", "Bash"]
TOOLS_REVIEW_FULL = ["Read", "Write", "Glob", "Grep", "Bash", "WebSearch", "WebFetch"]


@dataclass(frozen=True)
class SubagentDef:
    """Definition of a single subagent."""

    name: str
    phase: str
    description: str
    model: str
    tools: list[str]


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


def build_subagent_dicts(prompts: PromptLoader) -> dict[str, dict]:
    """Build subagent definitions as plain dicts for the sandbox SDK session."""
    return {
        defn.name: {
            "description": defn.description,
            "prompt": prompts.load_subagent_prompt(f"{defn.phase}/{defn.name}"),
            "model": defn.model,
            "tools": defn.tools,
        }
        for defn in SUBAGENT_DEFS
    }
