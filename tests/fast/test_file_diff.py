"""Tests for per-file diff utilities.

Covers extract_file_patch parsing: boundary matching, binary files,
prefix false-positive prevention, and fetch_github_file_diff fallback chain.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from utils.diff import extract_file_patch, fetch_github_file_diff


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
        result = extract_file_patch(SAMPLE_FULL_DIFF, "src/main.py")
        assert result is not None
        assert "+import sys" in result
        assert "new_helper" not in result

    def test_extracts_second_file(self) -> None:
        result = extract_file_patch(SAMPLE_FULL_DIFF, "src/utils.py")
        assert result is not None
        assert "+def new_helper():" in result
        assert "+import sys" not in result

    def test_returns_none_for_missing_file(self) -> None:
        assert extract_file_patch(SAMPLE_FULL_DIFF, "nonexistent.py") is None

    def test_empty_diff(self) -> None:
        assert extract_file_patch("", "any.py") is None

    def test_single_file_diff(self) -> None:
        single = """\
diff --git a/foo.ts b/foo.ts
--- a/foo.ts
+++ b/foo.ts
@@ -1 +1,2 @@
 const x = 1;
+const y = 2;
"""
        result = extract_file_patch(single, "foo.ts")
        assert result is not None
        assert "+const y = 2;" in result

    def test_no_prefix_false_positive(self) -> None:
        """foo.py must not match foo.py.bak."""
        diff = """\
diff --git a/foo.py.bak b/foo.py.bak
--- a/foo.py.bak
+++ b/foo.py.bak
@@ -1 +1,2 @@
 old
+new
"""
        assert extract_file_patch(diff, "foo.py") is None

    def test_binary_file_returns_none(self) -> None:
        diff = """\
diff --git a/image.png b/image.png
Binary files a/image.png and b/image.png differ
"""
        assert extract_file_patch(diff, "image.png") is None


class TestFetchGithubFileDiff:
    """fetch_github_file_diff must try compare, then PR, then error."""

    @pytest.mark.asyncio
    async def test_compare_success(self) -> None:
        """GitHub compare returns 200 → extract patch."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = SAMPLE_FULL_DIFF

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("utils.diff.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_github_file_diff("o/r", "feat", "main", "src/main.py", "tok")
        assert "+import sys" in result["patch"]

    @pytest.mark.asyncio
    async def test_compare_404_pr_found(self) -> None:
        """Compare 404 → finds PR → fetches PR diff."""
        call_count = 0

        async def mock_get(url: str, **kwargs: object) -> MagicMock:
            nonlocal call_count
            call_count += 1
            resp = MagicMock()
            if call_count == 1:  # compare
                resp.status_code = 404
            elif call_count == 2:  # PR list
                resp.status_code = 200
                resp.json.return_value = [{"number": 42}]
            elif call_count == 3:  # PR diff
                resp.status_code = 200
                resp.text = SAMPLE_FULL_DIFF
            return resp

        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("utils.diff.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_github_file_diff("o/r", "feat", "main", "src/main.py", "tok")
        assert "+import sys" in result["patch"]

    @pytest.mark.asyncio
    async def test_compare_404_no_pr(self) -> None:
        """Compare 404, no PR found → error with message."""
        call_count = 0

        async def mock_get(url: str, **kwargs: object) -> MagicMock:
            nonlocal call_count
            call_count += 1
            resp = MagicMock()
            if call_count == 1:
                resp.status_code = 404
            elif call_count == 2:
                resp.status_code = 200
                resp.json.return_value = []
            return resp

        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("utils.diff.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_github_file_diff("o/r", "deleted", "main", "x.py", "tok")
        assert "error" in result
        assert "no PR found" in result["error"]

    @pytest.mark.asyncio
    async def test_github_api_error(self) -> None:
        """Non-404 error from compare → returns error."""
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.text = "rate limited"

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("utils.diff.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_github_file_diff("o/r", "feat", "main", "x.py", "tok")
        assert "error" in result
        assert result["status"] == 403
