"""Tests for autofyn update image tag resolution and orchestration logic."""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from cli.commands.services import _resolve_image_tag, update_services


class TestResolveImageTag:
    """Tests for _resolve_image_tag branch-to-tag mapping."""

    def test_production_maps_to_stable(self) -> None:
        """production branch resolves to stable tag."""
        assert _resolve_image_tag("production", None) == "stable"

    def test_main_maps_to_nightly(self) -> None:
        """main branch resolves to nightly tag."""
        assert _resolve_image_tag("main", None) == "nightly"

    def test_feature_branch_returns_none(self) -> None:
        """Unknown branches return None (no pre-built image)."""
        assert _resolve_image_tag("fix-auth-bug", None) is None

    def test_image_tag_override_beats_branch(self) -> None:
        """Explicit image tag override takes precedence over branch mapping."""
        assert _resolve_image_tag("production", "abc1234") == "abc1234"

    def test_image_tag_override_on_unknown_branch(self) -> None:
        """Override works even on branches with no default mapping."""
        assert _resolve_image_tag("my-feature", "abc1234") == "abc1234"


MODULE = "cli.commands.services"


class TestUpdateServices:
    """Tests for update_services orchestration — branch switching, pull vs build."""

    @patch(f"{MODULE}._git_pull")
    @patch(f"{MODULE}._detect_branch", return_value="main")
    @patch(f"{MODULE}._pull_images", return_value=True)
    @patch(f"{MODULE}._switch_branch")
    def test_main_branch_pulls_nightly(
        self,
        mock_switch: MagicMock,
        mock_pull: MagicMock,
        mock_detect: MagicMock,
        mock_git_pull: MagicMock,
    ) -> None:
        """On main branch, pulls nightly images."""
        update_services(None, None, False)
        mock_switch.assert_not_called()
        mock_pull.assert_called_once_with("nightly")

    @patch(f"{MODULE}._git_pull")
    @patch(f"{MODULE}._detect_branch", return_value="production")
    @patch(f"{MODULE}._pull_images", return_value=True)
    @patch(f"{MODULE}._switch_branch")
    def test_production_branch_pulls_stable(
        self,
        mock_switch: MagicMock,
        mock_pull: MagicMock,
        mock_detect: MagicMock,
        mock_git_pull: MagicMock,
    ) -> None:
        """On production branch, pulls stable images."""
        update_services(None, None, False)
        mock_pull.assert_called_once_with("stable")

    @patch(f"{MODULE}._git_pull")
    @patch(f"{MODULE}._detect_branch", return_value="fix-bug")
    @patch(f"{MODULE}._pull_images")
    @patch(f"{MODULE}.build_services")
    @patch(f"{MODULE}._switch_branch")
    def test_feature_branch_builds_locally(
        self,
        mock_switch: MagicMock,
        mock_build: MagicMock,
        mock_pull: MagicMock,
        mock_detect: MagicMock,
        mock_git_pull: MagicMock,
    ) -> None:
        """Feature branches have no GHCR images — builds locally."""
        update_services(None, None, False)
        mock_pull.assert_not_called()
        mock_build.assert_called_once()

    @patch(f"{MODULE}._git_pull")
    @patch(f"{MODULE}._detect_branch", return_value="main")
    @patch(f"{MODULE}._pull_images", return_value=True)
    @patch(f"{MODULE}._switch_branch")
    def test_image_tag_override(
        self,
        mock_switch: MagicMock,
        mock_pull: MagicMock,
        mock_detect: MagicMock,
        mock_git_pull: MagicMock,
    ) -> None:
        """--image-tag overrides branch-based tag."""
        update_services(None, "abc1234", False)
        mock_pull.assert_called_once_with("abc1234")

    @patch(f"{MODULE}._git_pull")
    @patch(f"{MODULE}._detect_branch", return_value="main")
    @patch(f"{MODULE}._pull_images")
    @patch(f"{MODULE}.build_services")
    @patch(f"{MODULE}._switch_branch")
    def test_force_build_skips_pull(
        self,
        mock_switch: MagicMock,
        mock_build: MagicMock,
        mock_pull: MagicMock,
        mock_detect: MagicMock,
        mock_git_pull: MagicMock,
    ) -> None:
        """--build forces local build, never attempts pull."""
        update_services(None, None, True)
        mock_pull.assert_not_called()
        mock_build.assert_called_once()

    @patch(f"{MODULE}._git_pull")
    @patch(f"{MODULE}._detect_branch", return_value="main")
    @patch(f"{MODULE}._pull_images", return_value=False)
    @patch(f"{MODULE}.build_services")
    @patch(f"{MODULE}._switch_branch")
    def test_pull_failure_falls_back_to_build(
        self,
        mock_switch: MagicMock,
        mock_build: MagicMock,
        mock_pull: MagicMock,
        mock_detect: MagicMock,
        mock_git_pull: MagicMock,
    ) -> None:
        """When pull fails, falls back to local build."""
        update_services(None, None, False)
        mock_pull.assert_called_once_with("nightly")
        mock_build.assert_called_once()

    @patch(f"{MODULE}._git_pull")
    @patch(f"{MODULE}._detect_branch", return_value="main")
    @patch(f"{MODULE}._pull_images", return_value=True)
    @patch(f"{MODULE}._switch_branch")
    def test_branch_override_switches_first(
        self,
        mock_switch: MagicMock,
        mock_pull: MagicMock,
        mock_detect: MagicMock,
        mock_git_pull: MagicMock,
    ) -> None:
        """--branch switches branch before detecting and pulling."""
        update_services("production", None, False)
        mock_switch.assert_called_once_with("production")

    @patch(f"{MODULE}._git_pull")
    @patch(f"{MODULE}._detect_branch", return_value="my-feature")
    @patch(f"{MODULE}._pull_images")
    @patch(f"{MODULE}.build_services")
    @patch(f"{MODULE}._switch_branch")
    def test_branch_override_to_feature_builds(
        self,
        mock_switch: MagicMock,
        mock_build: MagicMock,
        mock_pull: MagicMock,
        mock_detect: MagicMock,
        mock_git_pull: MagicMock,
    ) -> None:
        """--branch to a feature branch switches then builds locally."""
        update_services("my-feature", None, False)
        mock_switch.assert_called_once_with("my-feature")
        mock_pull.assert_not_called()
        mock_build.assert_called_once()

    @patch(f"{MODULE}._git_pull")
    @patch(f"{MODULE}._detect_branch", return_value="my-feature")
    @patch(f"{MODULE}._pull_images")
    @patch(f"{MODULE}.build_services")
    @patch(f"{MODULE}._switch_branch")
    def test_branch_override_with_force_build(
        self,
        mock_switch: MagicMock,
        mock_build: MagicMock,
        mock_pull: MagicMock,
        mock_detect: MagicMock,
        mock_git_pull: MagicMock,
    ) -> None:
        """--branch + --build switches branch then builds, no pull attempt."""
        update_services("my-feature", None, True)
        mock_switch.assert_called_once_with("my-feature")
        mock_pull.assert_not_called()
        mock_build.assert_called_once()
