"""Tests for per-run token isolation — tokens flow via env dict, not os.environ."""

import os
import sys
import types

from utils.constants import ENV_KEY_CLAUDE_TOKEN, ENV_KEY_GIT_TOKEN

# Provide a minimal fastapi stub so endpoints.py can be imported without the real package.
_fastapi_stub = types.ModuleType("fastapi")


class _HTTPException(Exception):
    def __init__(self, status_code: int = 500, detail: str = "") -> None:
        self.status_code = status_code
        self.detail = detail


_fastapi_stub.FastAPI = type("FastAPI", (), {})  # type: ignore[attr-defined]
_fastapi_stub.HTTPException = _HTTPException  # type: ignore[attr-defined]
sys.modules.setdefault("fastapi", _fastapi_stub)

# Provide a minimal utils.db stub so endpoints.py can be imported without DB.
_db_stub = types.ModuleType("utils.db")
sys.modules.setdefault("utils.db", _db_stub)

from endpoints import _merge_tokens_into_env  # noqa: E402


class TestTokenIsolation:
    """Verify that tokens are merged into body.env and never touch os.environ."""

    def test_tokens_merged_into_env_dict(self) -> None:
        result = _merge_tokens_into_env(None, "tok-a", "tok-b")
        assert result is not None
        assert result[ENV_KEY_CLAUDE_TOKEN] == "tok-a"
        assert result[ENV_KEY_GIT_TOKEN] == "tok-b"

    def test_tokens_do_not_touch_os_environ(self) -> None:
        original_claude = os.environ.get(ENV_KEY_CLAUDE_TOKEN)
        original_git = os.environ.get(ENV_KEY_GIT_TOKEN)

        _merge_tokens_into_env(None, "tok-a", "tok-b")

        assert os.environ.get(ENV_KEY_CLAUDE_TOKEN) == original_claude
        assert os.environ.get(ENV_KEY_GIT_TOKEN) == original_git

    def test_existing_env_preserved_with_tokens(self) -> None:
        existing = {"CUSTOM": "val"}
        result = _merge_tokens_into_env(existing, "tok-a", "tok-b")
        assert result is not None
        assert result["CUSTOM"] == "val"
        assert result[ENV_KEY_CLAUDE_TOKEN] == "tok-a"
        assert result[ENV_KEY_GIT_TOKEN] == "tok-b"

    def test_no_tokens_returns_env_unchanged(self) -> None:
        env: dict[str, str] = {"CUSTOM": "val"}
        result = _merge_tokens_into_env(env, None, None)
        assert result is env

    def test_no_tokens_with_none_env_returns_none(self) -> None:
        result = _merge_tokens_into_env(None, None, None)
        assert result is None
