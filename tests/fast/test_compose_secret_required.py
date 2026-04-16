"""Tests for docker-compose.yml security configuration.

Verifies that AGENT_INTERNAL_SECRET uses the :? required-variable form,
that no hardcoded dev-secret fallback is present, and that the dashboard
ports are bound to loopback only.
"""

from pathlib import Path

import yaml


_COMPOSE_PATH = Path(__file__).parents[2] / "docker-compose.yml"
_REQUIRED_SECRET_MARKER = "${AGENT_INTERNAL_SECRET:?"
_FORBIDDEN_DEFAULT = ":-autofyn-dev-secret"
_EXPECTED_ERROR_MSG = "AGENT_INTERNAL_SECRET must be set — run up.sh or define it in .env"


def _load_compose() -> dict:
    return yaml.safe_load(_COMPOSE_PATH.read_text())


def _compose_text() -> str:
    return _COMPOSE_PATH.read_text()


class TestComposeSecretRequired:
    """docker-compose.yml must not fall back to a hardcoded dev secret."""

    def test_no_hardcoded_dev_secret_fallback(self) -> None:
        assert _FORBIDDEN_DEFAULT not in _compose_text()

    def test_all_services_use_required_form(self) -> None:
        compose = _load_compose()
        services = compose.get("services", {})
        for service_name, service in services.items():
            env = service.get("environment", {})
            if "AGENT_INTERNAL_SECRET" in env:
                value = str(env["AGENT_INTERNAL_SECRET"])
                assert _REQUIRED_SECRET_MARKER in value, (
                    f"Service '{service_name}' AGENT_INTERNAL_SECRET does not use "
                    f"required-variable syntax: {value!r}"
                )

    def test_all_substitutions_share_same_error_message(self) -> None:
        """All three :? substitutions must use the exact same error message."""
        text = _compose_text()
        count = text.count(_EXPECTED_ERROR_MSG)
        # There are three services that set AGENT_INTERNAL_SECRET
        assert count == 3, (
            f"Expected 3 occurrences of the error message, found {count}"
        )

    def test_dashboard_port_3400_bound_to_loopback(self) -> None:
        compose = _load_compose()
        ports = compose["services"]["dashboard"]["ports"]
        assert "127.0.0.1:3400:3400" in ports

    def test_dashboard_port_3401_bound_to_loopback(self) -> None:
        compose = _load_compose()
        ports = compose["services"]["dashboard"]["ports"]
        assert "127.0.0.1:3401:3401" in ports
