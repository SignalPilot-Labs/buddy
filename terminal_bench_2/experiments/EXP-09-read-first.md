# EXP-09: Read-First Discipline (Understand Before Building)

## Hypothesis

```
Target failure mode: Correctness gap (Category 2) on tasks with existing test suites
Evidence:
  - cancel-async-tasks (R7 hold-out): Agent completed in ~2 min, scored 5/6 tests.
    The failing test (test_tasks_cancel_above_max_concurrent) asserts exactly 2
    "Cleaned up." messages, which requires asyncio.TaskGroup for proper structured
    concurrency cleanup. The agent used asyncio.gather+manual cancel instead —
    a reasonable approach that misses a subtle edge case the test explicitly checks.
    If the agent had read the test file BEFORE coding, it would have seen the exact
    assertion (count of "Cleaned up." == max_concurrent) and understood that cleanup
    must complete even for cancelled tasks — which strongly signals TaskGroup.
  - dna-assembly (inconsistent 0-50%): Tasks with complex acceptance criteria benefit
    from the agent understanding what "correct" means before attempting a solution.
  - General pattern: Phase 1 currently says "Look for test/verification commands"
    (step 5), but this only checks for the existence of test scripts, not reading
    their contents. The agent treats understanding as a formality, not a requirement.
Root cause: The single-session prompt's Phase 1 treats test discovery as optional
  ("look for... 2>/dev/null") and does not instruct the agent to READ and UNDERSTAND
  test file contents before planning. The agent jumps to implementation based on
  README/instructions alone, missing edge-case requirements that are only visible
  in the test code.
Proposed change: Strengthen Phase 1 to require reading test file contents (not just
  listing them), and add an explicit step to extract acceptance criteria from tests
  before moving to Phase 2. Also add a constraint to Phase 2: the plan must address
  every test case discovered in Phase 1.
Predicted outcome:
  - cancel-async-tasks: 0/1 (5/6 tests) -> 1/1 (6/6 tests) — agent reads test,
    sees cleanup assertion, chooses TaskGroup
  - No regressions on write-compressor or overfull-hbox (test-reading adds <30s
    overhead, well within budget)
Generalization argument: "Any coding agent benefits from reading the test suite
  before writing code. Tests encode hidden requirements, edge cases, and acceptance
  criteria that task descriptions often omit. This is standard engineering practice
  (TDD, spec-first development) applied to AI agents. The improvement applies to
  any task with existing tests, regardless of domain."
```

## Scope

Test tasks:
1. **cancel-async-tasks** — target task. 5/6 tests passing, the 6th is a correctness gap that test-reading should close. Use opus-4-6.
2. **write-compressor** — regression check. Must remain 1/1 on opus-4-6. Already 3/3 baseline.

## Change

Type: PROMPT (single change to the single-session prompt)

Files:
- Created `terminal_bench_2/autofyn_agent_readfirst/` fork from `autofyn_agent_single/`
- Modified `terminal_bench_2/autofyn_agent_readfirst/prompts/single_session.md`

### Phase 1 changes (final version)

Replaced steps 5-6 with:

```
5. Find all test files: `find /app /tests 2>/dev/null -maxdepth 3 \( -name "test_*" -o -name "*_test.*" -o -name "test.py" -o -name "tests.py" \) | grep -v __pycache__ | head -20`.
6. **Read every test file found.** For each test, extract: (a) what it asserts, (b) what edge cases it covers, (c) what the expected output format/values are.
7. Find verification scripts: `ls /app/test.sh /app/verify.sh /app/run_tests.sh /app/Makefile /tests/test.sh /tests/Makefile 2>/dev/null` and read their contents.
8. Write out your understanding: list every acceptance criterion from the tests. If a test checks a specific edge case, note it explicitly.
```

### Phase 2 changes

Added after plan bullet points:

```
Your plan MUST address every test case discovered in Phase 1. If a test checks an edge case, your implementation must handle that case. Do not proceed to Phase 3 until your plan covers all discovered acceptance criteria.
```

### Prompt evolution during experiment

- **v1** (initial): `find /app -name "test_*" ...` — did not find tests (tests at /tests/, not /app/)
- **v2** (fix 1): `find / -maxdepth 4 -name ...` — too slow, caused write-compressor to timeout (15+ min fs scan)
- **v3** (fix 2, final): `find /app /tests 2>/dev/null -maxdepth 3 ...` — correct scope, fast

### Critical discovery: Tests not available to agent

