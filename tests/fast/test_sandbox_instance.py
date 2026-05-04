"""Verify SandboxInstance dataclass."""

from sandbox_client.instance import SandboxInstance


class TestSandboxInstance:
    """SandboxInstance is frozen and holds expected fields."""

    def test_local_handle(self) -> None:
        handle = SandboxInstance(
            run_key="test-123",
            url="http://sandbox:8080",
            backend_id="container-abc",
            sandbox_secret="secret123",
            sandbox_id=None,
            sandbox_type=None,
            remote_host=None,
            remote_port=None,
        )
        assert handle.run_key == "test-123"
        assert handle.sandbox_id is None
        assert handle.sandbox_type is None

    def test_remote_handle(self) -> None:
        handle = SandboxInstance(
            run_key="test-456",
            url="http://connector:9400/sandboxes/test-456",
            backend_id="12345",
            sandbox_secret="secret456",
            sandbox_id="uuid-abc",
            sandbox_type="slurm",
            remote_host="compute-7",
            remote_port=9123,
        )
        assert handle.sandbox_type == "slurm"
        assert handle.remote_host == "compute-7"
        assert handle.remote_port == 9123

    def test_handle_is_frozen(self) -> None:
        handle = SandboxInstance(
            run_key="test",
            url="http://x",
            backend_id=None,
            sandbox_secret="s",
            sandbox_id=None,
            sandbox_type=None,
            remote_host=None,
            remote_port=None,
        )
        try:
            handle.run_key = "changed"  # type: ignore[misc]
            assert False, "Should raise FrozenInstanceError"
        except AttributeError:
            pass
