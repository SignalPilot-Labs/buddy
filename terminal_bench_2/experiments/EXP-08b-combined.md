# EXP-08b: Sanity-Check Gate + Single-Session (Combined)

## HYPOTHESIS

```
Target failure mode: Approach-quality failure on raman-fitting, compounded by
  multi-subagent overhead consuming the wall-clock budget.

Evidence:
  - EXP-08 (sanity-check gate, multi-subagent): G peak x0 improved from 3745
    to 1500 (close to expected 1580), but timed out at 900s. The reviewer gate
    fired and forced replanning, but the planner->builder->reviewer round-trip
    overhead consumed all available time before the agent could converge.
  - EXP-05 (single-session): Eliminates multi-subagent overhead. 3/3 on
    write-compressor (opus-4-6), hold-out validated with no regressions.
    However, single-session alone scored 0/1 on raman-fitting because the
    agent lacks the sanity-check self-verification step.
  - The two changes are orthogonal: sanity-check fixes approach quality
    (catch wrong outputs, force re-examination), single-session fixes
    execution efficiency (no subagent dispatch overhead). Combined, the agent
    should catch its own mistakes AND have enough wall-clock budget to iterate.

Root cause addressed: Two independent failure modes compound on raman-fitting:
  (1) agent does not verify output values against task expectations, and
  (2) when it does iterate (via reviewer gate), multi-subagent overhead
  exhausts the 900s budget. Fixing both simultaneously should allow convergence.

Proposed change: Fork from autofyn_agent_single (the validated single-session
  fork). Add the sanity-check verification logic from EXP-08's reviewer.md
  into single_session.md's Phase 4 (Verify). In single-session mode there is
  no separate reviewer subagent, so the sanity-check must be embedded in the
  agent's own verification phase.

Predicted outcome:
  - raman-fitting: 0/1 -> 50%+ (agent catches nonsensical output values,
    re-examines approach, and has enough budget to converge)
  - No regression on other tasks (sanity-check is additive to Phase 4)

Generalization argument: "Combining self-verification with efficient execution
  is universally beneficial. Any agent should both check its outputs against
  requirements AND minimize coordination overhead. These are complementary
  improvements that address different failure modes."
```

## SCOPE

Test task: **raman-fitting** (task directory: `terminal_bench_2/tasks/tasks-run2/raman-fitting`)

This is the task where EXP-08 showed directional improvement (x0 from 3745 to 1500) but timed out due to multi-subagent overhead.

## CHANGE

Type: PROMPT (single-session prompt enhancement)
Category: MEMORY + EFFICIENCY (sanity-check self-verification + single-session execution)

### Fork

Created `terminal_bench_2/autofyn_agent_combined/` by copying `terminal_bench_2/autofyn_agent_single/`.

### Files changed

1. **`autofyn_agent_combined/prompts/single_session.md`** -- Added sanity-check gate as step 0 in Phase 4, before existing steps 1-4. Also updated Phase 4 intro to say "Start by checking whether your results make sense before running formal tests."

2. **`autofyn_agent_combined/pyproject.toml`** -- Package name changed to `autofyn-terminal-bench-combined`.

### Diff summary

New step 0 in Phase 4 instructs the agent to:
- Re-read task instructions and extract stated expected values/ranges
- Compare actual output values against those expectations
- If values are off by order of magnitude / wrong sign / wrong units: go BACK to Phase 2 with a different interpretation
- Lists common fundamental errors: wrong unit conversion, wrong data column, wrong formula

Key design decision: In single-session mode, there is no reviewer subagent. The equivalent location for the sanity-check gate is Phase 4 of single_session.md, with the loop-back going to Phase 2/3 (not "send back to planner").

## RESULTS

### Trial 1: raman-fitting

| Field | Value |
|-------|-------|
| Job ID | combined-20260414-090905 |
| Trial ID | raman-fitting__bwerTr4 |
| Reward | 0.0 |
| Exception | AgentTimeoutError (900s task timeout) |
| Duration | 901s (full timeout used) |
| Agent execution | 09:09:12 - 09:24:13 |
| Outcome | FAIL |

**Test results (from verifier, run after timeout):**
- `test_result_file_exists`: PASS
- `test_G_Peak`: FAIL — Got x0=3745.3166, gamma=28.5624, A=13111.5924, offset=165.9075 vs expected x0=1580.3, gamma=9.06
- `test_2D_Peak`: FAIL — Got x0=6327.8506, gamma=34.8599 vs expected x0=2670.08, gamma=17.52

**What happened:**

The agent used the full 900s budget (same as EXP-08). However, the output values did NOT improve compared to EXP-07 or EXP-08. The G peak x0=3745 is the same raw value seen in the original caveman failure (EXP-07), suggesting the agent reached the same wrong approach and did not successfully apply the sanity-check gate to redirect itself.

