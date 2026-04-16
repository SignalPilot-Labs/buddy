"""Regression: every call to `_git(...)` must pass the `with_token=` kwarg.

`_git` is declared keyword-only for `with_token` so callers have to
explicitly choose whether to leak the git token into the subprocess env
(authenticated ops) or not (local ops). A caller that forgets the kwarg
raises `TypeError: _git() missing 1 required keyword-only argument`
at runtime — exactly the crash that killed `/repo/bootstrap` after the
PR #157 base_sha capture landed without updating for this PR's refactor.

Rather than relying on runtime coverage catching every path, this test
AST-walks the two files where `_git` is called and asserts the kwarg
is present on every invocation. Fast, deterministic, covers paths that
integration tests don't hit.
"""

import ast
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).parent.parent.parent
_SOURCES = (
    _REPO_ROOT / "sandbox" / "handlers" / "repo.py",
    _REPO_ROOT / "sandbox" / "handlers" / "repo_phases.py",
)


def _git_callsites(source: Path) -> list[tuple[int, ast.Call]]:
    """Return (lineno, Call) for every `_git(...)` call in source."""
    tree = ast.parse(source.read_text())
    calls: list[tuple[int, ast.Call]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "_git":
                calls.append((node.lineno, node))
    return calls


@pytest.mark.parametrize("source", _SOURCES, ids=lambda p: p.name)
def test_every_git_call_passes_with_token(source: Path) -> None:
    missing: list[int] = []
    for lineno, call in _git_callsites(source):
        kwarg_names = {kw.arg for kw in call.keywords if kw.arg is not None}
        if "with_token" not in kwarg_names:
            missing.append(lineno)
    assert not missing, (
        f"{source.name}: `_git(...)` calls missing `with_token=` kwarg at lines "
        f"{missing}. `with_token` is keyword-only — omitting it crashes with "
        f"TypeError at runtime."
    )


def test_sources_actually_call_git() -> None:
    # Guard: if someone renames _git or restructures, the parametrized
    # test above would pass vacuously. Assert we actually found calls.
    total = sum(len(_git_callsites(src)) for src in _SOURCES)
    assert total >= 5, (
        f"Expected several _git(...) callsites across {[s.name for s in _SOURCES]}; "
        f"found {total}. Test file may be scanning the wrong sources."
    )
