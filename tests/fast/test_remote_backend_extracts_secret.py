"""Regression test: RemoteBackend.create() extracts secret from AF_READY event.

Verifies that RemoteBackend uses the secret transmitted in the AF_READY marker
event from the connector. This is the end-to-end flow that eliminates
command-line secret exposure.
"""

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from sandbox_client.backends.remote_backend import RemoteBackend
from sandbox_client.models import SandboxStartError


def _make_backend() -> RemoteBackend:
    """Build a RemoteBackend with dummy connection details."""
    return RemoteBackend(
        connector_url="http://localhost:9999",
        connector_secret="connector-secret",
        sandbox_id="sandbox-uuid-001",
        ssh_target="user@hpc",
        sandbox_type="slurm",
        heartbeat_timeout=60,
    )


def _make_event_generator(
    *items: dict[str, Any],
) -> AsyncGenerator[dict[str, Any], None]:
    """Return an async generator yielding the given event dicts."""

    async def _gen() -> AsyncGenerator[dict[str, Any], None]:
        for item in items:
            yield item

    return _gen()


class TestRemoteBackendExtractsSecret:
    """RemoteBackend.create() extracts sandbox_secret from the ready event."""

    @pytest.mark.asyncio
    async def test_secret_extracted_from_ready_event(self) -> None:
        """SandboxInstance.sandbox_secret comes from AF_READY event."""
        backend = _make_backend()
        marker_secret = "deadbeef" * 8  # 64-char hex

        def fake_start(
            run_key: str,
            start_cmd: str,
            host_mounts: list[dict[str, str]] | None,
        ) -> AsyncGenerator[dict[str, Any], None]:
            return _make_event_generator(
                {"event": "ready", "host": "compute-3", "port": 8080, "sandbox_secret": marker_secret},
            )

        with patch.object(backend, "_start_remote_sandbox", side_effect=fake_start):
            with patch("sandbox_client.backends.remote_backend.log_audit", new_callable=AsyncMock):
                handle, events = await backend.create(
                    run_key="run-123",
                    health_timeout=30,
                    host_mounts=None,
                    start_cmd="start.sh",
                )

        assert handle.sandbox_secret == marker_secret

    @pytest.mark.asyncio
    async def test_raises_when_ready_event_has_no_secret(self) -> None:
        """SandboxStartError raised if AF_READY does not carry a secret."""
        backend = _make_backend()

        def fake_start(
            run_key: str,
            start_cmd: str,
            host_mounts: list[dict[str, str]] | None,
        ) -> AsyncGenerator[dict[str, Any], None]:
            return _make_event_generator(
                {"event": "ready", "host": "compute-3", "port": 8080},
            )

        with patch.object(backend, "_start_remote_sandbox", side_effect=fake_start):
            with patch("sandbox_client.backends.remote_backend.log_audit", new_callable=AsyncMock):
                with pytest.raises(SandboxStartError, match="did not provide secret"):
                    await backend.create(
                        run_key="run-456",
                        health_timeout=30,
                        host_mounts=None,
                        start_cmd="start.sh",
                    )

    @pytest.mark.asyncio
    async def test_raises_when_ready_event_secret_is_empty_string(self) -> None:
        """SandboxStartError raised if AF_READY secret is empty string."""
        backend = _make_backend()

        def fake_start(
            run_key: str,
            start_cmd: str,
            host_mounts: list[dict[str, str]] | None,
        ) -> AsyncGenerator[dict[str, Any], None]:
            return _make_event_generator(
                {"event": "ready", "host": "compute-3", "port": 8080, "sandbox_secret": ""},
            )

        with patch.object(backend, "_start_remote_sandbox", side_effect=fake_start):
            with patch("sandbox_client.backends.remote_backend.log_audit", new_callable=AsyncMock):
                with pytest.raises(SandboxStartError, match="did not provide secret"):
                    await backend.create(
                        run_key="run-789",
                        health_timeout=30,
                        host_mounts=None,
                        start_cmd="start.sh",
                    )

    @pytest.mark.asyncio
    async def test_backend_id_from_queued_event_preserved(self) -> None:
        """backend_id from queued event is included in returned events list."""
        backend = _make_backend()
        marker_secret = "cafebabe" * 8

        def fake_start(
            run_key: str,
            start_cmd: str,
            host_mounts: list[dict[str, str]] | None,
        ) -> AsyncGenerator[dict[str, Any], None]:
            return _make_event_generator(
                {"event": "queued", "backend_id": "slurm-job-42"},
                {"event": "ready", "host": "compute-5", "port": 8080, "sandbox_secret": marker_secret},
            )

        with patch.object(backend, "_start_remote_sandbox", side_effect=fake_start):
            with patch("sandbox_client.backends.remote_backend.log_audit", new_callable=AsyncMock):
                handle, events = await backend.create(
                    run_key="run-999",
                    health_timeout=30,
                    host_mounts=None,
                    start_cmd="start.sh",
                )

        assert handle.sandbox_secret == marker_secret
        assert len(events) == 2
        assert events[0]["event"] == "queued"
