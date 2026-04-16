"""F2: docker-compose.yml network topology matches the spec.

Static analysis of docker-compose.yml to verify:
- autofyn-control (internal) has dashboard + agent + db but NOT sandbox
- autofyn-sandbox has agent + sandbox but NOT dashboard
- agent is on BOTH networks
- db is on autofyn-control ONLY
- Explicit name: overrides are present
"""

from pathlib import Path

import yaml


_COMPOSE_PATH = Path(__file__).parent.parent.parent / "docker-compose.yml"


def _load_compose() -> dict:
    return yaml.safe_load(_COMPOSE_PATH.read_text())


class TestComposeNetworks:
    """docker-compose.yml must define the correct network topology."""

    def setup_method(self) -> None:
        self._compose = _load_compose()
        self._networks = self._compose.get("networks", {})
        self._services = self._compose.get("services", {})

    def _service_networks(self, service: str) -> list[str]:
        svc = self._services.get(service, {})
        nets = svc.get("networks", [])
        if isinstance(nets, dict):
            return list(nets.keys())
        return list(nets)

    def test_autofyn_control_network_defined(self) -> None:
        assert "autofyn-control" in self._networks

    def test_autofyn_sandbox_network_defined(self) -> None:
        assert "autofyn-sandbox" in self._networks

    def test_autofyn_control_has_name_override(self) -> None:
        ctrl = self._networks["autofyn-control"]
        assert ctrl.get("name") == "autofyn-control"

    def test_autofyn_sandbox_has_name_override(self) -> None:
        sand = self._networks["autofyn-sandbox"]
        assert sand.get("name") == "autofyn-sandbox"

    def test_autofyn_control_is_internal(self) -> None:
        ctrl = self._networks["autofyn-control"]
        assert ctrl.get("internal") is True

    def test_agent_on_both_networks(self) -> None:
        nets = self._service_networks("agent")
        assert "autofyn-control" in nets, "agent must be on autofyn-control"
        assert "autofyn-sandbox" in nets, "agent must be on autofyn-sandbox"

    def test_dashboard_on_control_only(self) -> None:
        nets = self._service_networks("dashboard")
        assert "autofyn-control" in nets, "dashboard must be on autofyn-control"
        assert "autofyn-sandbox" not in nets, "dashboard must NOT be on autofyn-sandbox"

    def test_db_on_control_only(self) -> None:
        nets = self._service_networks("db")
        assert "autofyn-control" in nets, "db must be on autofyn-control"
        assert "autofyn-sandbox" not in nets, "db must NOT be on autofyn-sandbox"

    def test_sandbox_not_on_control_network(self) -> None:
        nets = self._service_networks("sandbox")
        assert "autofyn-control" not in nets, "sandbox must NOT be on autofyn-control"

    def test_sandbox_on_sandbox_network(self) -> None:
        nets = self._service_networks("sandbox")
        assert "autofyn-sandbox" in nets, "sandbox must be on autofyn-sandbox"
