"""Git workspace management: clone, branch, push, PR, diff.

GitWorkspace is instantiated once per agent container lifetime. It manages
the cloned repo in WORK_DIR and handles all git/gh CLI interactions.
"""

import base64
import json
import logging
import os
import shutil
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from utils.constants import CLONE_DEPTH, CLONE_TIMEOUT, CMD_TIMEOUT, GIT_RETRY_ATTEMPTS, GIT_RETRY_DELAY_SEC, NPM_INSTALL_TIMEOUT, WORK_DIR
from utils.helpers import validate_branch_name

log = logging.getLogger("agent.git")


class GitWorkspace:
    """Manages the cloned git repo inside the agent container."""

    def __init__(self):
        self._initialized = False
        self._last_repo = ""
        self._auth_in_config = False

    def is_ready(self) -> bool:
        """Check if the repo is cloned and initialized. Safe to call from polling endpoints."""
        return self._initialized

    def _get_repo(self) -> str:
        """Read GITHUB_REPO at call time so runtime changes are picked up."""
        return os.environ.get("GITHUB_REPO", "")

    def _run(self, args: list[str], cwd: str, timeout: int, extra_env: dict[str, str] | None = None) -> str:
        """Run a command and return stdout. Raises on failure."""
        env = os.environ.copy()
        if extra_env:
            env.update(extra_env)
        result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)
        if result.returncode != 0:
            raise RuntimeError(f"{args[0]} failed: {result.stderr.strip()}")
        return result.stdout.strip()

    def _git_auth_env(self) -> dict[str, str]:
        """Return env vars that inject auth via git config environment variables.

        Skipped once auth is written to local git config by setup_auth(),
        to avoid duplicate Authorization headers.
        """
        if self._auth_in_config:
            return {}
        token = os.environ.get("GIT_TOKEN", "")
        if not token:
            return {}
        b64 = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        return {
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "http.extraHeader",
            "GIT_CONFIG_VALUE_0": f"Authorization: Basic {b64}",
        }

    def run_git(self, args: list[str], cwd: str | None = None) -> str:
        """Run a git command in the work directory."""
        return self._run(["git"] + args, cwd=cwd or WORK_DIR, timeout=CMD_TIMEOUT, extra_env=self._git_auth_env())

    def _retry(self, fn) -> str:
        """Retry a git operation with exponential backoff. Uses constants for config."""
        last_error: RuntimeError = RuntimeError("_retry: no attempts")
        for attempt in range(GIT_RETRY_ATTEMPTS):
            try:
                return fn()
            except RuntimeError as e:
                last_error = e
                if attempt < GIT_RETRY_ATTEMPTS - 1:
                    wait = GIT_RETRY_DELAY_SEC * (2 ** attempt)
                    log.info("Retry %d/%d after %.0fs: %s", attempt + 1, GIT_RETRY_ATTEMPTS - 1, wait, e)
                    time.sleep(wait)
        raise last_error

    def _run_gh(self, args: list[str]) -> str:
        """Run a gh CLI command."""
        return self._run(["gh"] + args, cwd=WORK_DIR, timeout=CMD_TIMEOUT)

    def _ensure_repo(self) -> None:
        """Clone or update the repo. Re-clones if GITHUB_REPO changed."""
        repo = self._get_repo()
        token = os.environ.get("GIT_TOKEN", "")
        if not token or not repo:
            raise RuntimeError("GIT_TOKEN and GITHUB_REPO must be set")

        if self._initialized and self._last_repo and self._last_repo != repo:
            log.info("Repo changed from %s to %s — re-cloning", self._last_repo, repo)
            self._initialized = False
            self._auth_in_config = False

        repo_dir = Path(WORK_DIR)
        remote_url = f"https://github.com/{repo}.git"

        if self._initialized and repo_dir.exists() and (repo_dir / ".git").is_dir():
            try:
                self.run_git(["remote", "set-url", "origin", remote_url])
                self.run_git(["fetch", "origin"])
            except RuntimeError as e:
                log.warning("Fetch failed: %s", e)
        else:
            log.info("Cloning %s into %s...", repo, WORK_DIR)
            if repo_dir.exists():
                for item in repo_dir.iterdir():
                    shutil.rmtree(item) if item.is_dir() else item.unlink()
            else:
                repo_dir.mkdir(parents=True)
            self._run(
                ["git", "clone", "--depth", str(CLONE_DEPTH), "--no-single-branch", remote_url, "."],
                cwd=WORK_DIR, timeout=CLONE_TIMEOUT, extra_env=self._git_auth_env(),
            )

        self._last_repo = repo
        self._initialized = True

    def setup_auth(self) -> None:
        """Initialize the repo clone, configure auth, and install dependencies."""
        token = os.environ.get("GIT_TOKEN", "")
        if token and not os.environ.get("GH_TOKEN"):
            os.environ["GH_TOKEN"] = token
        self._ensure_repo()
        # Set auth in local git config so agent Bash git commands can push
        if token:
            b64 = base64.b64encode(f"x-access-token:{token}".encode()).decode()
            self.run_git(["config", "http.extraHeader", f"Authorization: Basic {b64}"])
            self._auth_in_config = True
        self._install_deps()

    def _install_deps(self) -> None:
        """Run npm install in directories that have package.json but no node_modules."""
        work_dir = Path(WORK_DIR)
        for pkg_json in work_dir.rglob("package.json"):
            # Skip nested node_modules
            if "node_modules" in pkg_json.parts:
                continue
            pkg_dir = pkg_json.parent
            if (pkg_dir / "node_modules").exists():
                continue
            log.info("Installing npm deps in %s", pkg_dir)
            try:
                self._run(["npm", "ci"], cwd=str(pkg_dir), timeout=NPM_INSTALL_TIMEOUT)
            except RuntimeError:
                try:
                    self._run(["npm", "install"], cwd=str(pkg_dir), timeout=NPM_INSTALL_TIMEOUT)
                except RuntimeError as e:
                    log.warning("npm install failed in %s: %s", pkg_dir, e)

    def get_branch_name(self) -> str:
        """Generate a unique branch name."""
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        short_id = uuid.uuid4().hex[:6]
        return f"buddy/{date_str}-{short_id}"

    def create_branch(self, branch_name: str, base_branch: str) -> str:
        """Create and checkout a new branch from the base branch."""
        validate_branch_name(branch_name)
        validate_branch_name(base_branch)
        self._ensure_repo()
        try:
            self.run_git(["fetch", "origin", base_branch])
            self.run_git(["checkout", "-B", base_branch, f"origin/{base_branch}"])
        except RuntimeError as e:
            log.warning("Could not reset to origin/%s: %s", base_branch, e)
            try:
                self.run_git(["checkout", base_branch])
            except RuntimeError:
                log.warning("Could not checkout %s, using current HEAD", base_branch)
        self.run_git(["checkout", "-b", branch_name])
        return branch_name

    def ensure_base_branch(self, base_branch: str) -> None:
        """Verify the base branch exists on remote. Bootstrap empty repos."""
        validate_branch_name(base_branch)
        self._ensure_repo()
        try:
            all_refs = self.run_git(["ls-remote", "--heads", "origin"])
        except RuntimeError:
            all_refs = ""

        if not all_refs.strip():
            self._bootstrap_empty_repo(base_branch)
            return
        try:
            self.run_git(["ls-remote", "--exit-code", "--heads", "origin", base_branch])
        except RuntimeError:
            self._create_missing_branch(base_branch)

    def push_branch(self, branch_name: str) -> None:
        """Push the current branch to origin with retries."""
        self._retry(lambda: self.run_git(["push", "-u", "origin", branch_name]))

    def create_pr(self, branch_name: str, run_id: str, base_branch: str) -> str:
        """Create or update a PR. Reads .buddy/pr.json if agent wrote one. Returns PR URL."""
        title, description = self._read_agent_pr()
        if not title:
            title = f"[Buddy] {branch_name}"
        footer = f"\n\n---\n**Branch:** `{branch_name}` · **Run:** `{run_id}` · *Generated by Buddy*"
        body = (description + footer) if description else footer.lstrip("\n")

        existing_url = self._find_existing_pr(branch_name)
        if existing_url:
            self._run_gh(["pr", "edit", existing_url, "--title", title, "--body", body])
            return existing_url

        return self._retry(lambda: self._run_gh([
            "pr", "create", "--base", base_branch,
            "--head", branch_name, "--title", title, "--body", body,
        ]))

    def _find_existing_pr(self, branch_name: str) -> str | None:
        """Find an open PR for this branch. Returns URL or None."""
        try:
            url = self._run_gh(["pr", "view", branch_name, "--json", "url", "-q", ".url"])
            return url.strip() if url.strip() else None
        except (RuntimeError, OSError) as e:
            log.debug("No existing PR for %s: %s", branch_name, e)
            return None

    def _read_agent_pr(self) -> tuple[str | None, str | None]:
        """Read and delete /tmp/pr.json written by the agent. Returns (title, description)."""
        pr_file = Path("/tmp/pr.json")
        if not pr_file.exists():
            return None, None
        try:
            data = json.loads(pr_file.read_text())
            pr_file.unlink()
            return data.get("title"), data.get("description")
        except (json.JSONDecodeError, OSError, KeyError) as e:
            log.warning("Failed to read /tmp/pr.json: %s", e)
            return None, None

    def get_branch_diff(self, branch_name: str, base_branch: str) -> list[dict]:
        """Get file-level diff stats between base and branch."""
        self._ensure_repo()
        try:
            self.run_git(["fetch", "origin", base_branch, "--depth", "1"])
            raw = self.run_git(["diff", "--numstat", f"origin/{base_branch}...{branch_name}"])
            if not raw.strip():
                return []
            status_raw = self.run_git(["diff", "--name-status", f"origin/{base_branch}...{branch_name}"])
            return _parse_numstat(raw, _parse_name_status(status_raw))
        except (RuntimeError, OSError, ValueError) as e:
            log.warning("Failed to get branch diff: %s", e)
            return []

    def get_branch_diff_live(self, base_branch: str) -> list[dict]:
        """Get diff stats including uncommitted changes."""
        self._ensure_repo()
        try:
            self.run_git(["fetch", "origin", base_branch, "--depth", "1"])
            raw = self.run_git(["diff", "--numstat", f"origin/{base_branch}...HEAD"])
            uncommitted = self.run_git(["diff", "--numstat", "HEAD"])
            all_lines = (raw.strip() + "\n" + uncommitted.strip()).strip()
            if not all_lines:
                return []
            return _aggregate_live_diff(all_lines)
        except (RuntimeError, OSError, ValueError) as e:
            log.warning("Failed to get live diff: %s", e)
            return []

    def has_changes(self) -> bool:
        """Check if there are any uncommitted or staged changes."""
        self._ensure_repo()
        return bool(self.run_git(["status", "--porcelain"]).strip())

    def get_current_branch(self) -> str:
        """Get the current branch name."""
        self._ensure_repo()
        return self.run_git(["branch", "--show-current"])

    def get_work_dir(self) -> str:
        """Return the working directory."""
        self._ensure_repo()
        return WORK_DIR

    def _bootstrap_empty_repo(self, base_branch: str) -> None:
        """Initialize an empty remote with main + staging branches."""
        try:
            self.run_git(["checkout", "--orphan", "main"])
            self.run_git(["commit", "--allow-empty", "-m", "Initialize repository"])
            self.run_git(["push", "-u", "origin", "main"])
            self.run_git(["checkout", "-b", "staging"])
            self.run_git(["push", "-u", "origin", "staging"])
            if base_branch not in ("main", "staging"):
                self.run_git(["checkout", "-b", base_branch])
                self.run_git(["push", "-u", "origin", base_branch])
            else:
                self.run_git(["checkout", base_branch])
        except RuntimeError as e:
            log.warning("Could not auto-init remote: %s", e)

    def _create_missing_branch(self, base_branch: str) -> None:
        """Create a missing base branch from the default branch."""
        try:
            default = self._get_default_branch()
            self.run_git(["checkout", default])
            self.run_git(["checkout", "-b", base_branch])
            self.run_git(["push", "-u", "origin", base_branch])
        except RuntimeError as e:
            log.warning("Could not create branch '%s': %s", base_branch, e)

    def _get_default_branch(self) -> str:
        """Detect the remote's default branch."""
        try:
            ref = self.run_git(["symbolic-ref", "refs/remotes/origin/HEAD", "--short"])
            return ref.replace("origin/", "")
        except RuntimeError:
            for name in ("main", "master"):
                try:
                    self.run_git(["ls-remote", "--exit-code", "--heads", "origin", name])
                    return name
                except RuntimeError:
                    continue
            return "main"