This is in contrast to EXP-08 (multi-subagent sanity check), where the G peak x0 improved from 3745 to 1500 -- suggesting the EXP-08 reviewer gate at least partially worked. In EXP-08b, the single-session agent appears to have either:
1. Not reached Phase 4 before timing out (still in Phase 3 build cycle)
2. Reached Phase 4 but the sanity-check text did not trigger meaningful re-examination
3. Attempted to re-plan but ran out of turns/time before producing a different result

Without a claude-stream.jsonl or events.jsonl (the agent ran in Daytona and timed out), we cannot directly confirm whether the agent executed the sanity-check step or not.

**Comparison table:**

| Metric | EXP-07 (caveman) | EXP-08 (sanity, multi-agent) | EXP-08b (combined) |
|--------|-----------------|------------------------------|---------------------|
| Reward | 0.0 | 0.0 | 0.0 |
| Exception | None (early exit) | AgentTimeoutError | AgentTimeoutError |
| Duration | ~82s | 900s | 901s |
| G x0 | 3745 | 1500 | 3745 |
| G gamma | (large) | 200 | 28.56 |
| 2D x0 | 19195 | 2934 | 6327 |
| Mechanism evidence | N/A | Used full budget (vs 82s) | Used full budget |

### Summary table

| Task | Baseline (caveman, run4) | EXP-08 (sanity, multi-agent) | EXP-08b (combined) | Delta vs EXP-08 |
|------|--------------------------|------------------------------|--------------------|-----------------|
| raman-fitting | 0/1 (0%) | 0/1 (0%) | 0/1 (0%) | No change |

### Observations

1. **Sanity-check mechanism did not fire (or did not redirect)**: Unlike EXP-08, the G peak x0=3745 in this trial is the same wrong value as EXP-07 (pre-sanity-check). EXP-08's reviewer gate produced x0=1500 (closer to 1580), which was evidence the mechanism partially worked. Here, the single-session agent ended with the same wrong value it started with.

2. **Agent still used full 900s budget**: The agent did not stop early like EXP-07 (caveman, 82s). This suggests the single-session agent was doing something for the full 15 minutes -- possibly multiple fitting iterations -- but the sanity-check instruction either wasn't reached or wasn't effective enough to redirect the approach.

3. **Single-session mode did not help on raman-fitting**: The hypothesis was that eliminating multi-subagent overhead would give the agent more time to iterate after the sanity-check fires. But if the sanity-check doesn't redirect the agent in single-session mode, there is no iteration benefit to unlock.

4. **The EXP-08 mechanism was different in kind**: In EXP-08, the sanity-check gate was enforced by a SEPARATE reviewer subagent that could block progress and force the planner to receive explicit feedback. In single-session mode, the instruction is just a prompt guideline -- the agent can (and apparently does) proceed past Phase 4 without meaningfully applying the sanity-check, or the agent simply runs out of time before even reaching Phase 4.

5. **n=1 trial caveat**: One trial is insufficient to draw firm conclusions. The agent may sometimes apply the sanity-check correctly. However, the output values (x0=3745) matching the known baseline failure pattern is a strong signal that the mechanism did not fire.

## VERDICT

```
VERDICT: NO-GO — sanity-check gate not effective in single-session mode

Primary failure:
  - Reward = 0.0 (test failure, same as baseline)
  - G peak x0=3745 matches the pre-sanity-check failure pattern (EXP-07)
  - No improvement in output quality compared to either EXP-07 or EXP-08

Hypothesis was partially wrong:
  - The assumption that combining sanity-check + single-session would compound
    their benefits was incorrect. The sanity-check gate requires a separate
    architectural enforcer (the reviewer subagent) to be effective. Embedding
    it as a prompt guideline in single_session.md Phase 4 is not sufficient
    because: (a) the agent may not reach Phase 4 within 900s on this task, and
    (b) prompt instructions without architectural enforcement are advisory only.

Root cause of remaining failure:
  - The raman-fitting task requires multiple iterations to discover the
    nm-to-wavenumber unit conversion. This discovery requires the agent to
    explicitly question its x-axis interpretation -- something the sanity-check
    gate in EXP-08 prompted via a separate reviewer agent feeding back to
    the planner, but which a single-session prompt instruction cannot enforce.

What worked in EXP-08 that doesn't apply here:
  - EXP-08's reviewer is a separate agent with separate context that can observe
    the builder's output and inject feedback into the planner's next iteration.
    The structural separation creates a genuine checkpoint. A Phase 4 instruction
    in a single-session prompt is not the same thing -- the agent in-context may
    rationalize away the mismatch rather than truly re-planning.

Recommendation:
  - Do NOT ship this combination as a general improvement.
  - The EXP-08 direction (separate reviewer with sanity gate) is more promising
    but needs the timeout problem solved independently (longer budget, or faster
    iteration per round).
  - For single-session mode, the sanity-check instruction may need to be
    more aggressive (e.g., requiring the agent to explicitly write out the
    comparison before proceeding) or combined with a turn budget gate.
```
