"""Security gating inside the sandbox container.

SecurityGate enforces minimal access controls. The sandbox is isolated
by gVisor — these rules only protect structural integrity and secrets.

Rules (and why):
1. Branch integrity — orchestrator owns branching, subagents must not switch/create
2. Push integrity — only push to the run's working branch
3. Secret protection — don't leak tokens in stdout (gets logged to DB)
4. Remote/clone protection — stay on configured repo, don't exfiltrate code
5. git clean — protect in-progress work from other subagents
6. Merge integrity — orchestrator owns branch convergence, not subagents
7. GitHub writes — orchestrator owns PR/release/repo writes; reads are fine
8. Secret var refs — block commands that name GIT_TOKEN / GH_TOKEN /
   AGENT_INTERNAL_SECRET, which would enable curl/interpreter exfil
9. /proc/<pid>/environ — block reads; execve snapshot may still contain
   secrets even after os.environ scrub
"""

import logging
import re
import shlex

from constants import CREDENTIAL_PATTERNS, SECRET_ENV_VARS

log = logging.getLogger("sandbox.security")


class SecurityGate:
    """Minimal permission callback for sandbox tool calls.

    Only blocks operations that would break the orchestrator or leak secrets.
    Everything else is allowed — the sandbox is the sandbox, let it rip.
    """

    def __init__(self, github_repo: str, branch_name: str):
        self._github_repo = github_repo
        self._branch_name = branch_name
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
        """Run bash checks. Blocks anything that could leak secrets, mutate
        remote GitHub state, or rewrite branching outside the working branch."""
        return (
            self._check_token_exposure(cmd)
            or self._check_secret_var_refs(cmd)
            or self._check_proc_environ(cmd)
            or self._check_branch_integrity(cmd)
            or self._check_merge(cmd)
            or self._check_push_target(cmd)
            or self._check_remote_and_clone(cmd)
            or self._check_git_config_writes(cmd)
            or self._check_gh_writes(cmd)
            or self._check_github_api_direct(cmd)
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

    def _check_push_target(self, cmd: str) -> str | None:
        """Block pushes to any branch other than the run's working branch."""
        if not re.search(r"git\s+push", cmd):
            return None
        if not self._branch_name:
            return "git push blocked — no working branch configured"
        if ":" in cmd:
            return "Refspec pushes are blocked — use 'git push origin HEAD'"
        if re.search(rf"origin\s+(HEAD|{re.escape(self._branch_name)})(\s|$)", cmd):
            return None
        return f"Can only push to the working branch '{self._branch_name}' — use 'git push origin HEAD'"

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

    def _check_merge(self, cmd: str) -> str | None:
        """Block git merge — the orchestrator owns branch convergence.

        Reads like `git merge-base` / `git merge-tree` / `git merge-file`
        are allowed because they don't mutate refs.
        """
        if re.search(r"\bgit\s+merge\b(?!-)", cmd):
            return "git merge is blocked — the orchestrator handles branch convergence"
        return None

    # Scope flags that appear between `git config` and the config key.
    _GIT_CONFIG_SCOPE_FLAGS = frozenset(
        ("--local", "--global", "--system", "--worktree")
    )

    # Read-only operation flags for git config.
    _GIT_CONFIG_READ_FLAGS = frozenset(
        (
            "--get", "--get-all", "--get-regexp",
            "--list", "-l",
            "--show-origin", "--show-scope",
        )
    )

    # Blocked key patterns (case-insensitive) for git config writes.
    _GIT_CONFIG_BLOCKED_KEY_RES = [
        re.compile(r"\bcredential\.", re.IGNORECASE),
        re.compile(r"\.helper(\s|=|$)", re.IGNORECASE),
        re.compile(r"\bcore\.sshCommand\b", re.IGNORECASE),
        re.compile(r"\burl\.[^\s=]+\.(insteadOf|pushInsteadOf)\b", re.IGNORECASE),
        re.compile(r"\binclude(?:If\.[^\s=]+)?\.path\b", re.IGNORECASE),
    ]

    # Global git flags that may appear between `git` and the subcommand.
    # Flags in the "with value" set consume the next token as their argument.
    _GIT_GLOBAL_FLAGS_WITH_VALUE = frozenset(("-C", "-c", "--namespace", "--work-tree",
                                               "--git-dir", "--exec-path"))
    # Flags in the "no value" set are standalone boolean flags.
    _GIT_GLOBAL_FLAGS_NO_VALUE = frozenset((
        "--bare", "--no-replace-objects", "--no-optional-locks",
        "--literal-pathspecs", "--glob-pathspecs", "--noglob-pathspecs",
        "--icase-pathspecs", "--paginate", "--no-pager",
    ))

    _SHELL_SPLIT_RE = re.compile(r"&&|[;|\n]")

    # Regex to match backtick substitutions `...` (no nesting inside backticks).
    _BACKTICK_RE = re.compile(r"`([^`]*)`")

    # Regex to match a single shell env assignment token (e.g. FOO=bar).
    _ENV_ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

    # Maximum extraction depth for nested subshell bodies.
    _SUBSHELL_MAX_DEPTH = 8

    # env(1) flags that modify environment setup but don't end the prefix.
    # Flags in this set are standalone (consume only the flag token itself).
    _ENV_STANDALONE_FLAGS = frozenset((
        "-", "-i", "-0", "--ignore-environment", "--null",
    ))

    # env(1) flags that consume the *next* token as their argument.
    _ENV_VALUE_FLAGS = frozenset((
        "-u", "--unset", "-S", "--split-string", "-C", "--chdir",
    ))

    # env(1) flags that embed their argument after '=' (--unset=NAME form).
    _ENV_INLINE_VALUE_FLAG_RE = re.compile(
        r"^(--unset=|--split-string=|--chdir=|--block-signal=|--default-signal=)"
    )

    @staticmethod
    def _mask_subshell_bodies(text: str) -> str:
        """Replace $(...) and `...` body contents with whitespace-free placeholders.

        shlex.split has no concept of shell command substitution and splits on
        whitespace inside $(...) and `...` just like anywhere else. This causes
        `FOO=$(echo x) git config ...` to tokenise as:
            ['FOO=$(echo', 'x)', 'git', 'config', ...]
        instead of:
            ['FOO=$(echo x)', 'git', 'config', ...]

        By replacing the body of each substitution with a placeholder that
        contains no whitespace, shlex sees the entire `$(...)` / `` `...` ``
        span as part of a single token, restoring correct env-prefix detection.

        The real subshell bodies are examined independently via
        _extract_subshell_clauses — losing them here is intentional and safe.
        """
        # Replace $(...) bodies (balanced paren walk).
        result: list[str] = []
        i = 0
        n = len(text)
        placeholder_idx = 0
        while i < n:
            if i < n - 1 and text[i] == "$" and text[i + 1] == "(":
                depth = 1
                j = i + 2
                while j < n and depth > 0:
                    if text[j] == "(":
                        depth += 1
                    elif text[j] == ")":
                        depth -= 1
                    j += 1
                if depth == 0:
                    placeholder = f"__SUBSHELL_{placeholder_idx}__"
                    placeholder_idx += 1
                    result.append(f"$({placeholder})")
                    i = j
                    continue
            result.append(text[i])
            i += 1
        masked = "".join(result)

        # Replace `...` bodies (no nesting; simple scan).
        backtick_result: list[str] = []
        in_backtick = False
        for ch in masked:
            if ch == "`":
                if in_backtick:
                    # Close the backtick substitution.
                    placeholder = f"__SUBSHELL_{placeholder_idx}__"
                    placeholder_idx += 1
                    backtick_result.append(f"`{placeholder}`")
                    in_backtick = False
                else:
                    in_backtick = True
            elif in_backtick:
                # Skip body characters — they'll be replaced by the placeholder.
                pass
            else:
                backtick_result.append(ch)

        return "".join(backtick_result)

    @staticmethod
    def _extract_dollar_paren_bodies(text: str) -> list[str]:
        """Extract all $(...) bodies from text using a balanced-paren walker.

        Handles nested $(...) correctly by tracking paren depth. Returns the
        immediate body of each top-level $(...) found. Bodies are not further
        expanded here — that happens via iteration in _extract_subshell_clauses.
        """
        bodies: list[str] = []
        i = 0
        n = len(text)
        while i < n - 1:
            if text[i] == "$" and text[i + 1] == "(":
                # Found a $( — walk forward tracking paren depth.
                depth = 1
                start = i + 2
                j = start
                while j < n and depth > 0:
                    if text[j] == "(":
                        depth += 1
                    elif text[j] == ")":
                        depth -= 1
                    j += 1
                if depth == 0:
                    bodies.append(text[start:j - 1])
                    i = j
                    continue
            i += 1
        return bodies

    def _extract_subshell_clauses(self, clause: str) -> list[str]:
        """Return all $(...) and backtick bodies found in clause, recursively.

        Uses a balanced-paren walker for $(...) so that nested forms like
        $($(git config ...)) and $(echo $(git config ...)) are fully surfaced.
        Backtick bodies are extracted with a simple regex (no nesting in sh).
        Each extracted body is itself examined for further substitutions.
        Capped at _SUBSHELL_MAX_DEPTH iterations.
        """
        seen: set[str] = set()
        pending: list[str] = [clause]
        result: list[str] = []

        for _ in range(self._SUBSHELL_MAX_DEPTH):
            next_pending: list[str] = []
            for item in pending:
                new_bodies = self._extract_dollar_paren_bodies(item)
                for match in self._BACKTICK_RE.finditer(item):
                    new_bodies.append(match.group(1))
                for body in new_bodies:
                    if body not in seen:
                        seen.add(body)
                        result.append(body)
                        next_pending.append(body)
            if not next_pending:
                break
            pending = next_pending

        return result

    def _strip_env_prefix(self, clause: str) -> str:
        """Strip leading shell env assignments and env command with its flags.

        Handles patterns like:
          FOO=bar git config ...
          env FOO=bar git config ...
          FOO=bar BAR=baz git config ...
          env git config ...
          env - FOO=bar git config ...
          env -i git config ...
          env -i FOO=bar git config ...
          env -u HOME FOO=bar git config ...
          env --ignore-environment FOO=bar git config ...
          FOO=$(echo x) git config ...  (subshell in env value)
          FOO=`echo x` git config ...   (backtick in env value)

        Strips repeatedly until neither an assignment nor 'env' (with flags)
        is at the front.

        Pre-masks $(...) and `...` body contents with whitespace-free
        placeholders before shlex tokenisation so that embedded subshells in
        env values (e.g. FOO=$(echo x)) are treated as single tokens rather
        than split on whitespace inside the substitution body.
        """
        masked = self._mask_subshell_bodies(clause)
        try:
            tokens = shlex.split(masked)
        except ValueError:
            return clause

        pos = 0
        while pos < len(tokens):
            token = tokens[pos]
            if self._ENV_ASSIGN_RE.match(token):
                pos += 1
                continue
            if token == "env":
                pos += 1
                # Consume any env flags that follow the 'env' token.
                pos = self._consume_env_flags(tokens, pos)
                continue
            break

        if pos == 0:
            return clause
        # Reconstruct from the remaining tokens.  shlex.join would be ideal but
        # we need to preserve enough quoting for _parse_git_config_clause.
        return " ".join(shlex.quote(t) for t in tokens[pos:])

    def _consume_env_flags(self, tokens: list[str], pos: int) -> int:
        """Consume env(1) flags starting at pos, returning the new position.

        Stops when the current token is neither an env flag nor a KEY=VALUE
        assignment. The caller handles KEY=VALUE tokens in the outer loop.
        """
        while pos < len(tokens):
            token = tokens[pos]
            if token in self._ENV_STANDALONE_FLAGS:
                pos += 1
                continue
            if token in self._ENV_VALUE_FLAGS:
                # Consumes the flag and its value argument.
                pos += 2
                continue
            if self._ENV_INLINE_VALUE_FLAG_RE.match(token):
                pos += 1
                continue
            # Not an env flag; return so the outer loop handles it.
            break
        return pos

    def _check_git_config_writes(self, cmd: str) -> str | None:
        """Block git config writes to credential/helper/sshCommand/url.insteadOf keys.

        Compound commands (&&, ;, |, newline) are split and each clause is
        checked independently so a read flag in one clause cannot mask a write
        in another. Read flags (--get, --list, etc.) are only recognised as
        reads when they appear immediately after `git config` (and any scope
        flags) — not when they appear in the value position or a later clause.
        All key pattern matches are case-insensitive.

        Pre-normalisation before each clause:
        - $(...) and `...` substitution bodies are extracted as independent
          clauses so that wrapped git config writes are not missed. Extraction
          uses a balanced-paren walker to handle nested $(...) forms.
        - Leading shell env assignments (FOO=bar) and 'env' token (including
          its flags: -, -i, --ignore-environment, -u NAME, etc.) are stripped
          so that prefixed forms (env -i FOO=bar git config ...) are parsed.

        Residual bypasses deferred to Round 3 (architectural, defense-in-depth):
        - Interpreter escapes: eval "...", sh -c "...", bash -c "...", python3 -c,
          node -e, perl -e. Gate can't analyse string contents of interpreter args.
        - Process substitution: cat <(git config ...) — distinct from $(...).
        - Git env-var config: GIT_CONFIG_COUNT=/GIT_CONFIG_KEY_0= env var injection.
        - Runtime -c flag on non-config subcommand: git -c credential.helper=x fetch.
        - Direct file write to .git/config: echo/cat/tee writing config file path.
        """
        _DENY = (
            "git config writes to credential/helper/sshCommand/url.insteadOf/include.path"
            " are blocked — they can redirect fetches or exfiltrate tokens"
        )
        raw_clauses = self._SHELL_SPLIT_RE.split(cmd)
        clauses: list[str] = []
        for raw in raw_clauses:
            stripped = raw.strip()
            clauses.append(stripped)
            clauses.extend(self._extract_subshell_clauses(stripped))

        for clause in clauses:
            normalized = self._strip_env_prefix(clause)
            result = self._check_git_config_clause(normalized, _DENY)
            if result is not None:
                return result
        return None

    def _parse_git_config_clause(self, clause: str) -> list[str] | None:
        """Parse a shell clause and return git config arguments, or None.

        Shlex-tokenises the clause, confirms the first token is `git`, walks
        past any global git flags (e.g. -C <path>, -c <k=v>, --work-tree=…),
        and returns the token list starting from the token *after* `config`.

        Returns None when:
        - shlex raises ValueError (malformed shell — fail-closed)
        - the first token is not `git`
        - the first non-global-flag token after `git` is not `config`
        """
        try:
            tokens = shlex.split(clause)
        except ValueError:
            return None

        if not tokens or tokens[0] != "git":
            return None

        pos = 1
        while pos < len(tokens):
            token = tokens[pos]

            # --foo=value form: strip the =value suffix to compare flag name.
            bare_token = token.split("=", 1)[0]

            if bare_token in self._GIT_GLOBAL_FLAGS_WITH_VALUE:
                if "=" in token:
                    # Value is inline (--git-dir=/tmp/.git) — consume only this token.
                    pos += 1
                else:
                    # Value is the next token (-C /path) — consume both.
                    pos += 2
                continue

            if bare_token in self._GIT_GLOBAL_FLAGS_NO_VALUE:
                pos += 1
                continue

            # First non-global-flag token must be `config` for this to be
            # a git config invocation.
            if token != "config":
                return None

            # Return everything after `git [flags...] config`.
            return tokens[pos + 1:]

        return None

    def _check_git_config_clause(self, clause: str, deny_msg: str) -> str | None:
        """Check a single (already-split) shell clause for blocked git config writes."""
        args = self._parse_git_config_clause(clause)
        if args is None:
            return None
        if self._args_are_git_config_read(args):
            return None
        for pattern in self._GIT_CONFIG_BLOCKED_KEY_RES:
            if pattern.search(clause):
                return deny_msg
        return None

    def _args_are_git_config_read(self, args: list[str]) -> bool:
        """Return True iff the git config argument list represents a read operation.

        `args` is the token list *after* `git [global-flags...] config` — i.e.
        the scope flags, read/write operation flags, and key/value tokens.
        """
        pos = 0
        while pos < len(args):
            token = args[pos]
            if token in self._GIT_CONFIG_SCOPE_FLAGS:
                pos += 1
                continue
            if token == "--file":
                pos += 2  # skip --file and its path argument
                continue
            # First non-scope token is the operation or key.
            return token in self._GIT_CONFIG_READ_FLAGS
        return False

    def _clause_is_git_config_read(self, clause: str) -> bool:
        """Return True iff the clause is a git config read operation.

        Delegates to _parse_git_config_clause + _args_are_git_config_read so
        global git flags between `git` and `config` are correctly skipped.
        """
        args = self._parse_git_config_clause(clause)
        if args is None:
            return False
        return self._args_are_git_config_read(args)

    def _check_gh_writes(self, cmd: str) -> str | None:
        """Block `gh` subcommands that mutate GitHub state.

        Read-only commands (`gh pr view`, `gh pr list`, `gh api GET`,
        `gh pr diff`, `gh pr checks`, `gh repo view`) remain allowed —
        subagents may legitimately inspect repo state.
        """
        write_patterns = [
            r"\bgh\s+pr\s+(create|edit|merge|close|reopen|ready|review|comment|lock|unlock)\b",
            r"\bgh\s+release\s+(create|edit|delete|upload|download)\b",
            r"\bgh\s+repo\s+(create|delete|edit|archive|unarchive|rename|fork|clone|sync)\b",
            r"\bgh\s+issue\s+(create|edit|close|reopen|comment|delete|lock|unlock|pin|unpin|transfer)\b",
            r"\bgh\s+workflow\s+(run|enable|disable)\b",
            r"\bgh\s+run\s+(rerun|cancel|delete|watch)\b",
            r"\bgh\s+secret\s+(set|delete|remove)\b",
            r"\bgh\s+variable\s+(set|delete|remove)\b",
            r"\bgh\s+gist\s+(create|edit|delete)\b",
            r"\bgh\s+label\s+(create|edit|delete|clone)\b",
            r"\bgh\s+ruleset\s+(create|edit|delete)\b",
            r"\bgh\s+auth\s+(login|logout|refresh|setup-git|switch|token)\b",
        ]
        for pattern in write_patterns:
            if re.search(pattern, cmd):
                return "gh write commands are blocked — the orchestrator handles GitHub state changes"
        if re.search(r"\bgh\s+api\b", cmd):
            if re.search(r"(-X|--method)\s+(POST|PUT|PATCH|DELETE)\b", cmd, re.IGNORECASE):
                return "gh api write methods (POST/PUT/PATCH/DELETE) are blocked — GET only"
        return None

    def _check_github_api_direct(self, cmd: str) -> str | None:
        """Block direct HTTP clients hitting api.github.com.

        The orchestrator owns all GitHub API writes — a subagent hitting
        api.github.com with curl/wget/httpie would be using the token we
        inject for git auth to bypass `gh` and the `_check_gh_writes` block.
        """
        if re.search(r"\b(curl|wget|http|https|httpie)\b", cmd) and "api.github.com" in cmd:
            return "Direct calls to api.github.com are blocked — the orchestrator handles GitHub API writes"
        return None

    def _check_secret_var_refs(self, cmd: str) -> str | None:
        """Block commands that name our internal secret env vars.

        Catches `curl -H "... $GH_TOKEN"`, `python -c "os.environ['GH_TOKEN']"`,
        `node -e "process.env.GH_TOKEN"`, and similar. The orchestrator owns
        authenticated operations; subagents have no legitimate reason to
        reference these names in a command string.
        """
        for name in ("AGENT_INTERNAL_SECRET", "GH_TOKEN", "GIT_TOKEN"):
            if name in cmd:
                return f"Commands that reference {name} are blocked"
        return None

    def _check_proc_environ(self, cmd: str) -> str | None:
        """Block reads of `/proc/<pid>/environ`.

        Linux freezes each process's env at execve() time in kernel memory;
        Python's `os.environ.pop` doesn't scrub that memory, so the sandbox
        server's original env is still reachable via /proc/1/environ and
        would leak AGENT_INTERNAL_SECRET.
        """
        if re.search(r"/proc/[^/\s]+/environ\b", cmd):
            return "/proc/<pid>/environ is blocked — it can leak credentials"
        return None
