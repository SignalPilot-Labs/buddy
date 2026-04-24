## Verification

Before considering work done, run:
1. **Typechecker** — `pyright` for Python, `tsc --noEmit` for TypeScript.
2. **Linter** — `ruff check` for Python, `eslint` for JS/TS if configured.
3. **Tests** — `pytest tests/fast/` for backend. If frontend tests exist (`vitest.config.*` or `jest.config.*`), run those too.
4. **Goal eval** — Run the eval command from run_state.md's Concrete Target. Compare against the last Eval History entry. Report the delta.
