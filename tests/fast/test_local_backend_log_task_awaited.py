"""Regression test: DockerLocalBackend._destroy_by_key awaits cancelled log drainer task."""

import asyncio
import os
import warnings
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from utils.constants import ENV_KEY_IMAGE_TAG
from sandbox_client.backends.local_backend import DockerLocalBackend


def _make_backend() -> DockerLocalBackend:
    """Instantiate DockerLocalBackend with mocked Docker client and sandbox_config."""
    env: dict[str, str] = {ENV_KEY_IMAGE_TAG: "test"}
    with (
        patch("sandbox_client.backends.local_backend.docker.from_env", return_value=MagicMock()),
        patch(
            "sandbox_client.backends.local_backend.sandbox_config",
            return_value={"vm_timeout_sec": 30, "health_timeout_sec": 5},
        ),
        patch.dict(os.environ, env, clear=False),
    ):
        return DockerLocalBackend()


class TestLocalBackendLogTaskAwaited:
    """Verify that _destroy_by_key awaits the cancelled log drainer task to prevent ResourceWarning."""

    @pytest.mark.asyncio
    async def test_log_task_is_done_after_destroy(self) -> None:
        """Log drainer task must be done (not pending) after _destroy_by_key completes."""
        backend = _make_backend()

        async def _long_running() -> None:
            await asyncio.sleep(10)

        task: asyncio.Task[None] = asyncio.create_task(_long_running())
        backend._log_tasks["test-run"] = task
        backend._containers["test-run"] = "fake-container-id"

        with (
            patch.object(backend, "_remove_container", new=AsyncMock()),
            patch.object(backend, "_remove_volume", new=AsyncMock()),
        ):
            await backend._destroy_by_key("test-run")

        assert task.done(), "Log drainer task must be done after destroy"

    @pytest.mark.asyncio
    async def test_no_resource_warning_after_destroy(self) -> None:
        """No ResourceWarning must be emitted when destroy properly awaits the task."""
        backend = _make_backend()

        async def _long_running() -> None:
            await asyncio.sleep(10)

        task: asyncio.Task[None] = asyncio.create_task(_long_running())
        backend._log_tasks["test-run"] = task
        backend._containers["test-run"] = "fake-container-id"

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            with (
                patch.object(backend, "_remove_container", new=AsyncMock()),
                patch.object(backend, "_remove_volume", new=AsyncMock()),
            ):
                await backend._destroy_by_key("test-run")

        resource_warnings = [w for w in caught if issubclass(w.category, ResourceWarning)]
        assert resource_warnings == [], f"Unexpected ResourceWarning: {resource_warnings}"