# ── Pure Helpers (no state) ──

def _parse_name_status(raw: str) -> dict[str, str]:
    """Parse git diff --name-status into a path→status map."""
    result: dict[str, str] = {}
    for line in raw.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            code = parts[0][0]
            result[parts[-1]] = {"A": "added", "M": "modified", "D": "deleted", "R": "renamed"}.get(code, "modified")
    return result


def _parse_numstat(raw: str, status_map: dict[str, str]) -> list[dict]:
    """Parse git diff --numstat into file change dicts."""
    results: list[dict] = []
    for line in raw.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        results.append({
            "path": parts[2],
            "added": int(parts[0]) if parts[0] != "-" else 0,
            "removed": int(parts[1]) if parts[1] != "-" else 0,
            "status": status_map.get(parts[2], "modified"),
        })
    return results


def _aggregate_live_diff(all_lines: str) -> list[dict]:
    """Aggregate numstat lines by path."""
    stats: dict[str, dict] = {}
    for line in all_lines.split("\n"):
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        added = int(parts[0]) if parts[0] != "-" else 0
        removed = int(parts[1]) if parts[1] != "-" else 0
        path = parts[2]
        if path in stats:
            stats[path]["added"] += added
            stats[path]["removed"] += removed
        else:
            stats[path] = {"path": path, "added": added, "removed": removed, "status": "modified"}
    return list(stats.values())
