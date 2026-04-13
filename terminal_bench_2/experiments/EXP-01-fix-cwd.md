# EXP-01: Fix Missing cwd=TASK_CWD in Caveman Agent

## HYPOTHESIS

```
Target failure mode: Budget exhaustion (Category 1) + general efficiency
Evidence:
  - autofyn_agent/agent.py:98 passes cwd=TASK_CWD to exec_as_agent()
  - autofyn_agent_caveman/agent.py:78 does NOT pass cwd, defaulting to container root
  - system.md line 11 tells orchestrator to read files in /app, line 61 says "Work directory is /app"
  - Agent must waste early turns doing `cd /app && pwd` to orient itself
  - write-compressor run4: all 4 trials timeout at exactly 900s (0%), run2 with cwd: 75% pass
Root cause: Caveman agent.py omits cwd=TASK_CWD when calling exec_as_agent().
  Claude CLI starts in the wrong directory, wasting turns on navigation.
Proposed change: Add cwd=TASK_CWD to the exec_as_agent() call in caveman agent.py
Predicted outcome:
  - All tasks: agent starts in /app immediately, saving 1-2 early turns
  - write-compressor: may recover some trials (though caveman overhead is the primary factor)
  - No regressions expected — this restores behavior the non-caveman agent already has
Generalization argument: "A coding agent working on a completely different
  domain would also benefit from this change because starting in the correct
  working directory is fundamental to any file-based task. Without it, the
  agent wastes turns on navigation that provide zero task value."
```

## SCOPE

Test tasks (chosen from evidence):
1. **write-compressor** — direct evidence of cwd impact (75% run2 with cwd, 0% run4 without)
2. **overfull-hbox** — easy task that should always pass; canary for regressions

Both have clean trial execution (no infra errors) and are NOT in the hold-out set.

## CHANGE

Type: TOOL USE (how the agent process is launched)

Single-line diff in `agent.py`:

```diff
--- a/autofyn_agent_caveman/agent.py
+++ b/autofyn_agent_experiment/agent.py
@@ -18,6 +18,7 @@
-from terminal_bench.constants import AGENT_TIMEOUT_SEC, DEFAULT_MAX_TURNS, DEFAULT_MODEL
+from terminal_bench.constants import AGENT_TIMEOUT_SEC, DEFAULT_MAX_TURNS, DEFAULT_MODEL, TASK_CWD
@@ -78,4 +79,5 @@
         await self.exec_as_agent(
             environment,
             cmd,
+            cwd=TASK_CWD,
             timeout_sec=AGENT_TIMEOUT_SEC,
         )
```

## MEASUREMENT PLAN

- Compare write-compressor pass rate: baseline 0/4 → target 1+/4
- Compare overfull-hbox pass rate: baseline 2/4 → target 2+/4 (no regression)
- Check timing: does agent spend fewer early turns on directory navigation?

## STATUS

- [ ] Fork created: `autofyn_agent_fix_cwd/`
- [ ] Change implemented
- [ ] Run completed
- [ ] Results recorded
- [ ] Verdict issued
