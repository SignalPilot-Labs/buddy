"""F2: dashboard/entrypoint.sh binds to 127.0.0.1, not 0.0.0.0."""

from pathlib import Path


_ENTRYPOINT_PATH = Path(__file__).parent.parent.parent / "dashboard" / "entrypoint.sh"


class TestDashboardEntrypointBindsLoopback:
    """entrypoint.sh must bind listeners to 127.0.0.1."""

    def setup_method(self) -> None:
        self._content = _ENTRYPOINT_PATH.read_text()

    def test_uvicorn_binds_loopback(self) -> None:
        assert "--host 127.0.0.1" in self._content

    def test_uvicorn_does_not_bind_all_interfaces(self) -> None:
        # 0.0.0.0 must not appear in any --host flag
        lines = self._content.splitlines()
        for line in lines:
            if "--host" in line:
                assert "0.0.0.0" not in line, f"Found 0.0.0.0 in: {line!r}"

    def test_nextjs_hostname_is_loopback(self) -> None:
        assert 'HOSTNAME="127.0.0.1"' in self._content

    def test_nextjs_does_not_use_all_interfaces(self) -> None:
        assert 'HOSTNAME="0.0.0.0"' not in self._content
