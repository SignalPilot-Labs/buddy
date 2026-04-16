"""Exact-set pin test for SECRET_ENV_KEYS.

Catches both additions and removals to the source. If SECRET_ENV_VARS
in config/config.yml changes, this test fails and forces an intentional
review of the secret key set.
"""

from constants import SECRET_ENV_KEYS


class TestSecretEnvKeysPin:
    """SECRET_ENV_KEYS must match the exact expected set."""

    def test_exact_set(self) -> None:
        assert SECRET_ENV_KEYS == frozenset({
            "GIT_TOKEN",
            "GH_TOKEN",
            "CLAUDE_CODE_OAUTH_TOKEN",
            "AGENT_INTERNAL_SECRET",
            "SANDBOX_INTERNAL_SECRET",
            "ANTHROPIC_API_KEY",
            "FGAT_GIT_TOKEN",
        })
