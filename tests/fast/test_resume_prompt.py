"""Tests for Bootstrap._build_resume_prompt."""

from unittest.mock import MagicMock

from core.bootstrap import Bootstrap
from sandbox_manager.client import SandboxClient
from sandbox_manager.repo_ops import RepoOps


def _make_bootstrap() -> Bootstrap:
    mock_client = MagicMock(spec=SandboxClient)
    mock_env: dict[str, str] = {}
    return Bootstrap(RepoOps(mock_client, mock_env), mock_client)


class TestResumePromptBuilder:
    """Tests for Bootstrap._build_resume_prompt."""

    def test_includes_branch_and_status(self):
        bootstrap = _make_bootstrap()
        run_info = {"branch_name": "autofyn/test-branch", "status": "paused"}
        prompt = bootstrap._build_resume_prompt(run_info, None, [])
        assert "autofyn/test-branch" in prompt
        assert "paused" in prompt
        assert "Continue where you left off" in prompt

    def test_includes_operator_message(self):
        bootstrap = _make_bootstrap()
        run_info = {"branch_name": "test", "status": "running"}
        prompt = bootstrap._build_resume_prompt(run_info, "fix the auth bug", [])
        assert "fix the auth bug" in prompt
        assert "Operator message" in prompt
        assert "Continue where you left off" not in prompt

    def test_includes_original_task(self):
        bootstrap = _make_bootstrap()
        run_info = {
            "branch_name": "test", "status": "running",
            "custom_prompt": "Improve error handling across the codebase",
        }
        prompt = bootstrap._build_resume_prompt(run_info, None, [])
        assert "Improve error handling" in prompt
        assert "Original task" in prompt

    def test_includes_cost(self):
        bootstrap = _make_bootstrap()
        run_info = {"branch_name": "test", "status": "running", "total_cost_usd": 2.50}
        prompt = bootstrap._build_resume_prompt(run_info, None, [])
        assert "$2.50" in prompt

    def test_includes_operator_history(self):
        bootstrap = _make_bootstrap()
        run_info = {"branch_name": "test", "status": "completed"}
        messages = [
            {"ts": "2025-01-01T00:00:00", "prompt": "focus on auth"},
            {"ts": "2025-01-01T01:00:00", "prompt": "now fix tests"},
        ]
        prompt = bootstrap._build_resume_prompt(run_info, None, messages)
        assert "focus on auth" in prompt
        assert "now fix tests" in prompt
        assert "Previous operator messages" in prompt
