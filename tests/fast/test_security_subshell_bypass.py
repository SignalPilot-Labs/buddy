"""Regression tests for SecurityGate subshell/wrapper/quoting/interpreter bypasses.

Covers four bypass categories:
  1. Subshell substitution: $(env), `env`, $(printenv), etc.
  2. Shell wrapper: sh -c "env", bash -c 'printenv', etc.
  3. Quote-concatenation obfuscation: e""nv, e''nv, pri""ntenv, etc.
  4. Interpreter env dumps: python3 -c "...os.environ...", node -e "...process.env...", etc.
"""

from sdk.security import SecurityGate


REPO = "owner/test-repo"
BRANCH = "autofyn/2026-04-07-abc123"
DENY_MSG = "credential"


def _make_gate() -> SecurityGate:
    """Build a SecurityGate with standard test config."""
    return SecurityGate(REPO, BRANCH)


class TestSecuritySubshellBypass:
    """Verify subshell/wrapper/quoting/interpreter bypass variants are blocked."""

    # ── Subshell substitution — blocked ──

    def test_blocks_subshell_env_assignment(self) -> None:
        """x=$(env); echo $x must be blocked (subshell env capture)."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "x=$(env); echo $x"})
        assert result is not None
        assert DENY_MSG in result.lower()

    def test_blocks_backtick_env_assignment(self) -> None:
        """x=`env`; echo $x must be blocked (backtick env capture)."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "x=`env`; echo $x"})
        assert result is not None
        assert DENY_MSG in result.lower()

    def test_blocks_subshell_printenv(self) -> None:
        """echo $(printenv) must be blocked (subshell printenv)."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "echo $(printenv)"})
        assert result is not None
        assert DENY_MSG in result.lower()

    def test_blocks_subshell_env(self) -> None:
        """echo $(env) must be blocked (subshell env)."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "echo $(env)"})
        assert result is not None
        assert DENY_MSG in result.lower()

    def test_blocks_backtick_env(self) -> None:
        """echo `env` must be blocked (backtick env)."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "echo `env`"})
        assert result is not None
        assert DENY_MSG in result.lower()

    def test_blocks_subshell_export_dash_p(self) -> None:
        """$(export -p) must be blocked (subshell export -p)."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "$(export -p)"})
        assert result is not None
        assert DENY_MSG in result.lower()

    def test_blocks_backtick_declare_dash_x(self) -> None:
        """`declare -x` must be blocked (backtick declare -x)."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "`declare -x`"})
        assert result is not None
        assert DENY_MSG in result.lower()

    def test_blocks_subshell_env_in_double_quotes(self) -> None:
        """echo "$(env)" must be blocked (subshell inside double quotes)."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": 'echo "$(env)"'})
        assert result is not None
        assert DENY_MSG in result.lower()

    def test_blocks_subshell_env_piped(self) -> None:
        """cat $(env | base64) must be blocked (piped subshell)."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "cat $(env | base64)"})
        assert result is not None
        assert DENY_MSG in result.lower()

    # ── Shell wrapper — blocked ──

    def test_blocks_sh_c_env(self) -> None:
        """sh -c "env" must be blocked (sh -c wrapper)."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": 'sh -c "env"'})
        assert result is not None
        assert DENY_MSG in result.lower()

    def test_blocks_bash_c_printenv(self) -> None:
        """bash -c 'printenv' must be blocked (bash -c wrapper)."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "bash -c 'printenv'"})
        assert result is not None
        assert DENY_MSG in result.lower()

    def test_blocks_sh_c_env_pipe(self) -> None:
        """sh -c 'env | grep TOKEN' must be blocked (sh -c with pipe)."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "sh -c 'env | grep TOKEN'"})
        assert result is not None
        assert DENY_MSG in result.lower()

    def test_blocks_bash_c_export_dash_p(self) -> None:
        """bash -c "export -p" must be blocked (bash -c export -p)."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": 'bash -c "export -p"'})
        assert result is not None
        assert DENY_MSG in result.lower()

    def test_blocks_bash_c_declare_dash_x(self) -> None:
        """bash -c "declare -x" must be blocked (bash -c declare -x)."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": 'bash -c "declare -x"'})
        assert result is not None
        assert DENY_MSG in result.lower()

    # ── Quote-concatenation obfuscation — blocked ──

    def test_blocks_quote_concat_env_double(self) -> None:
        """e""nv must be blocked (double-quote concatenation bypass)."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": 'e""nv'})
        assert result is not None
        assert DENY_MSG in result.lower()

    def test_blocks_quote_concat_env_single(self) -> None:
        """e''nv must be blocked (single-quote concatenation bypass)."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "e''nv"})
        assert result is not None
        assert DENY_MSG in result.lower()

    def test_blocks_quote_concat_printenv_double(self) -> None:
        """pri""ntenv must be blocked (double-quote printenv bypass)."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": 'pri""ntenv'})
        assert result is not None
        assert DENY_MSG in result.lower()

    def test_blocks_quote_concat_printenv_single(self) -> None:
        """pri''ntenv must be blocked (single-quote printenv bypass)."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "pri''ntenv"})
        assert result is not None
        assert DENY_MSG in result.lower()

    # ── Interpreter env dumps — blocked ──

    def test_blocks_python3_os_environ_dict(self) -> None:
        """python3 -c "import os; print(dict(os.environ))" must be blocked."""
        gate = _make_gate()
        result = gate.check_permission(
            "Bash",
            {"command": 'python3 -c "import os; print(dict(os.environ))"'},
        )
        assert result is not None
        assert DENY_MSG in result.lower()

    def test_blocks_node_process_env(self) -> None:
        """node -e "console.log(process.env)" must be blocked."""
        gate = _make_gate()
        result = gate.check_permission(
            "Bash",
            {"command": 'node -e "console.log(process.env)"'},
        )
        assert result is not None
        assert DENY_MSG in result.lower()

    def test_blocks_ruby_env_to_h(self) -> None:
        """ruby -e "puts ENV.to_h" must be blocked."""
        gate = _make_gate()
        result = gate.check_permission(
            "Bash",
            {"command": "ruby -e \"puts ENV.to_h\""},
        )
        assert result is not None
        assert DENY_MSG in result.lower()

    def test_blocks_perl_percent_env(self) -> None:
        """perl -e "print %ENV" must be blocked."""
        gate = _make_gate()
        result = gate.check_permission(
            "Bash",
            {"command": 'perl -e "print %ENV"'},
        )
        assert result is not None
        assert DENY_MSG in result.lower()

    def test_blocks_python_os_environ_print(self) -> None:
        """python -c "import os; print(os.environ)" must be blocked."""
        gate = _make_gate()
        result = gate.check_permission(
            "Bash",
            {"command": 'python -c "import os; print(os.environ)"'},
        )
        assert result is not None
        assert DENY_MSG in result.lower()

    # ── Allowed commands ──

    def test_allows_env_with_flag(self) -> None:
        """env -i bash must be allowed (legitimate env usage with flag)."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "env -i bash"})
        assert result is None

    def test_allows_env_var_assignment(self) -> None:
        """env VAR=val command must be allowed (setting env for subprocess)."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "env VAR=val command"})
        assert result is None

    def test_allows_printenv_specific_var(self) -> None:
        """printenv HOME must be allowed (non-secret variable)."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "printenv HOME"})
        assert result is None

    def test_allows_source_venv(self) -> None:
        """source venv/bin/activate must be allowed (env substring in path)."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "source venv/bin/activate"})
        assert result is None

    def test_allows_node_env_var_assignment(self) -> None:
        """NODE_ENV=production npm start must be allowed (env in variable name)."""
        gate = _make_gate()
        result = gate.check_permission(
            "Bash", {"command": "NODE_ENV=production npm start"}
        )
        assert result is None

    def test_allows_bash_c_node_env_var(self) -> None:
        """bash -c "NODE_ENV=production npm start" must be allowed (env substring in var name inside sh -c)."""
        gate = _make_gate()
        result = gate.check_permission(
            "Bash", {"command": 'bash -c "NODE_ENV=production npm start"'}
        )
        assert result is None

    def test_allows_bash_c_set_option(self) -> None:
        """bash -c "set -e; npm install" must be allowed (set with flag, not env dump)."""
        gate = _make_gate()
        result = gate.check_permission(
            "Bash", {"command": 'bash -c "set -e; npm install"'}
        )
        assert result is None

    def test_allows_set_pipefail(self) -> None:
        """set -o pipefail must be allowed (shell option, not env dump)."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "set -o pipefail"})
        assert result is None

    def test_allows_python3_script(self) -> None:
        """python3 script.py must be allowed (no inline code)."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "python3 script.py"})
        assert result is None

    def test_allows_node_script(self) -> None:
        """node server.js must be allowed (no inline code)."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "node server.js"})
        assert result is None

    def test_allows_python3_inline_no_env(self) -> None:
        """python3 -c "print('hello')" must be allowed (no env access)."""
        gate = _make_gate()
        result = gate.check_permission(
            "Bash", {"command": "python3 -c \"print('hello')\""}
        )
        assert result is None

    def test_allows_echo_redirect_no_env(self) -> None:
        """echo "" > /tmp/file must be allowed (empty string, not env-dump after stripping)."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": 'echo "" > /tmp/file'})
        assert result is None

    def test_allows_python3_getenv_single_var(self) -> None:
        """python3 -c "import os; print(os.getenv('HOME'))" must be allowed (single-var lookup)."""
        gate = _make_gate()
        result = gate.check_permission(
            "Bash",
            {"command": "python3 -c \"import os; print(os.getenv('HOME'))\""},
        )
        assert result is None

    def test_allows_ruby_env_single_var(self) -> None:
        """ruby -e "puts ENV['HOME']" must be allowed (single-var lookup, not full dump)."""
        gate = _make_gate()
        result = gate.check_permission(
            "Bash",
            {"command": "ruby -e \"puts ENV['HOME']\""},
        )
        assert result is None

    # ── V1: env/printenv with null-separator flags — blocked ──

    def test_blocks_env_dash_0(self) -> None:
        """env -0 must be blocked (null-separated full env dump)."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "env -0"})
        assert result is not None
        assert DENY_MSG in result.lower()

    def test_blocks_env_dash_dash_null(self) -> None:
        """env --null must be blocked (null-separated full env dump)."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "env --null"})
        assert result is not None
        assert DENY_MSG in result.lower()

    def test_blocks_env_dash_0_piped(self) -> None:
        """env -0 | cat must be blocked (null-separated env dump piped)."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "env -0 | cat"})
        assert result is not None
        assert DENY_MSG in result.lower()

    def test_blocks_printenv_dash_0(self) -> None:
        """printenv -0 must be blocked (null-separated full env dump)."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "printenv -0"})
        assert result is not None
        assert DENY_MSG in result.lower()

    def test_blocks_printenv_dash_dash_null(self) -> None:
        """printenv --null must be blocked (null-separated full env dump)."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "printenv --null"})
        assert result is not None
        assert DENY_MSG in result.lower()

    # ── V2: Quote-concatenation covers all checks — blocked ──

    def test_blocks_quote_concat_subshell_env(self) -> None:
        """$(e""nv) must be blocked (quote-concat in subshell)."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": '$(e""nv)'})
        assert result is not None
        assert DENY_MSG in result.lower()

    def test_blocks_quote_concat_shell_wrapper_env(self) -> None:
        """sh -c "e""nv" must be blocked (quote-concat in shell wrapper)."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": 'sh -c "e""nv"'})
        assert result is not None
        assert DENY_MSG in result.lower()

    def test_blocks_quote_concat_python_environ(self) -> None:
        """python3 -c "import os; print(os.envir""on)" must be blocked (quote-concat in interpreter)."""
        gate = _make_gate()
        result = gate.check_permission(
            "Bash",
            {"command": 'python3 -c "import os; print(os.envir""on)"'},
        )
        assert result is not None
        assert DENY_MSG in result.lower()

    # ── V3: Process substitution — blocked ──

    def test_blocks_process_substitution_env(self) -> None:
        """cat <(env) must be blocked (process substitution env dump)."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "cat <(env)"})
        assert result is not None
        assert DENY_MSG in result.lower()

    def test_blocks_process_substitution_printenv(self) -> None:
        """cat <(printenv) must be blocked (process substitution printenv dump)."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "cat <(printenv)"})
        assert result is not None
        assert DENY_MSG in result.lower()

    # ── V4: Python environ without os. prefix — blocked ──

    def test_blocks_python_from_os_import_environ(self) -> None:
        """python3 -c "from os import environ; print(environ)" must be blocked."""
        gate = _make_gate()
        result = gate.check_permission(
            "Bash",
            {"command": 'python3 -c "from os import environ; print(environ)"'},
        )
        assert result is not None
        assert DENY_MSG in result.lower()

    def test_blocks_python_import_os_environ_word(self) -> None:
        """python -c "print(__import__('os').environ)" must be blocked (environ word)."""
        gate = _make_gate()
        result = gate.check_permission(
            "Bash",
            {"command": "python -c \"print(__import__('os').environ)\""},
        )
        assert result is not None
        assert DENY_MSG in result.lower()

    # ── V5: Additional shells — blocked ──

    def test_blocks_zsh_c_env(self) -> None:
        """zsh -c "env" must be blocked (zsh shell wrapper)."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": 'zsh -c "env"'})
        assert result is not None
        assert DENY_MSG in result.lower()

    def test_blocks_dash_c_env(self) -> None:
        """dash -c "env" must be blocked (dash shell wrapper)."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": 'dash -c "env"'})
        assert result is not None
        assert DENY_MSG in result.lower()

    def test_blocks_ksh_c_printenv(self) -> None:
        """ksh -c 'printenv' must be blocked (ksh shell wrapper)."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "ksh -c 'printenv'"})
        assert result is not None
        assert DENY_MSG in result.lower()

    # ── V6: node --eval and long flags for other interpreters — blocked ──

    def test_blocks_node_eval_long_flag(self) -> None:
        """node --eval "console.log(process.env)" must be blocked (long flag form)."""
        gate = _make_gate()
        result = gate.check_permission(
            "Bash",
            {"command": 'node --eval "console.log(process.env)"'},
        )
        assert result is not None
        assert DENY_MSG in result.lower()

    def test_blocks_perl_eval_long_flag(self) -> None:
        """perl --eval "print %ENV" must be blocked (long flag form)."""
        gate = _make_gate()
        result = gate.check_permission(
            "Bash",
            {"command": 'perl --eval "print %ENV"'},
        )
        assert result is not None
        assert DENY_MSG in result.lower()

    # ── V1: Allowed (env with legitimate flags) ──

    def test_allows_env_dash_i_bash(self) -> None:
        """env -i bash must be allowed (legitimate env reset for subprocess)."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "env -i bash"})
        assert result is None

    def test_allows_env_var_assignment_after_flag(self) -> None:
        """env VAR=val command must be allowed (env used to set variables)."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "env VAR=val mycommand"})
        assert result is None
