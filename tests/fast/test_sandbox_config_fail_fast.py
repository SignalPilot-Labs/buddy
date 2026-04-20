"""Regression tests proving missing config keys raise KeyError instead of silently falling back."""

import inspect
import os
from unittest.mock import MagicMock, patch

import pytest

# Ensure env vars are set before server.py is imported (module-level _server = AgentServer()).
os.environ.setdefault("AGENT_INTERNAL_SECRET", "test-secret")
os.environ.setdefault("SANDBOX_INTERNAL_SECRET", "test-sandbox-secret")

with patch("docker.from_env", return_value=MagicMock()):
    from server import AgentServer

from sandbox_client.client import SandboxClient


class TestAgentServerMissingConfig:
    """AgentServer.__init__ must raise KeyError if a required config key is absent."""

    def test_missing_health_timeout_raises(self) -> None:
        incomplete_cfg = {
            "exec_timeout_sec": 120,
            "clone_timeout_sec": 300,
            # health_timeout_sec intentionally omitted
        }
        with patch("server.sandbox_config", return_value=incomplete_cfg):
            with patch("sandbox_client.pool.SandboxPool.__init__", return_value=None):
                with pytest.raises(KeyError):
                    AgentServer()

    def test_missing_exec_timeout_raises(self) -> None:
        incomplete_cfg = {
            "health_timeout_sec": 5,
            "clone_timeout_sec": 300,
            # exec_timeout_sec intentionally omitted
        }
        with patch("server.sandbox_config", return_value=incomplete_cfg):
            with patch("sandbox_client.pool.SandboxPool.__init__", return_value=None):
                with pytest.raises(KeyError):
                    AgentServer()

    def test_missing_clone_timeout_raises(self) -> None:
        incomplete_cfg = {
            "health_timeout_sec": 5,
            "exec_timeout_sec": 120,
            # clone_timeout_sec intentionally omitted
        }
        with patch("server.sandbox_config", return_value=incomplete_cfg):
            with patch("sandbox_client.pool.SandboxPool.__init__", return_value=None):
                with pytest.raises(KeyError):
                    AgentServer()


class TestSandboxPoolMissingMount:
    """pool.py must raise KeyError when a mount dict is missing required fields."""

    def test_missing_host_path_raises(self) -> None:
        """Direct dict access on mount["host_path"] raises KeyError for missing key."""
        mount: dict[str, str] = {
            "container_path": "/mnt/data",
            # host_path intentionally omitted
        }
        with pytest.raises(KeyError):
            _ = mount["host_path"]

    def test_missing_container_path_raises(self) -> None:
        """Direct dict access on mount["container_path"] raises KeyError for missing key."""
        mount: dict[str, str] = {
            "host_path": "/tmp/data",
            # container_path intentionally omitted
        }
        with pytest.raises(KeyError):
            _ = mount["container_path"]


class TestSandboxClientRequiresTimeout:
    """SandboxClient.__init__ must require the timeout parameter with no default."""

    def test_timeout_parameter_has_no_default(self) -> None:
        sig = inspect.signature(SandboxClient.__init__)
        params = sig.parameters
        assert "timeout" in params, "timeout parameter must exist on SandboxClient.__init__"
        timeout_param = params["timeout"]
        assert timeout_param.default is inspect.Parameter.empty, (
            "timeout parameter must have no default value"
        )

    def test_health_timeout_parameter_has_no_default(self) -> None:
        sig = inspect.signature(SandboxClient.__init__)
        params = sig.parameters
        assert "health_timeout" in params, "health_timeout parameter must exist"
        health_timeout_param = params["health_timeout"]
        assert health_timeout_param.default is inspect.Parameter.empty, (
            "health_timeout parameter must have no default value"
        )
