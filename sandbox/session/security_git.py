"""Git-config write detection helpers for the sandbox SecurityGate.

Extracted from security.py to stay within the 400-line cap.

Exposes one public function:
    check_git_config_writes(command: str) -> str | None

All parsing helpers are private to this module.
"""

import re
import shlex


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
                placeholder = f"__SUBSHELL_{placeholder_idx}__"
                placeholder_idx += 1
                backtick_result.append(f"`{placeholder}`")
                in_backtick = False
            else:
                in_backtick = True
        elif in_backtick:
            pass
        else:
            backtick_result.append(ch)

    return "".join(backtick_result)


def _extract_dollar_paren_bodies(text: str) -> list[str]:
    """Extract all $(...) bodies from text using a balanced-paren walker."""
    bodies: list[str] = []
    i = 0
    n = len(text)
    while i < n - 1:
        if text[i] == "$" and text[i + 1] == "(":
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


def _extract_subshell_clauses(clause: str) -> list[str]:
    """Return all $(...) and backtick bodies found in clause, recursively."""
    seen: set[str] = set()
    pending: list[str] = [clause]
    result: list[str] = []

    for _ in range(_SUBSHELL_MAX_DEPTH):
        next_pending: list[str] = []
        for item in pending:
            new_bodies = _extract_dollar_paren_bodies(item)
            for match in _BACKTICK_RE.finditer(item):
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


def _consume_env_flags(tokens: list[str], pos: int) -> int:
    """Consume env(1) flags starting at pos, returning the new position."""
    while pos < len(tokens):
        token = tokens[pos]
        if token in _ENV_STANDALONE_FLAGS:
            pos += 1
            continue
        if token in _ENV_VALUE_FLAGS:
            pos += 2
            continue
        if _ENV_INLINE_VALUE_FLAG_RE.match(token):
            pos += 1
            continue
        break
    return pos


def _strip_env_prefix(clause: str) -> str:
    """Strip leading shell env assignments and env command with its flags."""
    masked = _mask_subshell_bodies(clause)
    try:
        tokens = shlex.split(masked)
    except ValueError:
        return clause

    pos = 0
    while pos < len(tokens):
        token = tokens[pos]
        if _ENV_ASSIGN_RE.match(token):
            pos += 1
            continue
        if token == "env":
            pos += 1
            pos = _consume_env_flags(tokens, pos)
            continue
        break

    if pos == 0:
        return clause
    return " ".join(shlex.quote(t) for t in tokens[pos:])


def _args_are_git_config_read(args: list[str]) -> bool:
    """Return True iff the git config argument list represents a read operation."""
    pos = 0
    while pos < len(args):
        token = args[pos]
        if token in _GIT_CONFIG_SCOPE_FLAGS:
            pos += 1
            continue
        if token == "--file":
            pos += 2
            continue
        return token in _GIT_CONFIG_READ_FLAGS
    return False


def _parse_git_config_clause(clause: str) -> list[str] | None:
    """Parse a shell clause and return git config arguments, or None."""
    try:
        tokens = shlex.split(clause)
    except ValueError:
        return None

    if not tokens or tokens[0] != "git":
        return None

    pos = 1
    while pos < len(tokens):
        token = tokens[pos]
        bare_token = token.split("=", 1)[0]

        if bare_token in _GIT_GLOBAL_FLAGS_WITH_VALUE:
            if "=" in token:
                pos += 1
            else:
                pos += 2
            continue

        if bare_token in _GIT_GLOBAL_FLAGS_NO_VALUE:
            pos += 1
            continue

        if token != "config":
            return None

        return tokens[pos + 1:]

    return None


def _check_git_config_clause(clause: str, deny_msg: str) -> str | None:
    """Check a single (already-split) shell clause for blocked git config writes."""
    args = _parse_git_config_clause(clause)
    if args is None:
        return None
    if _args_are_git_config_read(args):
        return None
    for pattern in _GIT_CONFIG_BLOCKED_KEY_RES:
        if pattern.search(clause):
            return deny_msg
    return None


def check_git_config_writes(command: str) -> str | None:
    """Block git config writes to credential/helper/sshCommand/url.insteadOf keys.

    Public entry point. Returns deny reason string or None if allowed.

    Compound commands (&&, ;, |, newline) are split and each clause is
    checked independently so a read flag in one clause cannot mask a write
    in another. Read flags (--get, --list, etc.) are only recognised as
    reads when they appear immediately after `git config` (and any scope
    flags) — not when they appear in the value position or a later clause.

    Residual bypasses: interpreter escapes (eval, sh -c, bash -c, python3 -c,
    node -e, perl -e) are not analysed; architectural env-layer isolation
    (build_git_env F5) is the structural closure for those.
    """
    _DENY = (
        "git config writes to credential/helper/sshCommand/url.insteadOf/include.path"
        " are blocked — they can redirect fetches or exfiltrate tokens"
    )
    raw_clauses = _SHELL_SPLIT_RE.split(command)
    clauses: list[str] = []
    for raw in raw_clauses:
        stripped = raw.strip()
        clauses.append(stripped)
        clauses.extend(_extract_subshell_clauses(stripped))

    for clause in clauses:
        normalized = _strip_env_prefix(clause)
        result = _check_git_config_clause(normalized, _DENY)
        if result is not None:
            return result
    return None
