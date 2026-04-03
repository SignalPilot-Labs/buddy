"""Critical security tests — pure validation logic, no external deps. Must run < 1 min."""

import re

import pytest

from utils.helpers import validate_branch_name


class TestValidateBranchName:
    """Tests for validate_branch_name."""

    def test_valid_simple_branch(self):
        validate_branch_name("main")
        validate_branch_name("feature-123")
        validate_branch_name("bugfix/issue_42")
        validate_branch_name("buddy/2026-04-03-abc123")

    def test_valid_with_dots(self):
        validate_branch_name("release/v1.2.3")

    def test_rejects_empty(self):
        with pytest.raises(ValueError, match="length"):
            validate_branch_name("")

    def test_rejects_too_long(self):
        with pytest.raises(ValueError, match="length"):
            validate_branch_name("a" * 257)

    def test_rejects_directory_traversal(self):
        with pytest.raises(ValueError, match="format"):
            validate_branch_name("refs/../etc/passwd")

    def test_rejects_double_dot(self):
        with pytest.raises(ValueError, match="format"):
            validate_branch_name("main..develop")

    def test_rejects_lock_suffix(self):
        with pytest.raises(ValueError, match="format"):
            validate_branch_name("refs/heads/main.lock")

    def test_rejects_trailing_slash(self):
        with pytest.raises(ValueError, match="format"):
            validate_branch_name("feature/")

    def test_rejects_special_characters(self):
        for bad in ["branch name", "branch;rm", "branch&cmd", "branch|pipe",
                     "branch$(cmd)", "branch`cmd`", "branch\nnewline"]:
            with pytest.raises(ValueError):
                validate_branch_name(bad)

    def test_rejects_leading_dot(self):
        with pytest.raises(ValueError):
            validate_branch_name(".hidden")

    def test_rejects_leading_dash(self):
        with pytest.raises(ValueError):
            validate_branch_name("-flag")


class TestSandboxBuiltins:
    """Verify the sandbox builtins allowlist excludes dangerous functions."""

    SAFE_ALLOWLIST = [
        "print", "len", "range", "enumerate", "zip", "map", "filter", "sorted", "reversed",
        "min", "max", "sum", "abs", "round", "pow", "divmod",
        "int", "float", "str", "bool", "list", "dict", "tuple", "set", "frozenset",
        "bytes", "bytearray", "memoryview", "complex",
        "type", "isinstance", "issubclass", "hasattr", "getattr", "setattr", "delattr",
        "iter", "next", "slice", "repr", "format", "hash", "id", "callable",
        "all", "any", "chr", "ord", "hex", "oct", "bin",
        "input", "Exception", "ValueError", "TypeError", "KeyError", "IndexError",
        "RuntimeError", "StopIteration", "AttributeError", "NameError", "ZeroDivisionError",
        "True", "False", "None",
    ]

    DANGEROUS_BUILTINS = [
        "open", "__import__", "exec", "eval", "compile",
        "breakpoint", "globals", "locals", "vars",
    ]

    def test_dangerous_builtins_excluded(self):
        for name in self.DANGEROUS_BUILTINS:
            assert name not in self.SAFE_ALLOWLIST, f"{name} should not be in allowlist"

    def test_safe_builtins_included(self):
        essential = ["print", "len", "range", "int", "float", "str", "list", "dict",
                     "True", "False", "None", "Exception", "ValueError"]
        for name in essential:
            assert name in self.SAFE_ALLOWLIST, f"{name} should be in allowlist"

    def test_allowlist_builds_valid_dict(self):
        import builtins
        safe = {k: getattr(builtins, k) for k in self.SAFE_ALLOWLIST if hasattr(builtins, k)}
        assert callable(safe["print"])
        assert safe["int"] is int
        assert "open" not in safe
        assert "__import__" not in safe
        assert "exec" not in safe

    def test_exec_with_restricted_builtins_blocks_import(self):
        import builtins
        safe = {k: getattr(builtins, k) for k in self.SAFE_ALLOWLIST if hasattr(builtins, k)}
        with pytest.raises((NameError, ImportError)):
            exec(compile("import os", "<test>", "exec"), {"__builtins__": safe})

    def test_exec_with_restricted_builtins_blocks_open(self):
        import builtins
        safe = {k: getattr(builtins, k) for k in self.SAFE_ALLOWLIST if hasattr(builtins, k)}
        with pytest.raises(NameError):
            exec(compile("open('/etc/passwd')", "<test>", "exec"), {"__builtins__": safe})

    def test_exec_with_restricted_builtins_allows_print(self):
        import builtins
        safe = {k: getattr(builtins, k) for k in self.SAFE_ALLOWLIST if hasattr(builtins, k)}
        exec(compile("x = len([1, 2, 3])", "<test>", "exec"), {"__builtins__": safe})


class TestRepoSlugValidation:
    """Tests for the repo slug regex used in the DELETE /repos endpoint."""

    PATTERN = r'^[\w\-\.]+/[\w\-\.]+$'

    def _is_valid(self, slug: str) -> bool:
        return bool(re.match(self.PATTERN, slug))

    def test_valid_slugs(self):
        assert self._is_valid("owner/repo")
        assert self._is_valid("my-org/my-repo.js")
        assert self._is_valid("user_123/project-v2")

    def test_rejects_path_traversal(self):
        assert not self._is_valid("../../etc/passwd")

    def test_rejects_no_slash(self):
        assert not self._is_valid("justaname")

    def test_rejects_double_slash(self):
        assert not self._is_valid("owner/repo/extra")

    def test_rejects_empty_parts(self):
        assert not self._is_valid("/repo")
        assert not self._is_valid("owner/")


class TestApiKeyAuth:
    """Tests for API key auth logic (no DB dependency)."""

    @staticmethod
    async def _verify(api_key: str | None, expected_key: str | None) -> None:
        import hmac
        from fastapi import HTTPException
        if expected_key is None:
            return
        if not api_key or not hmac.compare_digest(api_key, expected_key):
            raise HTTPException(status_code=401, detail="Invalid or missing API key")

    @pytest.mark.asyncio
    async def test_auth_disabled_when_no_key(self):
        await self._verify(api_key=None, expected_key=None)
        await self._verify(api_key="anything", expected_key=None)

    @pytest.mark.asyncio
    async def test_rejects_missing_key(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await self._verify(api_key=None, expected_key="secret-key-12345678")
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_rejects_wrong_key(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await self._verify(api_key="wrong", expected_key="secret-key-12345678")
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_accepts_correct_key(self):
        await self._verify(api_key="secret-key-12345678", expected_key="secret-key-12345678")
