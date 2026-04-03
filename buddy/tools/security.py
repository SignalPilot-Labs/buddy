"""Security gating: enforces all tool access controls.

SecurityGate is instantiated per-run with a RunContext and passed to
the SDK as the can_use_tool callback. All checks are instance methods
chained via short-circuit or.
"""

import os
import re

from claude_agent_sdk.types import (
    PermissionResultAllow,
    PermissionResultDeny,
    ToolPermissionContext,
)

from utils import db
from utils.constants import (
    ALLOWED_PATHS,
    ALLOWED_SYSTEM_PATHS,
    CREDENTIAL_PATTERNS,
    DANGEROUS_PATTERNS,
    INPUT_SUMMARY_LIMIT,
    PROTECTED_BRANCHES,
    SECRET_ENV_VARS,
)
from utils.models import RunContext
from utils.helpers import summarize_input


class SecurityGate:
    """Permission callback that enforces all access controls.

    Rules:
    1. Block reads/writes to credential files
    2. Block git push to any repo other than GITHUB_REPO
    3. Block push to protected branches
    4. Confine file operations to allowed paths
    5. Block dangerous commands
    6. Audit every decision
    """

    def __init__(self, ctx: RunContext):
        self._ctx = ctx
        self._cred_re = re.compile("|".join(CREDENTIAL_PATTERNS), re.IGNORECASE)
        self._dangerous_re = re.compile("|".join(DANGEROUS_PATTERNS))

    async def check_permission(
        self, tool_name: str, input_data: dict, context: ToolPermissionContext,
    ) -> PermissionResultAllow | PermissionResultDeny:
        """Main callback — every tool call passes through here."""
        deny_reason = self._check(tool_name, input_data)

        await db.log_audit(self._ctx.run_id, "permission_denied" if deny_reason else "permission_allowed", {
            "tool_name": tool_name,
            "input_summary": summarize_input(input_data, INPUT_SUMMARY_LIMIT),
            "deny_reason": deny_reason,
        })

        if deny_reason:
            return PermissionResultDeny(message=deny_reason)
        return PermissionResultAllow(updated_input=input_data)

    # ── Dispatch ──

    def _check(self, tool_name: str, input_data: dict) -> str | None:
        """Run all checks for a tool call. Returns deny reason or None."""
        if tool_name in ("Read", "Write", "Edit", "Glob", "Grep"):
            return self._check_file_tool(input_data)
        if tool_name == "Bash":
            return self._check_bash(input_data.get("command", ""))
        return None

    # ── File Checks ──

    def _check_file_tool(self, input_data: dict) -> str | None:
        """Check file operation tools for credential access and path confinement."""
        path = input_data.get("file_path") or input_data.get("path")
        if not path:
            return None
        if self._cred_re.search(path):
            return f"Access to credential file '{path}' is blocked"
        norm = os.path.normpath(path)
        if not any(norm.startswith(p) for p in ALLOWED_PATHS):
            return f"Path '{path}' is outside allowed directories — operations are confined to the repo"
        return None

    # ── Bash Checks (chained via short-circuit or) ──

    def _check_bash(self, cmd: str) -> str | None:
        """Run all bash command checks in priority order."""
        return (
            self._check_token_exposure(cmd)
            or self._check_dangerous(cmd)
            or self._check_git_branch_creation(cmd)
            or self._check_git_push(cmd)
            or self._check_repo_exploration(cmd)
        )

    def _check_token_exposure(self, cmd: str) -> str | None:
        """Block commands that would print or expose tokens/secrets."""
        patterns = [
            rf"echo\s+.*\$\{{?({SECRET_ENV_VARS})",
            r"cat\s+.*\.env",
            rf"printenv\s+({SECRET_ENV_VARS})",
            r"printenv\s*$", r"\benv\s*$", r"\bset\s*$", r"\bexport\s*$",
        ]
        for pattern in patterns:
            if re.search(pattern, cmd):
                return "Blocked command that would expose credentials"
        return None

    def _check_dangerous(self, cmd: str) -> str | None:
        """Check for destructive system commands."""
        if self._dangerous_re.search(cmd):
            return "Blocked dangerous system command"
        return None

    def _check_git_branch_creation(self, cmd: str) -> str | None:
        """Block git branch creation/switching and git clean."""
        if re.search(r"git\s+checkout\s+-b\b", cmd):
            return "Cannot create branches — the system manages branching"
        if re.search(r"git\s+switch\s+-c\b", cmd):
            return "Cannot create branches — the system manages branching"
        if re.search(r"git\s+branch\s+(?!-[dD])\S", cmd):
            return "Cannot create branches — the system manages branching"
        if re.search(r"git\s+switch\s+(?!-)\S", cmd):
            return "Cannot switch branches — stay on the current branch"
        # git checkout <branch> (but allow git checkout -- <file>)
        if re.search(r"git\s+checkout\s+(?!-)\S", cmd) and "--" not in cmd:
            return "Cannot switch branches — use 'git checkout -- <file>' to revert files"
        if re.search(r"git\s+clean\s+-[a-zA-Z]*f", cmd):
            return "git clean -f is blocked — it deletes untracked files permanently"
        return None

    def _check_git_push(self, cmd: str) -> str | None:
        """Check git push/remote commands for repo and branch violations."""
        if "git remote" in cmd:
            repo = os.environ.get("GITHUB_REPO", "")
            if repo and repo not in cmd:
                return f"Cannot modify git remotes — only {repo} is allowed"

        if "git push" not in cmd:
            return None

        for branch in PROTECTED_BRANCHES:
            if re.search(rf"git\s+push\s+.*\b{branch}\b", cmd):
                return f"Cannot push directly to protected branch '{branch}' — create a PR instead"

        if re.search(r"git\s+push\s+.*(-f|--force)", cmd):
            return "Force push is not allowed"
        return None

    def _check_repo_exploration(self, cmd: str) -> str | None:
        """Block commands that try to clone or explore other repos."""
        if "git clone" in cmd:
            repo = os.environ.get("GITHUB_REPO", "")
            if repo and repo not in cmd:
                return f"Cannot clone other repositories — stay within {repo}"
            if not repo:
                return "Cannot clone repositories — GITHUB_REPO not configured"

        cd_match = re.search(r"cd\s+([^\s;&|]+)", cmd)
        if cd_match:
            target = cd_match.group(1)
            if target.startswith("/") and not target.startswith("/workspace"):
                if not any(target.startswith(p) for p in ALLOWED_SYSTEM_PATHS):
                    return f"Cannot cd to '{target}' — operations confined to /workspace"
        return None


