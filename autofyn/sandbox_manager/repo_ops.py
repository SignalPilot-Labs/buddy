"""Git repository operations via sandbox execution.

RepoOps replaces the direct-subprocess GitWorkspace. All git/gh commands
are delegated to the sandbox container through SandboxClient.exec().
"""

import asyncio
import base64
import json
import logging
import os
import uuid
from collections.abc import Callable, Coroutine
from datetime import datetime, timezone
from typing import Any

from utils.constants import (
    GIT_RETRY_ATTEMPTS,
    GIT_RETRY_DELAY_SEC,
    WORK_DIR,
)
from utils.helpers import validate_branch_name
from utils.models import ExecRequest, ExecResult
from sandbox_manager.client import SandboxClient
from sandbox_manager.repo_diff import aggregate_live_diff, parse_name_status, parse_numstat
from sandbox_manager.repo_init import bootstrap_empty_repo, create_missing_branch

log = logging.getLogger("sandbox_manager.repo_ops")


class RepoOps:
    """Git operations delegated to the sandbox container.

    Public API:
        setup_auth(repo, exec_timeout, clone_timeout) -> None
        ensure_base_branch(base_branch, exec_timeout) -> None
        get_branch_name() -> str
        create_branch(branch_name, base_branch, exec_timeout) -> str
        push_branch(branch_name, exec_timeout) -> None
        create_pr(branch_name, run_id, base_branch, exec_timeout) -> str
        get_branch_diff(branch_name, base_branch, exec_timeout) -> list[dict]
        get_branch_diff_live(base_branch, exec_timeout) -> list[dict]
        has_changes(exec_timeout) -> bool
        run_git(args, exec_timeout, cwd) -> str
        is_ready() -> bool
        get_work_dir() -> str
        checkout_branch(branch_name, base_branch, exec_timeout) -> None
    """

    def __init__(self, client: SandboxClient) -> None:
        self._client = client
        self._initialized = False
        self._repo = ""
        self._cloned_repo = ""
        self._init_lock = asyncio.Lock()

    def is_ready(self) -> bool:
        """Check if the repo is cloned and initialized."""
        return self._initialized

    def get_work_dir(self) -> str:
        """Return the sandbox working directory path."""
        return WORK_DIR

    # -- Git Commands --

    async def run_git(self, args: list[str], exec_timeout: int, cwd: str) -> str:
        """Run a git command in the sandbox."""
        result = await self._exec(
            ["git"] + args, cwd, exec_timeout, self._auth_env()
        )
        if result.exit_code != 0:
            raise RuntimeError(f"git failed: {result.stderr}")
        return result.stdout.strip()

    async def run_gh(self, args: list[str], exec_timeout: int) -> str:
        """Run a gh CLI command in the sandbox."""
        result = await self._exec(["gh"] + args, WORK_DIR, exec_timeout, self._auth_env())
        if result.exit_code != 0:
            raise RuntimeError(f"gh failed: {result.stderr}")
        return result.stdout.strip()

    # -- Setup --

    async def setup_auth(self, repo: str, exec_timeout: int, clone_timeout: int) -> None:
        """Clone the repo in sandbox and configure auth."""
        self._repo = repo
        await self._ensure_repo(clone_timeout)

    async def ensure_base_branch(self, base_branch: str, exec_timeout: int) -> None:
        """Verify the base branch exists on remote. Bootstrap empty repos."""
        validate_branch_name(base_branch)
        await self._ensure_repo(exec_timeout)
        try:
            all_refs = await self.run_git(
                ["ls-remote", "--heads", "origin"], exec_timeout, WORK_DIR,
            )
        except RuntimeError:
            all_refs = ""

        if not all_refs.strip():
            await bootstrap_empty_repo(self, base_branch, exec_timeout)
            return
        try:
            await self.run_git(
                ["ls-remote", "--exit-code", "--heads", "origin", base_branch],
                exec_timeout,
                WORK_DIR,
            )
        except RuntimeError:
            await create_missing_branch(self, base_branch, exec_timeout)

    async def create_branch(
        self, branch_name: str, base_branch: str, exec_timeout: int,
    ) -> str:
        """Create and checkout a new branch from the base branch."""
        validate_branch_name(branch_name)
        validate_branch_name(base_branch)
        await self._ensure_repo(exec_timeout)
        try:
            await self.run_git(["fetch", "origin", base_branch], exec_timeout, WORK_DIR)
            await self.run_git(
                ["checkout", "-B", base_branch, f"origin/{base_branch}"],
                exec_timeout,
                WORK_DIR,
            )
        except RuntimeError as e:
            log.warning("Could not reset to origin/%s: %s", base_branch, e)
            try:
                await self.run_git(["checkout", base_branch], exec_timeout, WORK_DIR)
            except RuntimeError:
                log.warning("Could not checkout %s, using current HEAD", base_branch)
        await self.run_git(["checkout", "-b", branch_name], exec_timeout, WORK_DIR)
        return branch_name

    def get_branch_name(self) -> str:
        """Generate a unique branch name."""
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        short_id = uuid.uuid4().hex[:6]
        return f"autofyn/{date_str}-{short_id}"

    # -- Push / PR --

    async def push_branch(self, branch_name: str, exec_timeout: int) -> None:
        """Push the current branch to origin with retries."""
        await self._retry(
            lambda: self.run_git(
                ["push", "-u", "origin", branch_name], exec_timeout, WORK_DIR,
            )
        )

    async def create_pr(
        self, branch_name: str, run_id: str, base_branch: str, exec_timeout: int,
    ) -> str:
        """Create or update a PR. Returns PR URL."""
        title, description = await self._read_agent_pr(exec_timeout)
        if not title:
            title = f"[AutoFyn] {branch_name}"
        footer = f"\n\n---\n**Branch:** `{branch_name}` · **Run:** `{run_id}` · *Generated by AutoFyn*"
        body = (description + footer) if description else footer.lstrip("\n")

        existing_url = await self._find_existing_pr(branch_name, exec_timeout)
        if existing_url:
            await self.run_gh(
                ["pr", "edit", existing_url, "--title", title, "--body", body],
                exec_timeout,
            )
            return existing_url

        return await self._retry(
            lambda: self.run_gh([
                "pr", "create", "--base", base_branch,
                "--head", branch_name, "--title", title, "--body", body,
            ], exec_timeout)
        )

    # -- Diff / Status --

    async def get_branch_diff(
        self, branch_name: str, base_branch: str, exec_timeout: int,
    ) -> list[dict]:
        """Get file-level diff stats between base and branch."""
        await self._ensure_repo(exec_timeout)
        try:
            await self.run_git(
                ["fetch", "origin", base_branch, "--depth", "1"], exec_timeout, WORK_DIR,
            )
            raw = await self.run_git(
                ["diff", "--numstat", f"origin/{base_branch}...{branch_name}"],
                exec_timeout,
                WORK_DIR,
            )
            if not raw.strip():
                return []
            status_raw = await self.run_git(
                ["diff", "--name-status", f"origin/{base_branch}...{branch_name}"],
                exec_timeout,
                WORK_DIR,
            )
            return parse_numstat(raw, parse_name_status(status_raw))
        except (RuntimeError, ValueError) as e:
            log.warning("Failed to get branch diff: %s", e)
            return []

    async def get_branch_diff_live(
        self, base_branch: str, exec_timeout: int,
    ) -> list[dict]:
        """Get diff stats including uncommitted changes."""
        await self._ensure_repo(exec_timeout)
        try:
            await self.run_git(
                ["fetch", "origin", base_branch, "--depth", "1"], exec_timeout, WORK_DIR,
            )
            raw = await self.run_git(
                ["diff", "--numstat", f"origin/{base_branch}...HEAD"],
                exec_timeout,
                WORK_DIR,
            )
            uncommitted = await self.run_git(
                ["diff", "--numstat", "HEAD"], exec_timeout, WORK_DIR,
            )
            all_lines = (raw.strip() + "\n" + uncommitted.strip()).strip()
            if not all_lines:
                return []
            return aggregate_live_diff(all_lines)
        except (RuntimeError, ValueError) as e:
            log.warning("Failed to get live diff: %s", e)
            return []

    async def has_changes(self, exec_timeout: int) -> bool:
        """Check if there are any uncommitted or staged changes."""
        await self._ensure_repo(exec_timeout)
        output = await self.run_git(["status", "--porcelain"], exec_timeout, WORK_DIR)
        return bool(output.strip())

    # -- Resume --

    async def checkout_branch(
        self, branch_name: str, base_branch: str, exec_timeout: int,
    ) -> None:
        """Checkout an existing branch for resume."""
        try:
            await self.run_git(["fetch", "origin", branch_name], exec_timeout, WORK_DIR)
            await self.run_git(["checkout", branch_name], exec_timeout, WORK_DIR)
            await self.run_git(["pull", "origin", branch_name], exec_timeout, WORK_DIR)
        except RuntimeError as e:
            log.warning("Could not fetch/checkout %s: %s — trying local", branch_name, e)
            try:
                await self.run_git(["checkout", branch_name], exec_timeout, WORK_DIR)
            except RuntimeError as e2:
                log.warning("Local checkout failed: %s — creating fresh branch", e2)
                await self.create_branch(branch_name, base_branch, exec_timeout)

    # -- Private --

    async def _exec(
        self, args: list[str], cwd: str, timeout: int, env: dict[str, str],
    ) -> ExecResult:
        """Execute a command via sandbox."""
        request = ExecRequest(args=args, cwd=cwd, timeout=timeout, env=env)
        return await self._client.exec(request)

    def _auth_env(self) -> dict[str, str]:
        """Return env vars for git and gh CLI auth."""
        token = os.environ.get("GIT_TOKEN", "")
        if not token:
            raise RuntimeError("GIT_TOKEN is not set")
        b64 = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        return {
            "GH_TOKEN": token,
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "http.extraHeader",
            "GIT_CONFIG_VALUE_0": f"Authorization: Basic {b64}",
        }

    async def _ensure_repo(self, timeout: int) -> None:
        """Clone the repo in sandbox if not already initialized or repo changed."""
        async with self._init_lock:
            if self._initialized and self._repo == self._cloned_repo:
                return
            token = os.environ.get("GIT_TOKEN", "")
            if not token or not self._repo:
                raise RuntimeError("GIT_TOKEN and repo must be set (call setup_auth first)")

            remote_url = f"https://github.com/{self._repo}.git"
            log.info("Cloning %s in sandbox...", self._repo)

            await self._exec(["rm", "-rf", WORK_DIR], "/", timeout, {})
            await self._exec(["mkdir", "-p", WORK_DIR], "/", timeout, {})
            result = await self._exec(
                ["git", "clone", "--depth", "50", "--no-single-branch", remote_url, "."],
                WORK_DIR, timeout, self._auth_env(),
            )
            if result.exit_code != 0:
                raise RuntimeError(f"Clone failed: {result.stderr}")
            self._cloned_repo = self._repo
            self._initialized = True

    async def _retry(
        self, fn: Callable[[], Coroutine[Any, Any, str]],
    ) -> str:
        """Retry an async operation with exponential backoff."""
        last_error: RuntimeError = RuntimeError("_retry: no attempts")
        for attempt in range(GIT_RETRY_ATTEMPTS):
            try:
                return await fn()
            except RuntimeError as e:
                last_error = e
                if attempt < GIT_RETRY_ATTEMPTS - 1:
                    wait = GIT_RETRY_DELAY_SEC * (2 ** attempt)
                    log.info("Retry %d/%d after %.0fs: %s", attempt + 1, GIT_RETRY_ATTEMPTS - 1, wait, e)
                    await asyncio.sleep(wait)
        raise last_error

    async def _find_existing_pr(self, branch_name: str, timeout: int) -> str | None:
        """Find an open PR for this branch. Returns URL or None."""
        try:
            url = await self.run_gh(
                ["pr", "view", branch_name, "--json", "url", "-q", ".url"], timeout,
            )
            return url.strip() if url.strip() else None
        except RuntimeError as e:
            log.debug("No existing PR for %s: %s", branch_name, e)
            return None

    async def _read_agent_pr(self, timeout: int) -> tuple[str | None, str | None]:
        """Read /tmp/pr.json written by the agent in sandbox."""
        result = await self._exec(["cat", "/tmp/pr.json"], "/tmp", timeout, {})
        if result.exit_code != 0:
            return None, None
        try:
            data = json.loads(result.stdout)
            await self._exec(["rm", "-f", "/tmp/pr.json"], "/tmp", timeout, {})
            return data.get("title"), data.get("description")
        except (json.JSONDecodeError, KeyError) as e:
            log.warning("Failed to parse /tmp/pr.json: %s", e)
            return None, None
