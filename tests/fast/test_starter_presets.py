"""Regression tests for starter presets.

Verifies that each preset key in STARTER_PRESET_KEYS has a loadable
markdown file, that StartRequest validates preset/prompt exclusivity,
and that the preset keys stay in sync between Python and TypeScript.
"""

import subprocess

import pytest
from pydantic import ValidationError

from db.constants import STARTER_PRESET_KEYS


class TestStarterPresetFiles:
    """Each preset key must have a corresponding markdown file."""

    @pytest.mark.parametrize("key", STARTER_PRESET_KEYS)
    def test_preset_file_loadable(self, key: str) -> None:
        from prompts.loader import load_markdown
        content = load_markdown(f"starter/{key}")
        assert len(content) > 0


class TestStartRequestPresetValidation:
    """StartRequest enforces preset/prompt mutual exclusivity."""

    def test_accepts_valid_preset(self) -> None:
        from utils.models import StartRequest
        req = StartRequest(preset="security_hardening")
        assert req.preset == "security_hardening"
        assert req.prompt is None

    def test_accepts_prompt_without_preset(self) -> None:
        from utils.models import StartRequest
        req = StartRequest(prompt="fix the bug")
        assert req.prompt == "fix the bug"
        assert req.preset is None

    def test_rejects_both_prompt_and_preset(self) -> None:
        from utils.models import StartRequest
        with pytest.raises(ValidationError, match="Cannot set both"):
            StartRequest(prompt="fix", preset="security_hardening")

    def test_rejects_invalid_preset_key(self) -> None:
        from utils.models import StartRequest
        with pytest.raises(ValidationError, match="preset must be one of"):
            StartRequest(preset="invalid_key")

    def test_accepts_neither_prompt_nor_preset(self) -> None:
        from utils.models import StartRequest
        req = StartRequest()
        assert req.prompt is None
        assert req.preset is None


class TestStarterPresetSync:
    """Python and TypeScript preset key sets must match."""

    def test_frontend_constants_contain_all_preset_keys(self) -> None:
        result = subprocess.run(
            ["grep", "-o", "security_hardening\\|bug_sweep\\|code_quality\\|test_coverage",
             "dashboard/frontend/lib/constants.ts"],
            capture_output=True, text=True,
        )
        found_keys = set(result.stdout.strip().split("\n"))
        python_keys = set(STARTER_PRESET_KEYS)
        assert found_keys == python_keys, f"Mismatch: Python={python_keys}, TS={found_keys}"
