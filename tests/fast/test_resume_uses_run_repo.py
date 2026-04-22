"""Regression test: resume must use run.github_repo, not settings.

Source-level test verifying _resume_completed_run builds the resume
body with run.github_repo (the run's original repo) instead of
creds.get("github_repo") (the currently active settings repo).
"""

from pathlib import Path

RUNS_SRC = (Path(__file__).parent.parent.parent / "dashboard" / "backend" / "endpoints" / "runs.py").read_text()


class TestResumeUsesRunRepo:
    """_resume_completed_run must reference run.github_repo in the resume body."""

    def test_resume_body_uses_run_github_repo(self) -> None:
        """The resume_body dict must use run.github_repo, not creds-based repo."""
        # Find the _resume_completed_run function
        start = RUNS_SRC.index("async def _resume_completed_run")
        # Find the next top-level function to bound the search
        next_fn = RUNS_SRC.index("\nasync def ", start + 1)
        fn_src = RUNS_SRC[start:next_fn]

        # The resume_body must contain run.github_repo
        assert "run.github_repo" in fn_src, (
            "_resume_completed_run must use run.github_repo in resume_body"
        )
        # Must NOT use creds.get("github_repo") for the repo field
        # (creds are fine for tokens, but repo must come from the Run record)
        body_block = fn_src[fn_src.index("resume_body"):]
        body_block = body_block[:body_block.index("}") + 1]
        assert 'creds.get("github_repo")' not in body_block, (
            "resume_body must not read github_repo from creds (settings) — use run.github_repo"
        )

    def test_resume_body_still_uses_creds_for_tokens(self) -> None:
        """Tokens should still come from creds (not hardcoded or from run)."""
        start = RUNS_SRC.index("async def _resume_completed_run")
        next_fn = RUNS_SRC.index("\nasync def ", start + 1)
        fn_src = RUNS_SRC[start:next_fn]

        assert 'creds.get("claude_token")' in fn_src
        assert 'creds.get("git_token")' in fn_src
