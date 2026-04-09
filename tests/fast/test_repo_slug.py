"""Tests for the repo slug regex used in the DELETE /repos endpoint."""

import re


class TestRepoSlugValidation:
    """Tests for the repo slug regex."""

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
