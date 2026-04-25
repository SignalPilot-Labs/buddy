"""Regression test: API key must NOT be written to a static public/config.js file.

Finding: CRIT-2 — API key exposed in unauthenticated static file (/public/config.js).
Fix: key injected server-side by layout.tsx into an inline <script> at render time.
"""

from __future__ import annotations

import re
from pathlib import Path


ENTRYPOINT_PATH = Path(__file__).parents[2] / "dashboard" / "entrypoint.sh"
LAYOUT_PATH = Path(__file__).parents[2] / "dashboard" / "frontend" / "app" / "layout.tsx"

# Matches lines that write anything to a public/config.js path.
_CONFIG_JS_WRITE_PATTERN = re.compile(r"public/config\.js")

# Matches a static <script src=...config.js...> tag.
_STATIC_SCRIPT_SRC_PATTERN = re.compile(r'<script[^>]+src=["\'][^"\']*config\.js["\']')

# Matches the env var assignment to the node server.js invocation.
_AUTOFYN_API_KEY_ENV_PATTERN = re.compile(r'AUTOFYN_API_KEY="\$API_KEY".*node server\.js')

# Matches the dangerouslySetInnerHTML inline injection of __AUTOFYN_API_KEY__.
_INLINE_INJECT_PATTERN = re.compile(r"dangerouslySetInnerHTML.*__AUTOFYN_API_KEY__", re.DOTALL)

# Matches presence of the \\u003c XSS escape in the inline script.
_XSS_ESCAPE_PATTERN = re.compile(r"\\\\u003c|\\u003c")


class TestNoStaticConfigJs:
    """entrypoint.sh must not write config.js; layout.tsx must use inline injection."""

    def test_entrypoint_does_not_write_config_js(self) -> None:
        """entrypoint.sh must not write the API key to any public/config.js path."""
        content = ENTRYPOINT_PATH.read_text()
        offending = [
            line.strip()
            for line in content.splitlines()
            if _CONFIG_JS_WRITE_PATTERN.search(line)
        ]
        assert offending == [], (
            "Found lines writing to public/config.js in entrypoint.sh:\n"
            + "\n".join(f"  {line}" for line in offending)
        )

    def test_layout_does_not_load_static_config_js(self) -> None:
        """layout.tsx must not load config.js via a static <script src=...> tag."""
        content = LAYOUT_PATH.read_text()
        assert not _STATIC_SCRIPT_SRC_PATTERN.search(content), (
            "layout.tsx still contains a static <script src=...config.js> tag; "
            "remove it and use the inline dangerouslySetInnerHTML injection instead."
        )

    def test_entrypoint_passes_autofyn_api_key_to_node(self) -> None:
        """The node server.js invocation must receive AUTOFYN_API_KEY as an env var."""
        content = ENTRYPOINT_PATH.read_text()
        assert _AUTOFYN_API_KEY_ENV_PATTERN.search(content), (
            "entrypoint.sh does not pass AUTOFYN_API_KEY to node server.js. "
            "Expected a line like: AUTOFYN_API_KEY=\"$API_KEY\" ... node server.js"
        )

    def test_layout_contains_inline_key_injection(self) -> None:
        """layout.tsx must contain a dangerouslySetInnerHTML block that sets __AUTOFYN_API_KEY__."""
        content = LAYOUT_PATH.read_text()
        assert _INLINE_INJECT_PATTERN.search(content), (
            "layout.tsx does not contain a dangerouslySetInnerHTML injection of "
            "__AUTOFYN_API_KEY__. The server-side inline script injection is missing."
        )

    def test_layout_inline_script_has_xss_escape(self) -> None:
        """The inline script in layout.tsx must escape '<' to prevent </script> breakout XSS."""
        content = LAYOUT_PATH.read_text()
        assert _XSS_ESCAPE_PATTERN.search(content), (
            "layout.tsx inline script does not escape '<' as \\u003c. "
            "JSON.stringify alone does not prevent </script> breakout; "
            "chain .replace(/</g, '\\\\u003c') after JSON.stringify."
        )
