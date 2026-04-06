"""Security gating inside the sandbox container.

SecurityGate enforces minimal access controls. The sandbox is isolated
by gVisor — these rules only protect structural integrity and secrets.

Rules (and why):
1. Branch integrity — orchestrator owns branching, subagents must not switch/create
2. Secret protection — don't leak tokens in stdout (gets logged to DB)
3. Remote/clone protection — stay on configured repo, don't exfiltrate code
4. git clean — protect in-progress work from other subagents
"""

import logging
import re

from constants import CREDENTIAL_PATTERNS, SECRET_ENV_VARS

log = logging.getLogger("sandbox.security")


class SecurityGate:
    """Minimal permission callback for sandbox tool calls.

    Only blocks operations that would break the orchestrator or leak secrets.
    Everything else is allowed — the sandbox is the sandbox, let it rip.
    """

    def __init__(self, github_repo: str):
        self._github_repo = github_repo
        self._cred_re = re.compile("|".join(CREDENTIAL_PATTERNS), re.IGNORECASE)

    def check_permission(
        self, tool_name: str, input_data: dict,
    ) -> str | None:
        """Check a tool call. Returns deny reason or None (allowed)."""
        if tool_name in ("Read", "Write", "Edit", "Glob", "Grep"):
            return self._check_credential_access(input_data)
        if tool_name == "Bash":
            return self._check_bash(input_data.get("command", ""))
        return None

    # ── File Checks ──

    def _check_credential_access(self, input_data: dict) -> str | None:
        """Block access to credential files. No path confinement — sandbox is isolated."""
        path = input_data.get("file_path") or input_data.get("path")
        if not path:
            return None
        if self._cred_re.search(path):
            return f"Access to credential file '{path}' is blocked"
        return None

    # ── Bash Checks ──

    def _check_bash(self, cmd: str) -> str | None:
        """Run bash checks. Only blocks secret leaks, branch ops, and remote ops."""
        return (
            self._check_token_exposure(cmd)
            or self._check_branch_integrity(cmd)
            or self._check_remote_and_clone(cmd)
        )

    def _check_token_exposure(self, cmd: str) -> str | None:
        """Block commands that would print secrets to stdout (gets logged)."""
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

    def _check_branch_integrity(self, cmd: str) -> str | None:
        """Block branch creation/switching/clean. Orchestrator owns branching."""
        if re.search(r"git\s+checkout\s+-b\b", cmd):
            return "Cannot create branches — the system manages branching"
        if re.search(r"git\s+switch\s+-c\b", cmd):
            return "Cannot create branches — the system manages branching"
        if re.search(r"git\s+branch\s+(?!-)\S", cmd):
            return "Cannot create branches — the system manages branching"
        if re.search(r"git\s+switch\s+(?!-)\S", cmd):
            return "Cannot switch branches — stay on the current branch"
        if re.search(r"git\s+checkout\s+(?!-)\S", cmd) and "--" not in cmd and not re.search(r"git\s+checkout\s+\.", cmd):
            return "Cannot switch branches — use 'git checkout -- <file>' to revert files"
        if re.search(r"git\s+clean\s+-[a-zA-Z]*f", cmd):
            return "git clean -f is blocked — it deletes untracked files permanently"
        return None

    def _check_remote_and_clone(self, cmd: str) -> str | None:
        """Block remote modifications and cloning other repos."""
        if "git remote" in cmd:
            if self._github_repo and self._github_repo not in cmd:
                return f"Cannot modify git remotes — only {self._github_repo} is allowed"

        if "git clone" in cmd:
            if self._github_repo and self._github_repo not in cmd:
                return f"Cannot clone other repositories — stay within {self._github_repo}"
            if not self._github_repo:
                return "Cannot clone repositories — repo not configured"

        return None
