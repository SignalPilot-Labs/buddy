# EXP-03: Verify-Before-Completing (Feedback Blindness Fix)

## HYPOTHESIS

```
Target failure mode: Feedback Blindness (Category 2)
Evidence:
  - overfull-hbox (50%): Builder substitutes words but never checks token-level agreement. Reviewer catches it one round later.
  - raman-fitting (25%): Builder assumes x-axis units without exploring data. Only the passing trial explored first.
  - filter-js-from-html (0%): Builder never discovers BeautifulSoup normalization mismatch because it never runs the test.
Root cause: Builder prompt says "Run any tests" as a weak suggestion in the "After Writing Code" section.
  The builder treats this as optional and rarely executes task-level tests. By the time the reviewer
  runs tests and reports failures, one full planner->builder->reviewer cycle has been consumed.
Proposed change: (1) Strengthen builder prompt with mandatory test-then-iterate loop.
  (2) Add orchestrator instruction to discover and communicate test commands to the builder.
Predicted outcome:
  - overfull-hbox: 50% -> 75%+ (builder catches article agreement errors on first attempt)
  - raman-fitting: 25% -> 50%+ (builder discovers unit mismatch when fit fails quality checks)
  - filter-js-from-html: 0% -> 25%+ (builder discovers normalization mismatch from test diff)
  - No regressions on passing tasks — verification only adds value, never removes it
Generalization argument: "Any coding agent benefits from running tests before declaring
  completion. This is the equivalent of a developer running `make test` before pushing —
  a universal practice regardless of domain or task type."
```

## SCOPE

Test tasks (chosen from evidence):
1. **overfull-hbox** — direct evidence of feedback blindness (50%, easy task)
2. **raman-fitting** — feedback blindness + data exploration gap (25%, medium task)
3. **filter-js-from-html** — structural mismatch discoverable via test output (0%, medium task)
4. **write-compressor** — canary for regressions / timing (0% in caveman, should improve with EXP-01 cwd fix)

## CHANGE

Type: PROMPT (builder prompt + orchestrator system prompt). No Python code changes beyond those inherited from EXP-01 (cwd fix) and EXP-02 (lean prompts).

Changes applied on top of EXP-01 cwd fix:

1. `agent.py`: Added `cwd=TASK_CWD` to `exec_as_agent()` call (EXP-01 fix).
2. `orchestrator.py`: Removed caveman injection from subagent prompts in `_build_agents_dict()` — subagents now receive clean prompts; caveman stays in `--append-system-prompt` only (EXP-02 lean prompt reduction).
3. `prompts/subagents/builder.md`: Replaced weak "After Writing Code" section with mandatory "Verify Before Completing" section including 3-attempt fix-and-retest loop and VERIFIED/UNVERIFIED status declaration.
4. `prompts/system.md`: Added test discovery as step 4 in first-round setup; updated Build step to forward test commands to builder and check VERIFIED/UNVERIFIED status.

## MEASUREMENT PLAN

- Compare pass rates against autofyn_agent_caveman baseline (4 trials per task):
  - overfull-hbox: baseline 50% → target 75%+
  - raman-fitting: baseline 25% → target 50%+
  - filter-js-from-html: baseline 0% → target 25%+
  - write-compressor: baseline 0% → target 50%+ (EXP-01 cwd fix contributing)
- Secondary metrics: number of rounds per task (should decrease when builder self-corrects), turn budget usage
- Regression check: any task that was 100% in baseline must stay at 100%

## STATUS

- [ ] Fork created: `autofyn_agent_verify/`
- [ ] Changes implemented
- [ ] Run completed
- [ ] Results recorded
- [ ] Verdict issued
