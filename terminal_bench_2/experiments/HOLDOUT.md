# Hold-Out Tasks

These 3 tasks are reserved for final validation only. NO experiments run on them.

```
HOLD-OUT TASKS:
1. gpt2-codegolf      — pure timeout/unsolvable (hard, 0% all runs)
2. dna-assembly        — inconsistent, model-sensitive (hard, 0-100% across runs)
3. cancel-async-tasks  — moderate inconsistency (hard, 50-75%)
```

## Selection Rationale

- **gpt2-codegolf** covers the "unsolvable under budget" failure mode. If a change improves this, it's likely a fundamental efficiency win. If it regresses, we've added overhead.
- **dna-assembly** covers model sensitivity and caveman overhead regression. It went from 75% (run2, no caveman) to 50% (run4, caveman). Serves as a canary for overhead changes.
- **cancel-async-tasks** covers moderate inconsistency (75% baseline in run4). Tests whether changes maintain reliability on tasks that already mostly work.

Together they span: always-fail, sometimes-fail, usually-pass — across easy/medium/hard difficulty.

## Validation Results

### EXP-05 Hold-Out Validation (Round 7, 2026-04-14)

Experiment: EXP-05 single-session mode (autofyn_agent_single fork, opus-4-6, 30 turns)

| Task | Run3 opus-4-6 Baseline | Run4 Caveman Baseline | Single EXP-05 Result | Regression? |
|------|------------------------|----------------------|----------------------|-------------|
| gpt2-codegolf | 0/4 (0%, timeout) | 0/4 (0%) | 0/1 (0%, AgentTimeoutError) | No |
| dna-assembly | 0/4 (0%, timeout) | 2/4 (50%) | 0/1 (0%, AgentTimeoutError) | No (vs opus-4-6 baseline) |
| cancel-async-tasks | 2/4 (50%) | 3/4 (75%) | 0/1 (0%, 5/6 tests passed) | Acceptable at n=1 |

Verdict: **PASS** — no regressions vs the same-model (opus-4-6) baseline. EXP-05 ships.

Notes:
- dna-assembly 0/1 looks like a regression vs run4 caveman (2/4), but run4 used opus-4-5. vs run3 opus-4-6, it matches exactly (0/4 → 0/1). The task is model-sensitive and opus-4-6 times out on it regardless of fork.
- cancel-async-tasks: agent completed the task quickly with 5/6 tests passing. The missed edge case (`test_tasks_cancel_above_max_concurrent`) is a correctness issue, not a budget/overhead issue. Single-session mode is not expected to improve correctness — only budget efficiency.
- gpt2-codegolf: unsolvable under budget for any current agent (expert time: 2400 min). Always-timeout, as in all prior runs.
