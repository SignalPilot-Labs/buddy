"""F5: _store_git_token stores the token without writing to disk."""

from pathlib import Path

import pytest

from handlers.repo_env import clear_git_token, get_git_token
from handlers.repo import _store_git_token


class TestStoreGitToken:
    """_store_git_token must store token in memory only — no .gitconfig on disk."""

    def setup_method(self) -> None:
        clear_git_token()

    def teardown_method(self) -> None:
        clear_git_token()

    @pytest.mark.asyncio
    async def test_token_stored_in_memory(self) -> None:
        await _store_git_token("my-git-token")
        assert get_git_token() == "my-git-token"

    @pytest.mark.asyncio
    async def test_no_gitconfig_written(self) -> None:
        """The function must not write any .gitconfig file."""
        home = Path.home()
        gitconfig = home / ".gitconfig"
        existed_before = gitconfig.exists()

        await _store_git_token("my-git-token")

        if not existed_before:
            # If the file didn't exist before, it still shouldn't
            assert not gitconfig.exists(), ".gitconfig should not have been created"

    @pytest.mark.asyncio
    async def test_no_tmp_gitconfig_written(self) -> None:
        """The function must not write to /tmp/git-isolated/.gitconfig."""
        gitconfig = Path("/tmp/git-isolated/.gitconfig")
        existed_before = gitconfig.exists()

        await _store_git_token("my-git-token")

        if not existed_before:
            assert not gitconfig.exists(), "/tmp/git-isolated/.gitconfig should not be created"
