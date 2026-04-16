"""Tests for dashboard/entrypoint.sh key-leak mitigations.

Static-grep style: reads the shell script and asserts the insecure
patterns are gone and the masked form is present.
"""

from pathlib import Path


_ENTRYPOINT_PATH = Path(__file__).parents[2] / "dashboard" / "entrypoint.sh"

_RAW_KEY_ECHO = 'echo "[dashboard] API key: ${API_KEY}"'
_CONFIG_JS_WRITE = "window.__AUTOFYN_API_KEY__"
_CONFIG_JS_PATH = "/app/frontend/public/config.js"
_MASKED_FORM = "${API_KEY:0:4}****"


def _entrypoint_text() -> str:
    return _ENTRYPOINT_PATH.read_text()


class TestEntrypointNoKeyLeak:
    """entrypoint.sh must not print or write the raw API key."""

    def test_no_raw_api_key_echo(self) -> None:
        assert _RAW_KEY_ECHO not in _entrypoint_text()

    def test_no_config_js_key_write(self) -> None:
        text = _entrypoint_text()
        assert _CONFIG_JS_WRITE not in text

    def test_no_config_js_path_written(self) -> None:
        """The /app/frontend/public/config.js file must not be referenced in a write."""
        text = _entrypoint_text()
        # Accept it not being referenced at all, or only in a comment (no echo/write)
        lines_with_path = [
            line for line in text.splitlines()
            if _CONFIG_JS_PATH in line and not line.strip().startswith("#")
        ]
        assert lines_with_path == [], (
            f"Found non-comment references to config.js: {lines_with_path}"
        )

    def test_masked_form_present(self) -> None:
        assert _MASKED_FORM in _entrypoint_text()

    def test_dashboard_api_key_exported(self) -> None:
        """DASHBOARD_API_KEY must be exported for the Next.js process to inherit it."""
        assert "export DASHBOARD_API_KEY" in _entrypoint_text()
