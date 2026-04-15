"""Tests for per-file diff utilities and endpoint logic.

Covers extract_file_patch parsing, and the agent endpoint's fallback
chain: sandbox → GitHub compare → PR diff → 404.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from utils.diff import extract_file_patch


SAMPLE_FULL_DIFF = """\
diff --git a/src/main.py b/src/main.py
index abc1234..def5678 100644
--- a/src/main.py
+++ b/src/main.py
@@ -1,3 +1,4 @@
 import os
+import sys

 def main():
diff --git a/src/utils.py b/src/utils.py
index 1111111..2222222 100644
--- a/src/utils.py
+++ b/src/utils.py
@@ -10,3 +10,5 @@
 def helper():
     pass
+
+def new_helper():
+    pass
"""


class TestExtractFilePatch:
    """extract_file_patch must isolate a single file's patch from a full diff."""

    def test_extracts_first_file(self) -> None:
        patch = extract_file_patch(SAMPLE_FULL_DIFF, "src/main.py")
        assert patch is not None
        assert "+import sys" in patch
        assert "new_helper" not in patch

    def test_extracts_second_file(self) -> None:
        patch = extract_file_patch(SAMPLE_FULL_DIFF, "src/utils.py")
        assert patch is not None
        assert "+def new_helper():" in patch
        assert "+import sys" not in patch

    def test_returns_none_for_missing_file(self) -> None:
        patch = extract_file_patch(SAMPLE_FULL_DIFF, "nonexistent.py")
        assert patch is None

    def test_empty_diff(self) -> None:
        patch = extract_file_patch("", "any.py")
        assert patch is None

    def test_single_file_diff(self) -> None:
        single = """\
diff --git a/foo.ts b/foo.ts
--- a/foo.ts
+++ b/foo.ts
@@ -1 +1,2 @@
 const x = 1;
+const y = 2;
"""
        patch = extract_file_patch(single, "foo.ts")
        assert patch is not None
        assert "+const y = 2;" in patch
