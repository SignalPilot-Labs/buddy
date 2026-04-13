# EXP-04: Mandatory Planner Exploration (Explore First)

## HYPOTHESIS

```
Target failure mode: Wrong abstraction / feedback blindness caused by insufficient upfront analysis (Categories 2+3)
Evidence:
  - raman-fitting (25%): Passing trial spent 15+ bash commands exploring data before fitting.
    Failing trials skipped exploration and fit in wrong spectral region (assumed x-axis was
    Raman shift when it was absolute wavenumber with European decimal commas).
  - overfull-hbox (50%): Passing trials verified article agreement after synonym substitution.
    Failing trials substituted words without checking grammar.
  - dna-assembly (50%): Passing trials discovered primer clamp requirements through exploration.
    Failing trials jumped to implementation.
  - Pattern: when the planner explores thoroughly, the agent passes. When it rushes, it fails.
Root cause: Planner prompt has no mandatory exploration phase. The "Map the territory" step
  (planner.md line 11-12) is advisory — the planner can skip it when the task looks familiar.
  This leads to wrong assumptions about data formats, units, and constraints.
Proposed change: Add a mandatory "Explore First" phase to the planner prompt. Before writing
  any spec, the planner MUST: (1) list all files in the task directory, (2) read key data/config
  files and print their structure, (3) state explicit assumptions about data formats, units,
  and expected I/O, (4) only then write the implementation spec.
Predicted outcome:
  - overfull-hbox: 50% -> 75%+ (planner discovers token-level constraints before spec)
  - raman-fitting: 25% -> 50%+ (planner discovers x-axis units and decimal format before spec)
  - No regressions — exploration only adds information, never removes it
Generalization argument: "Any coding agent working on an unfamiliar codebase benefits from
  systematic exploration before planning. This is the equivalent of a senior engineer reading
  the codebase before designing a solution — a universal practice regardless of domain."
```

## SCOPE

Test tasks (chosen from evidence):
1. **overfull-hbox** — direct evidence of exploration gap (50%, easy task; planner skips grammar verification)
2. **raman-fitting** — strongest evidence of exploration gap (25%, planner assumes x-axis units without checking)

Both are non-hold-out inconsistent tasks with documented exploration-gap failures. Both have clean trial execution (no infra errors).

## CHANGE

Type: PROMPT (planner prompt only). No Python code changes beyond those inherited from `autofyn_agent_verify` (EXP-01 cwd fix + EXP-02 lean subagents + EXP-03 verify-before-completing).

Single file changed: `prompts/subagents/planner.md`

```diff
--- a/autofyn_agent_verify/prompts/subagents/planner.md
+++ b/autofyn_agent_explore/prompts/subagents/planner.md
@@ -3,6 +3,50 @@
 You do NOT write code. You can read files and run read-only commands to understand the current state.

+## Explore First (Mandatory)
+
+Before writing ANY spec, you MUST complete this exploration phase. Do not skip it.
+Do not combine it with planning. Exploration comes first, planning comes second.
+
+### Step 1: Map the workspace
+
+Run `find /app -maxdepth 2 -type f | head -50` to see all task files. Read the README,
+instructions, or any task description files.
+
+### Step 2: Inspect data and configuration
+
+For every data file, config file, or input file in the task directory:
+- Read the first 20-30 lines to understand the format
+- Note: delimiters (comma, tab, semicolon), decimal format (period vs comma), encoding, units
+- Note: column headers, data types, value ranges, special characters
+
+For every script, Makefile, or test file:
+- Read it fully to understand what the task expects as output
+- Note: expected file paths, expected formats, expected value ranges
+
+### Step 3: State your assumptions
+
+Before writing the spec, write a section called "Assumptions" that lists:
+- What format the input data is in (with evidence: "line 3 shows X")
+- What units values are in (with evidence)
+- What the expected output format is (with evidence)
+- What libraries or tools are available (check with
+  `which python3 && python3 -c "import numpy; print(numpy.__version__)" 2>/dev/null` or equivalent)
+
+If you cannot find evidence for an assumption, say so explicitly:
+"UNVERIFIED ASSUMPTION: [what you assumed and why]". The builder will need to verify these.
+
+### Step 4: Proceed to planning
+
+Only after completing steps 1-3, proceed to the planning process below.
+
 ## Think Before You Plan
```

## MEASUREMENT PLAN

- Compare pass rates against `autofyn_agent_verify` baseline (4 trials per task):
  - overfull-hbox: baseline 50% → target 75%+
  - raman-fitting: baseline 25% → target 50%+
- Secondary metrics: does the planner's first-round spec contain correct data format assumptions? (qualitative review of spec files)
- Regression check: tasks at 100% in baseline must stay at 100%

## STATUS

- [ ] Fork created: `autofyn_agent_explore/`
- [ ] Change implemented
- [ ] Run completed
- [ ] Results recorded
- [ ] Verdict issued
