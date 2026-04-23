"""Shared helper functions for endpoint route modules."""

from utils.constants import ENV_KEY_CLAUDE_TOKEN, ENV_KEY_GIT_TOKEN


def _merge_tokens_into_env(
    env: dict[str, str] | None,
    claude_token: str | None,
    git_token: str | None,
) -> dict[str, str] | None:
    """Merge per-run tokens into the env dict without touching os.environ."""
    if not claude_token and not git_token:
        return env
    merged: dict[str, str] = dict(env) if env is not None else {}
    if claude_token:
        merged[ENV_KEY_CLAUDE_TOKEN] = claude_token
    if git_token:
        merged[ENV_KEY_GIT_TOKEN] = git_token
    return merged
