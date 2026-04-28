"""Tests for autofyn update image tag resolution and orchestration logic."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from cli.commands.services import _resolve_image_tag, update_services
from cli.main import app


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
        update_services(branch_override=None, image_tag_override=None, force_build=False)
        mock_switch.assert_not_called()
        mock_git_pull.assert_called_once_with("main", skip_fetch=False)
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
        update_services(branch_override=None, image_tag_override=None, force_build=False)
        mock_git_pull.assert_called_once_with("production", skip_fetch=False)
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
        update_services(branch_override=None, image_tag_override=None, force_build=False)
        mock_git_pull.assert_called_once_with("fix-bug", skip_fetch=False)
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
        update_services(branch_override=None, image_tag_override="abc1234", force_build=False)
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
        update_services(branch_override=None, image_tag_override=None, force_build=True)
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
        update_services(branch_override=None, image_tag_override=None, force_build=False)
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
        update_services(branch_override="production", image_tag_override=None, force_build=False)
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
        update_services(branch_override="my-feature", image_tag_override=None, force_build=False)
        mock_switch.assert_called_once_with("my-feature")
        mock_git_pull.assert_called_once_with("my-feature", skip_fetch=True)
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
        update_services(branch_override="my-feature", image_tag_override=None, force_build=True)
        mock_switch.assert_called_once_with("my-feature")
        mock_git_pull.assert_called_once_with("my-feature", skip_fetch=True)
        mock_pull.assert_not_called()
        mock_build.assert_called_once()

    @patch(f"{MODULE}._git_pull")
    @patch(f"{MODULE}._detect_branch", return_value="production")
    @patch(f"{MODULE}._pull_images", return_value=True)
    @patch(f"{MODULE}._switch_branch")
    def test_git_pull_uses_detected_branch_not_hardcoded(
        self,
        _mock_switch: MagicMock,
        _mock_pull: MagicMock,
        _mock_detect: MagicMock,
        mock_git_pull: MagicMock,
    ) -> None:
        """git pull resets to the detected branch, not hardcoded main."""
        update_services(branch_override=None, image_tag_override=None, force_build=False)
        mock_git_pull.assert_called_once_with("production", skip_fetch=False)

    @patch(f"{MODULE}._git_pull")
    @patch(f"{MODULE}._detect_branch", return_value="main")
    @patch(f"{MODULE}._pull_images", return_value=True)
    @patch(f"{MODULE}._switch_branch")
    def test_no_branch_override_fetches_in_git_pull(
        self,
        _mock_switch: MagicMock,
        _mock_pull: MagicMock,
        _mock_detect: MagicMock,
        mock_git_pull: MagicMock,
    ) -> None:
        """Without --branch, git pull does its own fetch (skip_fetch=False)."""
        update_services(branch_override=None, image_tag_override=None, force_build=False)
        mock_git_pull.assert_called_once_with("main", skip_fetch=False)

    @patch(f"{MODULE}._git_pull")
    @patch(f"{MODULE}._detect_branch", return_value="production")
    @patch(f"{MODULE}._pull_images", return_value=True)
    @patch(f"{MODULE}._switch_branch")
    def test_branch_override_skips_fetch_in_git_pull(
        self,
        _mock_switch: MagicMock,
        _mock_pull: MagicMock,
        _mock_detect: MagicMock,
        mock_git_pull: MagicMock,
    ) -> None:
        """With --branch, git pull skips fetch (already fetched by switch)."""
        update_services(branch_override="production", image_tag_override=None, force_build=False)
        mock_git_pull.assert_called_once_with("production", skip_fetch=True)


class TestUpdateCli:
    """Tests for autofyn update CLI argument validation."""

    def test_build_and_image_tag_mutually_exclusive(self) -> None:
        """--build and --image-tag together exits with error."""
        runner = CliRunner()
        result = runner.invoke(app, ["update", "--build", "--image-tag", "abc1234"])
        assert result.exit_code == 1
        assert "mutually exclusive" in result.output
