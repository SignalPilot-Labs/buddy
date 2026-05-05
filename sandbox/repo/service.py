"""RepoService — all git/gh operations for the sandbox repo lifecycle.

One instance per sandbox, stored on the aiohttp app. Endpoints call
public methods; the service owns git state (RepoState) and all
subprocess interactions via shared.subprocess helpers.

Lifecycle: bootstrap → (save per round) → teardown.
"""

import logging
import os

from aiohttp import web

from constants import (
    AUTO_COMMIT_MESSAGE,
    CLONE_TMP_DIR,
    CMD_TIMEOUT,
    GIT_CLONE_DEPTH,
    REPO_BRANCH_NAME_MAX_LEN,
    REPO_BRANCH_NAME_PATTERN,
    REPO_WORK_DIR,
    STDERR_BRIEF_LIMIT,
    STDERR_SHORT_LIMIT,
)
from models import RepoState
from repo.parsers import parse_name_status, parse_numstat
from shared.subprocess import fail, gh, git, run_cmd, scrub_secrets

log = logging.getLogger("sandbox.repo.service")

_GIT_TOKEN_KEY: str = "GIT_TOKEN"


class RepoService:
    """Manages the full git lifecycle for one sandbox run.

    Public API:
        bootstrap(body)      → RepoState
        save(message)        → dict
        teardown(body)       → dict
        diff()               → str
        diff_stats()         → list[dict]
    """

    def __init__(self) -> None:
        """Initialize with no repo state (set by bootstrap)."""
        self._state: RepoState | None = None

    @property
    def state(self) -> RepoState:
        """Return repo state. Fails fast if not bootstrapped."""
        if self._state is None:
            raise web.HTTPConflict(
                reason="repo not bootstrapped — call /repo/bootstrap first",
            )
        return self._state

    # ── Bootstrap ─────────────────────────────────────────────────────

    async def bootstrap(self, body: dict) -> RepoState:
        """Clone the repo, verify base branch, create working branch.

        GIT_TOKEN must be in os.environ (injected via POST /env).
        """
        repo, base_branch, working_branch = self._parse_bootstrap(body)

        if not os.environ.get(_GIT_TOKEN_KEY):
            raise web.HTTPBadRequest(
                reason="GIT_TOKEN not set — call POST /env before bootstrap",
            )

        await self._clone(repo)
        base_sha = await self._setup_base_branch(base_branch)
        await self._setup_working_branch(working_branch)

        self._state = RepoState(
            repo=repo,
            base_branch=base_branch,
            working_branch=working_branch,
            base_sha=base_sha,
        )
        return self._state

    # ── Save (per-round commit + push) ────────────────────────────────

    async def save(self, message: str) -> dict:
        """Commit + push. No-op if the working tree is clean."""
        await self._require_on_working_branch()

        if not await self._has_changes():
            return {"committed": False, "pushed": False, "push_error": None}

        committed = await self._commit(message)
        if not committed:
            return {"committed": False, "pushed": False, "push_error": None}

        push_error = await self._push()
        return {
            "committed": True,
            "pushed": push_error is None,
            "push_error": push_error,
        }

    # ── Teardown (end-of-run commit + push + PR + diff) ───────────────

    async def teardown(self, body: dict) -> dict:
        """Commit leftovers, push, create/update PR, capture diff."""
        pr_title: str = body["pr_title"]
        pr_description: str = body["pr_description"]
        base: str = body["base"]
        self._validate_branch(base)

        await self._require_on_working_branch()

        auto_committed = False
        if await self._has_changes():
            auto_committed = await self._commit(AUTO_COMMIT_MESSAGE)

        ahead = await self._commits_ahead(base)
        if ahead == 0:
            diff = await self._branch_diff()
            return self._teardown_response(
                auto_committed, 0, False, None, None, None, diff,
            )

        push_error = await self._push()
        if push_error is not None:
            diff = await self._branch_diff()
            return self._teardown_response(
                auto_committed, ahead, False, push_error, None, None, diff,
            )

        pr_url, pr_error = await self._create_or_update_pr(
            pr_title, pr_description, base,
        )
        diff = await self._branch_diff()
        return self._teardown_response(
            auto_committed, ahead, True, None, pr_url, pr_error, diff,
        )

    # ── Diff ──────────────────────────────────────────────────────────

    async def diff(self) -> str:
        """Full unified diff of working tree against base."""
        s = self.state
        result = await git(["diff", s.base_sha], CMD_TIMEOUT, cwd=REPO_WORK_DIR)
        if result.exit_code != 0:
            detail = scrub_secrets(result.stderr)[:STDERR_SHORT_LIMIT]
            raise web.HTTPInternalServerError(
                text=f'{{"error": "git diff failed", "detail": "{detail}"}}',
                content_type="application/json",
            )
        return result.stdout

    async def diff_stats(self) -> list[dict]:
        """Per-file diff stats including uncommitted working tree changes."""
        s = self.state
        return await self._worktree_diff(s.base_sha)

    # ── Private: bootstrap helpers ────────────────────────────────────

    def _parse_bootstrap(self, body: dict) -> tuple[str, str, str]:
        """Extract and validate bootstrap request fields."""
        repo: str = body["repo"]
        base_branch: str = body["base_branch"]
        working_branch: str = body["working_branch"]

        if "/" not in repo:
            raise web.HTTPBadRequest(reason="repo must be owner/name")
        self._validate_branch(base_branch)
        self._validate_branch(working_branch)

        return repo, base_branch, working_branch

    async def _clone(self, repo: str) -> None:
        """Clone repo via temp dir + rsync to handle bind mount conflicts."""
        await run_cmd(["rm", "-rf", CLONE_TMP_DIR], "/", CMD_TIMEOUT)
        await run_cmd(["mkdir", "-p", CLONE_TMP_DIR], "/", CMD_TIMEOUT)
        await run_cmd(["rm", "-rf", REPO_WORK_DIR], "/", CMD_TIMEOUT)
        await run_cmd(["mkdir", "-p", REPO_WORK_DIR], "/", CMD_TIMEOUT)

        remote_url = f"https://github.com/{repo}.git"
        fail(
            await git(
                ["clone", "--depth", str(GIT_CLONE_DEPTH), "--no-single-branch",
                 remote_url, "."],
                CMD_TIMEOUT,
                cwd=CLONE_TMP_DIR,
            ),
            "git clone",
        )

        mount_entries = await run_cmd(["ls", "-A", REPO_WORK_DIR], "/", CMD_TIMEOUT)
        excludes = [
            name.strip()
            for name in mount_entries.stdout.strip().split("\n")
            if name.strip()
        ]
        rsync_cmd = ["rsync", "-a"]
        for name in excludes:
            log.warning("Host mount shadows repo dir '%s' — using mounted version", name)
            rsync_cmd.append(f"--exclude=/{name}")
        rsync_cmd += [f"{CLONE_TMP_DIR}/", f"{REPO_WORK_DIR}/"]
        fail(await run_cmd(rsync_cmd, "/", CMD_TIMEOUT), "rsync clone into repo dir")
        await run_cmd(["rm", "-rf", CLONE_TMP_DIR], "/", CMD_TIMEOUT)

    async def _setup_base_branch(self, base_branch: str) -> str:
        """Verify base exists, fetch, checkout, return frozen base_sha."""
        fail(
            await git(
                ["ls-remote", "--exit-code", "--heads", "origin", base_branch],
                CMD_TIMEOUT,
                cwd=REPO_WORK_DIR,
            ),
            f"base branch '{base_branch}' not found on origin",
        )
        fail(
            await git(["fetch", "origin", base_branch], CMD_TIMEOUT, cwd=REPO_WORK_DIR),
            "git fetch",
        )
        fail(
            await git(
                ["checkout", "-B", base_branch, f"origin/{base_branch}"],
                CMD_TIMEOUT,
                cwd=REPO_WORK_DIR,
            ),
            "git checkout base",
        )
        sha_result = await git(
            ["rev-parse", f"origin/{base_branch}"], CMD_TIMEOUT, cwd=REPO_WORK_DIR,
        )
        fail(sha_result, f"git rev-parse origin/{base_branch}")
        base_sha = sha_result.stdout.strip()
        if not base_sha:
            raise web.HTTPInternalServerError(
                reason=f"git rev-parse origin/{base_branch} returned empty SHA",
            )
        return base_sha

    async def _setup_working_branch(self, working_branch: str) -> None:
        """Check out or create the working branch."""
        ls_result = await git(
            ["ls-remote", "--exit-code", "--heads", "origin", working_branch],
            CMD_TIMEOUT,
            cwd=REPO_WORK_DIR,
        )
        if ls_result.exit_code == 0:
            fail(
                await git(
                    ["fetch", "origin", working_branch], CMD_TIMEOUT, cwd=REPO_WORK_DIR,
                ),
                "git fetch working branch",
            )
            fail(
                await git(
                    ["checkout", "-b", working_branch, f"origin/{working_branch}"],
                    CMD_TIMEOUT,
                    cwd=REPO_WORK_DIR,
                ),
                "git checkout existing branch",
            )
        else:
            fail(
                await git(
                    ["checkout", "-b", working_branch], CMD_TIMEOUT, cwd=REPO_WORK_DIR,
                ),
                "git checkout -b",
            )

    # ── Private: git operations ───────────────────────────────────────

    async def _require_on_working_branch(self) -> None:
        """Refuse if HEAD isn't on the expected working branch."""
        s = self.state
        current = await git(
            ["branch", "--show-current"], CMD_TIMEOUT, cwd=REPO_WORK_DIR,
        )
        head = current.stdout.strip()
        if head != s.working_branch:
            raise web.HTTPConflict(
                reason=f"HEAD is on '{head}', not working branch '{s.working_branch}'",
            )

    async def _has_changes(self) -> bool:
        """True if the working tree has uncommitted or staged changes."""
        result = await git(["status", "--porcelain"], CMD_TIMEOUT, cwd=REPO_WORK_DIR)
        fail(result, "git status")
        return bool(result.stdout.strip())

    async def _commit(self, message: str) -> bool:
        """Stage everything and commit. Returns True on commit, False if clean."""
        fail(await git(["add", "."], CMD_TIMEOUT, cwd=REPO_WORK_DIR), "git add")
        result = await git(["commit", "-m", message], CMD_TIMEOUT, cwd=REPO_WORK_DIR)
        if result.exit_code != 0 and "nothing to commit" in (result.stdout + result.stderr):
            return False
        fail(result, "git commit")
        return True

    async def _push(self) -> str | None:
        """Push working branch. Returns error string on failure, None on success."""
        s = self.state
        result = await git(
            ["push", "-u", "origin", s.working_branch], CMD_TIMEOUT, cwd=REPO_WORK_DIR,
        )
        if result.exit_code != 0:
            err = scrub_secrets(result.stderr.strip())[:STDERR_SHORT_LIMIT]
            log.warning("push failed: %s", err)
            return err
        return None

    async def _commits_ahead(self, base: str) -> int:
        """Count commits between origin/base and HEAD."""
        fail(
            await git(
                ["fetch", "origin", base, "--depth", "1"], CMD_TIMEOUT, cwd=REPO_WORK_DIR,
            ),
            "git fetch base",
        )
        result = await git(
            ["rev-list", "--count", f"origin/{base}..HEAD"], CMD_TIMEOUT, cwd=REPO_WORK_DIR,
        )
        fail(result, "git rev-list")
        count_str = result.stdout.strip()
        lines = count_str.splitlines()
        if not lines:
            raise RuntimeError("git rev-list --count returned empty output")
        count_str = lines[-1].strip()
        if not count_str.isdigit():
            raise RuntimeError(
                f"git rev-list --count returned non-integer output: {count_str!r}"
            )
        return int(count_str)

    async def _branch_diff(self) -> list[dict]:
        """File-level diff stats between working branch and base SHA."""
        s = self.state
        numstat = await git(
            ["diff", "--numstat", s.base_sha, s.working_branch],
            CMD_TIMEOUT,
            cwd=REPO_WORK_DIR,
        )
        if numstat.exit_code != 0 or not numstat.stdout.strip():
            return []
        name_status = await git(
            ["diff", "--name-status", s.base_sha, s.working_branch],
            CMD_TIMEOUT,
            cwd=REPO_WORK_DIR,
        )
        if name_status.exit_code != 0:
            return []
        return parse_numstat(numstat.stdout, parse_name_status(name_status.stdout))

    async def _worktree_diff(self, base_sha: str) -> list[dict]:
        """File-level diff stats including uncommitted working tree changes."""
        numstat = await git(
            ["diff", "--numstat", base_sha], CMD_TIMEOUT, cwd=REPO_WORK_DIR,
        )
        if numstat.exit_code != 0 or not numstat.stdout.strip():
            return []
        name_status = await git(
            ["diff", "--name-status", base_sha], CMD_TIMEOUT, cwd=REPO_WORK_DIR,
        )
        if name_status.exit_code != 0:
            return []
        return parse_numstat(numstat.stdout, parse_name_status(name_status.stdout))

    async def _create_or_update_pr(
        self, title: str, description: str, base: str,
    ) -> tuple[str | None, str | None]:
        """Create a PR, or edit the existing one. Returns (url, error)."""
        s = self.state
        find = await gh(
            ["pr", "view", s.working_branch, "--repo", s.repo,
             "--json", "url", "-q", ".url"],
            CMD_TIMEOUT,
            cwd=REPO_WORK_DIR,
        )
        existing = find.stdout.strip() if find.exit_code == 0 else ""

        if existing:
            edit = await gh(
                ["pr", "edit", existing, "--title", title, "--body", description],
                CMD_TIMEOUT,
                cwd=REPO_WORK_DIR,
            )
            if edit.exit_code != 0:
                err = scrub_secrets(edit.stderr.strip())[:STDERR_BRIEF_LIMIT]
                return existing, f"gh pr edit failed: {err}"
            return existing, None

        create = await gh(
            [
                "pr", "create",
                "--repo", s.repo,
                "--base", base,
                "--head", s.working_branch,
                "--title", title,
                "--body", description,
            ],
            CMD_TIMEOUT,
            cwd=REPO_WORK_DIR,
        )
        if create.exit_code != 0:
            err = scrub_secrets(create.stderr.strip())[:STDERR_BRIEF_LIMIT]
            return None, f"gh pr create failed: {err}"
        return create.stdout.strip(), None

    # ── Private: validation ───────────────────────────────────────────

    def _validate_branch(self, name: str) -> None:
        """Reject branch names with invalid characters."""
        if not name or len(name) > REPO_BRANCH_NAME_MAX_LEN:
            raise web.HTTPBadRequest(reason=f"invalid branch length: {len(name or '')}")
        if not REPO_BRANCH_NAME_PATTERN.match(name):
            raise web.HTTPBadRequest(reason="invalid branch name characters")
        if ".." in name or name.endswith(".lock") or name.endswith("/"):
            raise web.HTTPBadRequest(reason="invalid branch name format")

    def _teardown_response(
        self,
        auto_committed: bool,
        commits_ahead: int,
        pushed: bool,
        push_error: str | None,
        pr_url: str | None,
        pr_error: str | None,
        diff_stats: list[dict],
    ) -> dict:
        """Construct the teardown response dict."""
        return {
            "auto_committed": auto_committed,
            "commits_ahead": commits_ahead,
            "pushed": pushed,
            "push_error": push_error,
            "pr_url": pr_url,
            "pr_error": pr_error,
            "diff_stats": diff_stats,
        }
