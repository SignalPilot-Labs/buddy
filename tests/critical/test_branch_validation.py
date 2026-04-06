"""Tests for validate_branch_name."""

import pytest

from utils.helpers import validate_branch_name


class TestValidateBranchName:
    """Tests for validate_branch_name."""

    def test_valid_simple_branch(self):
        validate_branch_name("main")
        validate_branch_name("feature-123")
        validate_branch_name("bugfix/issue_42")
        validate_branch_name("autofyn/2026-04-03-abc123")

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
