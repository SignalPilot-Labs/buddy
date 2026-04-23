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
