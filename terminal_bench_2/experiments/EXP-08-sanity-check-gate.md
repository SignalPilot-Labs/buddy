# EXP-08: Sanity-Check Gate (Reviewer Self-Verification)

## HYPOTHESIS

```
Target failure mode: Approach-quality failure — agent produces nonsensical results
  and commits without noticing they are wrong.

Evidence:
  - Failing EXP-07 raman-fitting trial (KVAwM9B, 14 turns): Agent found peaks at
    raw x-values 19140 and 3745, fitted Lorentzians to those raw coordinates, wrote
    results.json with x0=3745 for G peak (expected ~1580) and x0=19195 for 2D peak
    (expected ~2700). Never checked whether output values matched expected ranges.
    Committed and ended session.
  - Failing run4 trials (BgjcGFm, J9fcqRR, QaLv48C): Similar pattern — agent
    produces fitting parameters that are orders of magnitude off from expected values,
    but the reviewer does not catch this because it validates structure (JSON keys,
    types) not semantic correctness (are the numbers physically reasonable?).
  - Passing run4 trial (rBcV9fG, 78 turns): Agent spent 50+ turns exploring data
    interpretations. Crucially, it noticed peaks were at wrong positions and kept
    exploring until it discovered the nm-to-wavenumber conversion. The difference
    was persistent skepticism about intermediate results.
  - EXP-07 (100 turns) did NOT help: Agent used only 14 turns and stopped. The
    problem is not budget — it is that the agent does not verify its own output
    against the task's stated expectations before declaring victory.

Root cause: The reviewer prompt (reviewer.md) checks structural correctness (JSON
  format, types, file existence) and code quality, but has no instruction to compare
  computed output values against the task's stated expectations. When the task says
  "G peak ~1580 cm-1" and the output says x0=3745, the reviewer should flag this as
  a critical correctness issue. Currently it does not.

Proposed change: Add a "Sanity-Check Gate" section to the reviewer prompt that
  instructs the reviewer to:
  1. Re-read the task description/instructions to extract any stated expected values,
     units, ranges, or reference points.
  2. Compare actual output values against those expectations.
  3. Flag as CRITICAL if output values differ from stated expectations by more than
     a reasonable margin (order of magnitude, wrong units, wrong sign).
  4. Recommend the planner re-examine assumptions (not just re-run the same approach).

Predicted outcome:
  - raman-fitting: 0/1 -> 25%+ (reviewer catches nonsensical x0 values, forces
    replanning which may lead to discovering the unit conversion)
  - No regression on passing tasks (sanity check is additive — it only blocks when
    output values violate the task's own stated expectations)

Generalization argument: "Any coding agent benefits from checking computed outputs
  against the problem statement's stated expectations before declaring success. This
  is not domain-specific — it is the software engineering practice of validating
  outputs against requirements. A test that checks 'does my output match what the
  spec said to expect' catches a broad class of approach-quality failures."
```

## SCOPE

Test tasks:
1. **raman-fitting** — target task, currently 0% due to approach-quality failure
   where output values are orders of magnitude off from stated expectations

Do NOT test on:
- write-compressor — budget task, already solved by EXP-05
- mteb-retrieve — infra issue
- Other tasks — hold-out for later validation

## CHANGE

Type: PROMPT (reviewer prompt enhancement)
Category: MEMORY — the reviewer is instructed to checkpoint and compare the task's
stated expectations against actual computed output, creating a feedback loop.

### Fork

Created `autofyn_agent_sanity/` by copying `autofyn_agent_caveman/`.

### Files changed

1. **`autofyn_agent_sanity/prompts/subagents/reviewer.md`** — Added new "Step 2:
   Sanity-Check Gate" section between existing "Step 1: Run Verification" and
   "Step 2: Get the Diff" (renumbered to Step 3). Step 3 Review renumbered to Step 4.

2. **`autofyn_agent_sanity/pyproject.toml`** — Package name updated to
   `autofyn-terminal-bench-sanity`.

### Diff summary

The new Step 2 instructs the reviewer to:
- Re-read task instructions and extract stated expected values/ranges
- Compare actual output values against those expectations (order of magnitude,
  units, sign)
- Flag as Critical Issue if any value is wildly off, and recommend sending back
  to the planner to re-examine assumptions (not small fixes)

## RESULTS

### Trial: raman-fitting

| Field | Value |
|-------|-------|
| Job ID | sanity-20260414-084522 |
| Trial ID | raman-fitting__CK2zRkh |
| Reward | 0.0 |
| Exception | AgentTimeoutError (900s task timeout) |
| Duration | 900s (full timeout used) |
| Outcome | FAIL |

