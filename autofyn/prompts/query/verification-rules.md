## Verification

Before considering work done, run:
1. **Typechecker** — `pyright` for Python, `tsc --noEmit` for TypeScript.
2. **Linter** — `ruff check` for Python, `eslint` for JS/TS if configured.
3. **Tests** — `pytest tests/fast/` for backend. If frontend tests exist (`vitest.config.*` or `jest.config.*`), run those too.