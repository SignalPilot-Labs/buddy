# EXP-05: Single-Session Mode for Tight Budgets

## HYPOTHESIS

```
Target failure mode: Budget exhaustion (Category 1) on tight-budget tasks
Evidence:
  - write-compressor (900s budget): Run2 (no caveman, but still multi-subagent) passed at 877s.
    Run4 (caveman) timed out all 4 trials. Even with EXP-01+02 fixes removing cwd bug and
    caveman overhead, multi-subagent round-trips (planner->builder->reviewer) consume significant
    budget on a task whose correct solution is ~5 shell commands.
  - mteb-retrieve (1800s budget, 0% all runs): Agent never produces output. The correct solution
    runs in <2 minutes. Multi-subagent overhead is the dominant cost.
  - fix-code-vulnerability (900s budget): Reads 3500-line bottle.py, multi-subagent overhead
    exhausts budget. (Also has infra bug — exclude from testing.)
Root cause: Multi-subagent architecture (planner->builder->reviewer loop) has fixed per-round
  overhead from LLM dispatching, prompt loading, and context switching. On tight budgets
  (<=900s), this overhead consumes a large fraction of available time.
Proposed change: When explicitly opted in via AUTOFYN_SINGLE_SESSION=1, bypass the
  multi-subagent orchestrator and run a single Claude session with a combined prompt that
  includes planning, building, and self-review instructions. This eliminates subagent dispatch
  overhead entirely.
Predicted outcome:
  - write-compressor: 0% -> 75%+ (eliminates overhead, solution is simple)
  - No regressions on non-tight-budget tasks (they still use multi-subagent mode)
Generalization argument: "Any multi-agent system should adapt its coordination overhead
  to the available budget. When time is scarce, the overhead of dispatching work between
  specialists exceeds the benefit of specialization. A single generalist session is more
  efficient for simple tasks under tight deadlines."
```

## SCOPE

Test tasks (chosen from evidence):
1. **write-compressor** — 900s budget task with clear multi-subagent overhead evidence (Run2 barely passed at 877s, Run4 timed out)

Do NOT test on:
- **mteb-retrieve** — 0% all runs, may have other blocking issues beyond overhead
- **fix-code-vulnerability** — known infra bug, excluded

## CHANGE

Type: ORCHESTRATION + PROMPT (orchestrator routing + new combined prompt)

Opt-in mechanism: Set `AUTOFYN_SINGLE_SESSION=1` when invoking the agent.

Files changed:
- `autofyn_agent_single/constants.py` — add `SINGLE_SESSION_ENV_VAR`
- `autofyn_agent_single/prompts/single_session.md` — new combined prompt (plan+build+verify in one session)
- `autofyn_agent_single/orchestrator.py` — add `build_single_session_command()`
- `autofyn_agent_single/agent.py` — add routing based on `AUTOFYN_SINGLE_SESSION` env var
- `autofyn_agent_single/pyproject.toml` — rename package to `autofyn-terminal-bench-single`

```diff
--- a/autofyn_agent_verify/constants.py
+++ b/autofyn_agent_single/constants.py
+# Env var opt-in for single-session mode (bypass multi-subagent orchestration)
+SINGLE_SESSION_ENV_VAR: str = "AUTOFYN_SINGLE_SESSION"
```

```diff
--- a/autofyn_agent_verify/agent.py
+++ b/autofyn_agent_single/agent.py
+from terminal_bench.constants import SINGLE_SESSION_ENV_VAR
+from terminal_bench.orchestrator import build_cli_command, build_single_session_command, parse_stream_output

 # In run():
+if os.environ.get(SINGLE_SESSION_ENV_VAR, "") == "1":
+    claude_cmd = build_single_session_command(instruction, model, max_turns, claude_bin)
+else:
     claude_cmd = build_cli_command(instruction, model, max_turns, claude_bin)
```

## MEASUREMENT PLAN

- Run write-compressor with `AUTOFYN_SINGLE_SESSION=1`: baseline 0/4 → target 3+/4
- Run overfull-hbox without `AUTOFYN_SINGLE_SESSION` (normal mode): must match verify fork baseline (no regression)
- Check timing: does single-session finish well under 900s for write-compressor?

## STATUS

- [ ] Fork created: `autofyn_agent_single/`
- [ ] Change implemented
- [ ] Run completed
- [ ] Results recorded
- [ ] Verdict issued
