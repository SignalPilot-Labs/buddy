"""Verify SandboxInstance dataclass."""

from sandbox_client.models import SandboxInstance


class TestSandboxInstance:
    """SandboxInstance is frozen and holds expected fields."""

    def test_local_handle(self) -> None:
        handle = SandboxInstance(
            run_key="test-123",
            url="http://sandbox:8080",
            sandbox_secret="secret123",
            sandbox_id=None,
        )
        assert handle.run_key == "test-123"
        assert handle.sandbox_id is None

    def test_remote_handle(self) -> None:
        handle = SandboxInstance(
            run_key="test-456",
            url="http://connector:9400/sandboxes/test-456",
            sandbox_secret="secret456",
            sandbox_id="uuid-abc",
        )
        assert handle.sandbox_id == "uuid-abc"

    def test_handle_is_frozen(self) -> None:
        handle = SandboxInstance(
            run_key="test",
            url="http://x",
            sandbox_secret="s",
            sandbox_id=None,
        )
        try:
            handle.run_key = "changed"  # type: ignore[misc]
            assert False, "Should raise FrozenInstanceError"
        except AttributeError:
            pass
