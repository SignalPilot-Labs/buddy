"""Tests for docker-compose.yml security configuration.

Verifies that internal secrets use the :? required-variable form with no
hardcoded dev-secret fallbacks, and that the compose topology enforces
the two-secret split (dashboard↔agent vs agent↔sandbox).
"""

from pathlib import Path

import yaml


_COMPOSE_PATH = Path(__file__).parents[2] / "docker-compose.yml"
_AGENT_REQUIRED_MARKER = "${AGENT_INTERNAL_SECRET:?"
_SANDBOX_REQUIRED_MARKER = "${SANDBOX_INTERNAL_SECRET:?"
_FORBIDDEN_DEFAULTS = (":-autofyn-dev-secret", ":-autofyn-sandbox-dev-secret")


def _load_compose() -> dict:
    return yaml.safe_load(_COMPOSE_PATH.read_text())


def _compose_text() -> str:
    return _COMPOSE_PATH.read_text()


class TestComposeSecretRequired:
    """docker-compose.yml must not fall back to hardcoded dev secrets."""

    def test_no_hardcoded_dev_secret_fallback(self) -> None:
        text = _compose_text()
        for forbidden in _FORBIDDEN_DEFAULTS:
            assert forbidden not in text

    def test_secret_env_vars_use_required_form(self) -> None:
        compose = _load_compose()
        for service_name, service in compose.get("services", {}).items():
            env = service.get("environment", {}) or {}
            for key in ("AGENT_INTERNAL_SECRET", "SANDBOX_INTERNAL_SECRET"):
                if key in env:
                    value = str(env[key])
                    assert "${" + key + ":?" in value, (
                        f"Service '{service_name}' {key} does not use "
                        f"required-variable syntax: {value!r}"
                    )


class TestComposeSecretSplit:
    """The two secrets must be compartmentalized across services."""

    def test_dashboard_holds_only_agent_secret(self) -> None:
        svc = _load_compose()["services"]["dashboard"]
        env = svc.get("environment", {}) or {}
        assert "AGENT_INTERNAL_SECRET" in env, (
            "dashboard must hold AGENT_INTERNAL_SECRET to authenticate to the agent"
        )
        assert "SANDBOX_INTERNAL_SECRET" not in env, (
            "dashboard must NOT hold SANDBOX_INTERNAL_SECRET — compartmentalization"
        )

    def test_agent_holds_both_secrets(self) -> None:
        svc = _load_compose()["services"]["agent"]
        env = svc.get("environment", {}) or {}
        assert "AGENT_INTERNAL_SECRET" in env, (
            "agent must hold AGENT_INTERNAL_SECRET to verify incoming dashboard calls"
        )
        assert "SANDBOX_INTERNAL_SECRET" in env, (
            "agent must hold SANDBOX_INTERNAL_SECRET to verify /events/* and call sandboxes"
        )

    def test_sandbox_holds_only_sandbox_secret(self) -> None:
        svc = _load_compose()["services"]["sandbox"]
        env = svc.get("environment", {}) or {}
        assert "SANDBOX_INTERNAL_SECRET" in env, (
            "sandbox must hold SANDBOX_INTERNAL_SECRET to verify incoming agent calls"
        )
        assert "AGENT_INTERNAL_SECRET" not in env, (
            "sandbox must NOT hold AGENT_INTERNAL_SECRET — else a compromised "
            "sandbox could forge control-plane calls to /start"
        )
