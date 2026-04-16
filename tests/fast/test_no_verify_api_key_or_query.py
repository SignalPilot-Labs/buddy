"""Static regression: verify_api_key_or_query must not exist anywhere in the codebase.

This test catches future re-introduction of the removed query-param auth path.
Uses sys.modules injection to avoid the /data/api.key requirement.
"""

import pathlib
import sys


def _get_auth_module() -> object:
    """Return the real backend.auth module, loading it with a mocked API key file."""
    # Remove any cached version so we load fresh with our stub.
    for key in list(sys.modules):
        if key == "backend.auth":
            del sys.modules[key]

    # Stub pathlib.Path.exists and read_text for the key file only.
    import pathlib as _pathlib
    original_exists = _pathlib.Path.exists
    original_read_text = _pathlib.Path.read_text

    def patched_exists(self: _pathlib.Path, **kwargs: object) -> bool:
        if str(self) == "/data/api.key":
            return True
        return original_exists(self, **kwargs)  # type: ignore[call-arg]

    def patched_read_text(self: _pathlib.Path, *args: object, **kwargs: object) -> str:
        if str(self) == "/data/api.key":
            return "test-api-key-static-check"
        return original_read_text(self, *args, **kwargs)  # type: ignore[call-arg]

    _pathlib.Path.exists = patched_exists  # type: ignore[method-assign]
    _pathlib.Path.read_text = patched_read_text  # type: ignore[method-assign]
    try:
        import backend.auth as auth_module
        return auth_module
    finally:
        _pathlib.Path.exists = original_exists  # type: ignore[method-assign]
        _pathlib.Path.read_text = original_read_text  # type: ignore[method-assign]


class TestNoQueryApiKeyFunction:
    """verify_api_key_or_query is permanently deleted — enforce statically."""

    def test_symbol_not_on_auth_module(self) -> None:
        """The function must not exist on the auth module at all."""
        auth_module = _get_auth_module()
        assert not hasattr(auth_module, "verify_api_key_or_query")

    def test_no_occurrences_in_codebase(self) -> None:
        """Repo-wide grep: zero occurrences of the literal string in non-test files.

        Scans dashboard/**/*.py, autofyn/**/*.py, cli/**/*.py, sandbox/**/*.py.
        Excludes all test files (they may reference the name in comments/assertions
        about its absence) and this file itself.
        Production code must have zero occurrences.
        """
        search_roots = [
            pathlib.Path("dashboard"),
            pathlib.Path("autofyn"),
            pathlib.Path("cli"),
            pathlib.Path("sandbox"),
        ]
        matches: list[str] = []
        for root in search_roots:
            if not root.exists():
                continue
            for py_file in root.rglob("*.py"):
                try:
                    text = py_file.read_text(encoding="utf-8")
                except OSError:
                    continue
                if "verify_api_key_or_query" in text:
                    matches.append(str(py_file))

        assert matches == [], (
            f"verify_api_key_or_query found in: {matches} — "
            "the query-param auth path must remain deleted"
        )
