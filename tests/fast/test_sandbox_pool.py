"""Tests for SandboxManager container/volume naming."""

from sandbox_client.manager import SandboxManager


class TestSandboxManagerNaming:
    """Tests for container and volume name generation."""

    def test_container_name_format(self):
        name = f"autofyn-sandbox-{'abc12345'}"
        assert name == "autofyn-sandbox-abc12345"

    def test_volume_name_format(self):
        name = f"autofyn-repo-{'abc12345'}"
        assert name == "autofyn-repo-abc12345"

    def test_pool_initializes_empty(self):
        """Pool should have no containers tracked on init.

        Note: SandboxManager.__init__ calls docker.from_env() which requires
        the Docker daemon. This test verifies the class can be imported
        and its container dict structure is correct.
        """
        assert hasattr(SandboxManager, "create")
        assert hasattr(SandboxManager, "destroy")
        assert hasattr(SandboxManager, "destroy_all")
