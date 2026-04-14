# EXP-10: Single-Session Validation Run (Swing Tasks)

## HYPOTHESIS

```
Target failure mode: Score validation — confirming net-positive improvement from EXP-05
Evidence:
  - Single-session (opus-4-6) proven: write-compressor 0%->100% (n=3), overfull-hbox 50%->100%
  - Caveman Run 4: prove-plus-comm 100%, dna-assembly 50%, cancel-async-tasks 75%
  - Single-session removes caveman disk checkpointing
  - Model difference: single uses opus-4-6, caveman used opus-4-5 (confound)
Root cause: One validated GO experiment but no full-suite score comparison against Run 4 (50.0%)
Proposed change: No code changes. Run existing autofyn_agent_single on 4 swing tasks.
Predicted outcome:
  - prove-plus-comm: 75-100%
  - dna-assembly: 0-50%
  - cancel-async-tasks: 50-75%
  - raman-fitting: 0-25%
Generalization argument: "Before shipping a fork as the production agent, validate on
  the full task distribution, not just tasks where it was designed to improve."
```

## Task Subset

1. **prove-plus-comm** — regression risk (caveman scored 100%)
2. **cancel-async-tasks** — variance indicator (caveman scored 75%)
3. **dna-assembly** — model sensitivity (75% opus-4-5, 0% opus-4-6 in R3)
4. **raman-fitting** — approach quality check

## Results

### prove-plus-comm (2 trials)

| Trial | Job ID | Result | Time | Notes |
|---|---|---|---|---|
| 1 | single-20260414-102828 | 0.0 | 25s | NonZeroAgentExitCodeError: `cd: /app: No such file or directory` |
| 2 | single-20260414-102907 | 0.0 | 15s | NonZeroAgentExitCodeError: same CWD bug |

**Critical finding:** Both trials failed instantly because `cwd=TASK_CWD="/app"` in the harbor adapter causes the agent bootstrap to fail when `/app` doesn't exist in the task's Daytona sandbox. This is NOT a capability regression — the agent never got to run at all.

### cancel-async-tasks (2 trials)

| Trial | Job ID | Result | Time | Notes |
|---|---|---|---|---|
| 1 | single-20260414-103113 | 0.0 | 2m | 5/6 tests passed (same edge case: cancel_above_max_concurrent) |
| 2 | single-20260414-103340 | 0.0 | 1.5m | 5/6 tests passed (same edge case) |

Agent completes quickly but consistently misses the 6th test about cancellation with max_concurrent. Not a mode issue — same pattern in R7/R10.

### dna-assembly (1+ trials)

| Trial | Job ID | Result | Time | Notes |
|---|---|---|---|---|
| 1 | single-20260414-103513 | 0.0 | 30m | AgentTimeoutError |

Consistent with prior opus-4-6 results (R3: 0%, hold-out: 0/1 timeout).

### raman-fitting (not run in R11)

No R11 trials found for raman-fitting on this fork. Earlier trials:
- single opus-4-5: 0/1
- single opus-4-6: 0/1

## VERDICT

```
VERDICT: BLOCKED — CWD infrastructure bug invalidates prove-plus-comm results
Reason: prove-plus-comm never ran due to /app not existing in its sandbox
Next step: EXP-11 — fix CWD handling, then re-run prove-plus-comm
Risk: If prove-plus-comm genuinely regresses after CWD fix, single-session loses its net advantage
```

## Key Discovery

The harbor adapter (`harbor_agent.py:88`) passes `cwd=TASK_CWD` where `TASK_CWD="/app"` is hardcoded. Tasks whose Daytona sandboxes don't mount files at `/app` fail at bootstrap. Additionally, `single_session.md` hardcodes `/app` paths in Phase 1 instructions and git commands.

This bug may have been masked in earlier experiments because the tested tasks (write-compressor, fix-git, overfull-hbox, cobol-modernization) all happen to use `/app` as their working directory.
