## Pre-installed Tools

These are already available — do NOT pip/npm install them:
- Python: `pytest`, `pytest-asyncio`, `pyright`, `mypy`, `ruff`, `black`
- Node: `typescript` (tsc), `eslint`, `prettier`

If `CLAUDE.md` specifies different tools or configs (e.g. biome instead of eslint, mypy instead of pyright), follow those instead.

## Verification

Before considering work done, run:
1. **Typechecker** — `pyright` for Python, `tsc --noEmit` for TypeScript.
2. **Linter** — `ruff check` for Python, `eslint` for JS/TS if configured.
3. **Tests** — `pytest tests/fast/` for backend. If frontend tests exist (`vitest.config.*` or `jest.config.*`), run those too.