**The tests in this benchmark are NOT available to the agent during its run.** The test files live in `/tests/` which is only mounted by harbor for the verifier phase, AFTER the agent finishes. During agent execution:
- `/app/` — agent workspace (writable, initially empty)
- `/tests/` — NOT mounted

So `find /app /tests` during agent execution returns no test files. The read-first prompt change is structurally blocked for this benchmark's architecture.

## Results

| Trial | Job ID | Task | Prompt Version | Reward | Notes |
|-------|--------|------|----------------|--------|-------|
| 1 | readfirst-20260414-094313 | cancel-async-tasks | v1 (find /app) | 0 (5/6) | semaphore+gather, tests not found |
| 2 | readfirst-20260414-094318 | cancel-async-tasks | v1 (find /app) | 1 (6/6) | TaskGroup, tests not found |
| 3 | readfirst-20260414-094519 | cancel-async-tasks | v2 (find /) | 1 (6/6) | signal handler approach, tests not found |
| 4 | readfirst-20260414-094833 | write-compressor | v2 (find /) | 0 (timeout) | AgentTimeoutError — find / scan too slow |
| 5 | readfirst-20260414-100437 | write-compressor | v3 (find /app /tests) | 0 (timeout) | AgentTimeoutError — extra Phase 1 steps exceed 900s budget |

### cancel-async-tasks Analysis

Trials 1-3: Agent ran `find` for test files, found nothing (tests not mounted). Behavior varied:
- Trial 1: Used gather+manual cancel → 5/6 (original failure mode)
- Trial 2: Used `asyncio.TaskGroup` → 6/6 (correct solution, by model reasoning not test reading)
- Trial 3: Used signal handler approach → 6/6 (correct but different from TaskGroup)

The improvement from 5/6 to 6/6 in trials 2-3 is NOT attributable to reading test files. The agent chose correct approaches based on its own reasoning about asyncio cancellation, not from test inspection.

### write-compressor Analysis

Both write-compressor trials timed out. Root cause: the expanded Phase 1 (4 new steps) adds overhead that exceeds the 900-second budget. The task barely fit in 900s with the original prompt (EXP-05 baseline ~14 min total). Even the `find /app /tests` version (fast command, no files found) timed out, meaning the 4 extra steps in Phase 1 (even when producing no results) consume enough LLM time to exceed budget.

### Agent Behavior (cancel-async-tasks trials)

Looking at events.jsonl for each trial:
- All trials ran the `find` command as step 2 (Phase 1 step 5)
- All trials received empty results from find
- Trial 2 chose TaskGroup without finding tests (model knowledge, not test reading)
- Trial 3 chose signal handler without finding tests (model knowledge, not test reading)

The prompt change triggered the find command, but since tests aren't accessible, the read-first discipline was never exercised.

## Verdict

```
VERDICT: NO-GO

Reason:
1. The core mechanism (reading test files) doesn't work for this benchmark.
   Terminal-bench mounts test files only for the verifier, not for the agent.
   The `find` command returns empty — so the "read-first" behavior never fires.

2. cancel-async-tasks improved (2/2 passes in trials 2-3) BUT this is NOT
   because the agent read tests. The improvement is due to model stochasticity
   (the model correctly reasoning about asyncio TaskGroup or signal handlers).
   This cannot be credited to the prompt change.

3. write-compressor regressed to 0% (2/2 timeouts) vs 3/3 baseline.
   The additional Phase 1 steps (even when producing no test files) consume
   LLM processing time that exceeds the 900-second budget for tight tasks.

4. The hypothesis is structurally blocked: terminal-bench's architecture
   does not expose tests to agents. The prompt change cannot work as intended.

Alternative directions:
- Inline the key test assertions into the task instruction (task-level change)
- Post-generation fix cycles: run the test, read failure output, fix
  (Phase 4 already does this — the issue is failing before Phase 4)
- The cancel-async-tasks failure might be solved by Phase 4 fix-retest
  if we give the agent the actual test command to run

Measurement plan compliance:
- GO criterion (cancel-async-tasks 6/6 AND write-compressor 1.0): NOT MET
  (write-compressor timed out)
- PARTIAL (cancel-async-tasks 5/6, no regression): NOT MET
  (write-compressor regressed)
- NO-GO (regression on write-compressor): THIS APPLIES
```

## STATUS

- [x] Fork created: `autofyn_agent_readfirst/`
- [x] Prompt modified
- [x] cancel-async-tasks trials run (3 trials)
- [x] write-compressor trials run (2 trials)  
- [x] Results recorded
- [x] Verdict issued
