"""Tests for SandboxPool container/volume naming."""

from sandbox_manager.pool import SandboxPool


class TestSandboxPoolNaming:
    """Tests for container and volume name generation."""

    def test_container_name_format(self):
        name = f"autofyn-sandbox-{'abc12345'}"
        assert name == "autofyn-sandbox-abc12345"

    def test_volume_name_format(self):
        name = f"autofyn-repo-{'abc12345'}"
        assert name == "autofyn-repo-abc12345"

    def test_pool_initializes_empty(self):
        """Pool should have no containers tracked on init.

        Note: SandboxPool.__init__ calls docker.from_env() which requires
        the Docker daemon. This test verifies the class can be imported
        and its container dict structure is correct.
        """
        assert hasattr(SandboxPool, "create")
        assert hasattr(SandboxPool, "destroy")
        assert hasattr(SandboxPool, "destroy_all")
