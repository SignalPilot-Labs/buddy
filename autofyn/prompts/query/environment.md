## Environment

You run in a gVisor-sandboxed Docker container. Repo at `/home/agentuser/repo`, round reports at `/tmp/round-{ROUND_NUMBER}/`, Claude state at `/home/agentuser/.claude/`. Network is available. Single tool call timeout: {TOOL_CALL_TIMEOUT_MIN} min.

Pre-installed — do NOT install these: `pytest`, `pytest-asyncio`, `pyright`, `mypy`, `ruff`, `black`, `npm`, `typescript` (tsc), `eslint`, `prettier`. If `CLAUDE.md` specifies different tools (e.g. biome, vitest, uv), follow that.

{HOST_MOUNTS_BLOCK}
