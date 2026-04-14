"""Shared constants importable from both the agent and dashboard containers.

The `db` package is the only Python package imported by both `autofyn/` and
`dashboard/backend/`, so cross-container constants that must not drift live here.
"""

# Valid Claude model identifiers accepted at the run-start boundary.
# Source of truth for: agent validation, dashboard Pydantic regex, fallback map.
# "opus" and "sonnet" are Claude Code aliases resolved by the CLI to the latest
# snapshot. "opus-4-5" is our own key for the previous Opus generation and is
# translated to the full model ID "claude-opus-4-5" at the SDK boundary.
VALID_MODELS: tuple[str, ...] = ("opus", "sonnet", "opus-4-5")

# Default model used when the caller does not specify one.
DEFAULT_MODEL: str = "opus"

# Pydantic/regex-friendly alternation pattern built from VALID_MODELS.
VALID_MODELS_PATTERN: str = f"^({'|'.join(VALID_MODELS)})$"

# Translation from our internal model keys to the exact model IDs the Claude
# Agent SDK forwards to the Anthropic API. Keys not present here are passed
# through unchanged (the CLI resolves "opus"/"sonnet" aliases itself).
MODEL_ID_TRANSLATION: dict[str, str] = {
    "opus-4-5": "claude-opus-4-5",
}

# ── Effort ──
# Valid effort levels for the Claude Agent SDK.
# "max" is only supported on 4.6 models (opus, sonnet); for older models
# it is silently downgraded to "high" at the bootstrap boundary.
VALID_EFFORTS: tuple[str, ...] = ("low", "medium", "high", "max")
DEFAULT_EFFORT: str = "medium"
VALID_EFFORTS_PATTERN: str = f"^({'|'.join(VALID_EFFORTS)})$"

# Models that support effort="max". Others get downgraded to "high".
MODELS_SUPPORTING_MAX_EFFORT: frozenset[str] = frozenset({"opus", "sonnet"})


def resolve_sdk_model(model: str) -> str:
    """Translate an internal model key to the SDK model ID, or pass through."""
    return MODEL_ID_TRANSLATION.get(model, model)
