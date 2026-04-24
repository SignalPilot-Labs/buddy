"""Regression tests for starter presets.

Verifies that each preset key in STARTER_PRESET_KEYS has a loadable
markdown file, that StartRequest validates preset/prompt exclusivity,
and that the preset keys stay in sync between Python and TypeScript.
"""

import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from db.constants import STARTER_PRESET_KEYS
from prompts.loader import load_markdown
from utils.models_http import StartRequest


class TestStarterPresetFiles:
    """Each preset key must have a corresponding markdown file."""

    @pytest.mark.parametrize("key", STARTER_PRESET_KEYS)
    def test_preset_file_loadable(self, key: str) -> None:
        content = load_markdown(f"starter/{key}")
        assert len(content) > 0


class TestStartRequestPresetValidation:
    """StartRequest enforces preset/prompt mutual exclusivity."""

    def test_accepts_valid_preset(self) -> None:
        req = StartRequest(preset="security_hardening")
        assert req.preset == "security_hardening"
        assert req.prompt is None

    def test_accepts_prompt_without_preset(self) -> None:
        req = StartRequest(prompt="fix the bug")
        assert req.prompt == "fix the bug"
        assert req.preset is None

    def test_rejects_both_prompt_and_preset(self) -> None:
        with pytest.raises(ValidationError, match="Cannot set both"):
            StartRequest(prompt="fix", preset="security_hardening")

    def test_rejects_invalid_preset_key(self) -> None:
        with pytest.raises(ValidationError, match="preset must be one of"):
            StartRequest(preset="invalid_key")

    def test_accepts_neither_prompt_nor_preset(self) -> None:
        req = StartRequest()
        assert req.prompt is None
        assert req.preset is None


class TestPresetResolutionInEndpoint:
    """Preset is resolved to prompt text before the run is created."""

    @pytest.mark.asyncio
    async def test_preset_resolves_to_prompt_in_start_endpoint(self) -> None:
        """POST /start with preset resolves it to markdown content."""
        import os
        from unittest.mock import AsyncMock, MagicMock, patch

        os.environ.setdefault("AGENT_INTERNAL_SECRET", "test-secret")
        os.environ.setdefault("SANDBOX_INTERNAL_SECRET", "test-sandbox-secret")

        with patch("docker.from_env", return_value=MagicMock()):
            from server import app

        from httpx import ASGITransport, AsyncClient
        from utils.constants import INTERNAL_SECRET_HEADER

        create_run_calls: list[tuple] = []

        async def capture_create_run(*args: object) -> None:
            create_run_calls.append(args)

        with (
            patch("endpoints.run.db.create_run_starting", side_effect=capture_create_run),
            patch("endpoints.run.log_audit", AsyncMock()),
            patch("server.AgentServer.execute_run", AsyncMock()),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/start",
                    json={
                        "preset": "security_hardening",
                        "github_repo": "owner/repo",
                        "duration_minutes": 30,
                        "git_token": "ghp_test",
                    },
                    headers={INTERNAL_SECRET_HEADER: "test-secret"},
                )

        assert resp.status_code == 200
        # create_run_starting receives the resolved prompt text, not the preset key
        assert len(create_run_calls) == 1
        custom_prompt_arg = create_run_calls[0][1]
        assert custom_prompt_arg is not None
        assert "security" in custom_prompt_arg.lower()
        assert custom_prompt_arg != "security_hardening"

    @pytest.mark.asyncio
    async def test_no_prompt_or_preset_returns_422(self) -> None:
        """POST /start with neither prompt nor preset returns 422."""
        import os
        from unittest.mock import MagicMock, patch

        os.environ.setdefault("AGENT_INTERNAL_SECRET", "test-secret")
        os.environ.setdefault("SANDBOX_INTERNAL_SECRET", "test-sandbox-secret")

        with patch("docker.from_env", return_value=MagicMock()):
            from server import app

        from httpx import ASGITransport, AsyncClient
        from utils.constants import INTERNAL_SECRET_HEADER

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/start",
                json={
                    "github_repo": "owner/repo",
                    "duration_minutes": 30,
                    "git_token": "ghp_test",
                },
                headers={INTERNAL_SECRET_HEADER: "test-secret"},
            )

        assert resp.status_code == 422


class TestStarterPresetSync:
    """Python and TypeScript preset key sets must match."""

    def test_frontend_constants_contain_all_preset_keys(self) -> None:
        ts_path = Path("dashboard/frontend/lib/constants.ts")
        ts_content = ts_path.read_text(encoding="utf-8")
        python_keys = set(STARTER_PRESET_KEYS)
        ts_keys = set()
        for key in python_keys:
            if key in ts_content:
                ts_keys.add(key)
        missing = python_keys - ts_keys
        assert not missing, f"Keys missing from TS constants: {missing}"

    def test_no_extra_keys_in_frontend(self) -> None:
        ts_path = Path("dashboard/frontend/lib/constants.ts")
        ts_content = ts_path.read_text(encoding="utf-8")
        # Extract top-level keys from STARTER_PRESETS object (indented with 2 spaces)
        match = re.search(r"STARTER_PRESETS\s*=\s*\{([\s\S]*?)\}\s*as\s*const", ts_content)
        assert match, "Could not find STARTER_PRESETS in constants.ts"
        ts_keys = set(re.findall(r"^\s{2}(\w+):", match.group(1), re.MULTILINE))
        python_keys = set(STARTER_PRESET_KEYS)
        extra = ts_keys - python_keys
        assert not extra, f"Extra keys in TS constants not in Python: {extra}"