**Test results (from verifier, run after timeout):**
- `test_result_file_exists`: PASS
- `test_G_Peak`: FAIL — Got x0=1500, gamma=200 vs expected x0=1580.3, gamma=9.06
- `test_2D_Peak`: FAIL — Got x0=2934, gamma=176 vs expected x0=2670.08, gamma=17.52

**What happened:**

The agent used the full 900s budget (compared to caveman EXP-07 which used only 14 turns/~82s). This is a significant behavioral change — the agent spent more time iterating rather than stopping early with wrong results. This is consistent with the Sanity-Check Gate firing and sending work back to the planner for re-examination. However, without an events.jsonl (the agent timed out before completing), we cannot directly confirm the reviewer called out the sanity failure.

The results.json values are still wrong but differ from the EXP-07 failure pattern:
- EXP-07 (caveman): G x0=3745 (off by 2.4x), committed after 14 turns
- EXP-08 (sanity): G x0=1500 (off by ~5%), but gamma=200 vs 9.06 (off by 22x)

The x0 values are much closer in EXP-08 (1500 vs 1580 is ~5% error, nearly within tolerance). This suggests the agent may have gotten closer to the correct approach — potentially the reviewer's Sanity-Check Gate caught the extreme x0 values and the planner successfully found a better approach for peak location, but the Lorentzian fitting parameters (gamma, amplitude) are still wrong.

**Evidence the Sanity-Check Gate mechanism fired:**
- The agent used 900s (full budget) instead of stopping at ~82s (as in caveman)
- The G peak x0 improved from 3745 (EXP-07) to 1500 (EXP-08) — closer to 1580 target
- This time pattern and improvement is consistent with: reviewer flagged wrong values → planner re-planned → builder tried a different approach → agent used more turns cycling through review iterations

**Evidence against (ambiguous):**
- No events.jsonl to directly confirm the reviewer's review content
- Task still failed: x0=1500 passes the <5% relative tolerance test for a ballpark check but gamma=200 (vs 9.06) is still 22x off
- Could be coincidence — a timeout with a different random initial approach

### Summary table

| Task | Baseline (caveman, run4) | EXP-08 (sanity) | Delta |
|------|--------------------------|------------------|-------|
| raman-fitting | 0/1 (0%) | 0/1 (0%) | No improvement in pass rate |

### Observations

1. **The Sanity-Check Gate appears to have changed agent behavior**: The agent used the full 900s timeout instead of stopping at ~82s. This is a material behavioral change. In caveman, the agent stops early with wrong results. In sanity, the agent keeps iterating — consistent with the reviewer flagging bad values and forcing replanning.

2. **Partial improvement in x0 values**: G peak x0 improved from 3745 to 1500, which is much closer to 1580.3. This may indicate the reviewer's sanity check identified the large mismatch and the agent managed to find a better peak location approach. However, gamma (width) is still 22x too large, suggesting the Lorentzian fitting is still wrong.

3. **Timeout is now the binding constraint**: The mechanism appears to be working (more iterations, better intermediate values) but the task is constrained by the 900s wall-clock budget. The sanity-check → replan → rebuild cycles consume time, and 900s is not enough for the agent to converge on the correct answer.

4. **n=1 caveat**: With a single trial we cannot distinguish between the Sanity-Check Gate being effective and the agent getting stuck in a different failure mode that happened to run longer. The pattern is consistent with the hypothesis but not conclusive.

## VERDICT

```
VERDICT: PARTIAL — mechanism appears to fire, but task still fails due to timeout

Evidence for mechanism working:
  - Agent used full 900s budget (vs 82s for caveman) — consistent with reviewer
    flagging and planner replanning multiple times
  - G peak x0 improved from 3745 → 1500 (much closer to expected 1580)

Evidence task not solved:
  - Reward = 0.0 (test failure)
  - Gamma values still ~22x off (fitting parameters wrong)
  - No events.jsonl to confirm reviewer content

Root cause of remaining failure:
  - The Sanity-Check Gate appears to fire and prevent early exit with bad x0 values
  - But the agent still cannot find the correct Lorentzian fitting approach within
    the 900s budget — the re-planning cycles consume the wall-clock time
  - The fitting problem (wrong gamma/amplitude despite better x0) suggests the agent
    finds peak locations but uses wrong fitting bounds or algorithm

Recommendation:
  - This is NOT a clear GO — the task still fails and the mechanism is unconfirmed
    without events.jsonl
  - The approach direction is promising: more agent iteration time was spent, and
    intermediate values improved
  - For a definitive verdict, need either: (a) a second trial to check if behavior
    is consistent, or (b) longer task timeout to give more time for replanning cycles
  - The raman-fitting task itself has a correctness gap that is not fully addressed
    by the Sanity-Check Gate alone — the planner needs more guidance on the
    nm-to-wavenumber conversion or fitting bounds
```
