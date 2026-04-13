# EXP-02: Remove Caveman Injection from Subagent Prompts (Lean Subagents)

## HYPOTHESIS

```
Target failure mode: Budget exhaustion (Category 1) + Caveman overhead regression (Category 4)
Evidence:
  - write-compressor: 75% (run2, no caveman) → 0% (run4, with caveman), all 4 trials timeout at 900s
  - dna-assembly: 75% (run2) → 50% (run4) — caveman overhead contributes
  - orchestrator.py _build_agents_dict() appends caveman SKILL.md to all 4 subagent prompts
  - Each planner/builder/reviewer/explorer call carries the full caveman text as extra input tokens
  - Over a multi-round session (planner→builder→reviewer×N), this compounds significantly
Root cause: Caveman SKILL.md duplicated into every subagent prompt via _build_agents_dict().
  Subagents don't need terminal survival heuristics — they need focused task prompts.
Proposed change: Remove caveman injection from subagent prompts in _build_agents_dict().
  Keep caveman in orchestrator's --append-system-prompt (may contain useful reasoning patterns).
  Also includes EXP-01 cwd fix (cwd=TASK_CWD).
Predicted outcome:
  - write-compressor: recover from 0% toward 75% (run2 baseline) as token overhead drops
  - dna-assembly: recover from 50% toward 75% (run2 baseline)
  - Tasks already at 100% (fix-git, cobol-modernization, etc.): no regression
  - Potential minor regression on prove-plus-comm if caveman's disk checkpointing was helping subagents
Generalization argument: "Any multi-agent system benefits from lean, role-specific
  prompts. Injecting a large general-purpose skill document into every specialist
  subagent wastes context window budget and dilutes task-specific instructions."
```

## SCOPE

Test tasks (chosen from evidence):
1. **write-compressor** — direct evidence of caveman overhead regression (75%→0%)
2. **dna-assembly** — secondary evidence of overhead regression (75%→50%)
3. **overfull-hbox** — easy canary for regressions

## CHANGE

Type: ORCHESTRATION (how subagent prompts are constructed)

Two files changed: orchestrator.py (remove caveman from subagents), agent.py (cwd fix from EXP-01).

```diff
--- a/autofyn_agent_caveman/orchestrator.py
+++ b/autofyn_agent_lean/orchestrator.py
@@ -23,7 +23,7 @@
-    agents_json = json.dumps(_build_agents_dict(caveman))
+    agents_json = json.dumps(_build_agents_dict())
@@ -88,14 +88,12 @@
-def _build_agents_dict(caveman: str) -> dict[str, Any]:
+def _build_agents_dict() -> dict[str, Any]:
     """Build the agents JSON passed to --agents flag."""
-    def prompt(name: str) -> str:
-        return f"{load_subagent_prompt(name)}\n\n{caveman}"
-
     return {
         "planner": {
-            "prompt": prompt("planner"),
+            "prompt": load_subagent_prompt("planner"),
         ...
         "builder": {
-            "prompt": prompt("builder"),
+            "prompt": load_subagent_prompt("builder"),
         ...
         "reviewer": {
-            "prompt": prompt("reviewer"),
+            "prompt": load_subagent_prompt("reviewer"),
         ...
         "explorer": {
-            "prompt": prompt("explorer"),
+            "prompt": load_subagent_prompt("explorer"),

--- a/autofyn_agent_caveman/agent.py
+++ b/autofyn_agent_lean/agent.py
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

- write-compressor pass rate: baseline 0/4 → target 2+/4
- dna-assembly pass rate: baseline 2/4 → target 3+/4
- overfull-hbox pass rate: baseline 2/4 → target 2+/4 (no regression)
- Check timing: do rounds complete faster with leaner subagent prompts?

## STATUS

- [ ] Fork created: `autofyn_agent_lean/`
- [ ] Change implemented
- [ ] Run completed
- [ ] Results recorded
- [ ] Verdict issued
