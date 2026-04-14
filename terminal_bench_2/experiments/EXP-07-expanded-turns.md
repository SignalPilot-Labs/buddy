# EXP-07: Expanded Turn Budget for Single-Session Mode

## HYPOTHESIS

```
Target failure mode: Turn cap prevents sufficient exploration in single-session mode
Evidence:
  - raman-fitting single-session trial: 26/30 turns used, never discovered the
    nm-to-wavenumber conversion. Both passing trials needed 77-78 tool calls.
  - DEFAULT_MAX_TURNS=30 in constants.py was carried from multi-subagent mode
    where each subagent gets its own turn budget. Single-session concentrates
    all work into one session, so it needs a proportionally larger turn budget.
  - The passing multi-subagent trials used Agent tool calls that spawn subagents,
    each with their own turn budgets. A single session with 30 turns gets far
    fewer actual tool calls than a multi-subagent session with 30 orchestrator turns.
Root cause: Single-session mode inherited a max-turns constant designed for the
  orchestrator in multi-subagent mode. The orchestrator's 30 turns expand to
  100+ tool calls across subagents. Single-session gets exactly 30 tool calls.
Proposed change: Increase DEFAULT_MAX_TURNS from 30 to 100 for the single-session
  fork. This matches the effective turn budget that multi-subagent mode provides.
  100 turns gives the agent enough room for exploration-heavy tasks while still
  bounding runaway loops.
Predicted outcome:
  - raman-fitting: 0/1 (single) -> 50%+ (enough turns to explore data)
  - write-compressor: stays at 100% (task completes in <30 turns, extra turns unused)
  - overfull-hbox: stays at 100% (same reasoning)
Generalization argument: "Any coding agent in single-session mode needs a turn budget
  proportional to the total tool calls it would make in multi-agent mode. When
  consolidating N specialist agents into 1 generalist, the turn budget must scale
  by roughly N to maintain equivalent exploration capacity."
```

## SCOPE

Test tasks:
1. **raman-fitting** — target task, currently 0% in single-session mode due to turn cap
2. **write-compressor** — regression check, currently 100% in single-session mode (opus-4-6)

NOT tested on:
- **mteb-retrieve** — infra/download issue, not turn-cap related
- **overfull-hbox** — regression check deferred to reduce trial count
- Hold-out tasks (gpt2-codegolf, dna-assembly, cancel-async-tasks)

## CHANGE

Type: CONFIGURATION (one constant value, not a prompt or structural change)

Files changed:
- `terminal_bench_2/autofyn_agent_single/constants.py` — `DEFAULT_MAX_TURNS` changed from 30 to 100

```diff
--- a/terminal_bench_2/autofyn_agent_single/constants.py
+++ b/terminal_bench_2/autofyn_agent_single/constants.py
-DEFAULT_MAX_TURNS: int = 30
+DEFAULT_MAX_TURNS: int = 100
```

The constant flows through `harbor_agent.py` -> `build_cli_command()` -> `--max-turns` CLI flag.
The adapter also reads `AUTOFYN_MAX_TURNS` env var as override — this provides a rollback path
if 100 is too high.

## MEASUREMENT PLAN

- Run each task 1x with the change (model: opus-4-6, as set in run_experiment.sh)
- raman-fitting: baseline 0/1 (single) -> target 1/1
- write-compressor: must stay at 1.0 (regression guard)
- Monitor whether increased turns cause cost/time regressions on passing tasks

Risk: More turns could cause the agent to over-iterate on already-solved tasks, wasting
budget. Mitigated by the fact that Claude naturally stops when work is done (it commits
and signals completion). The extra turns are a ceiling, not a floor.

## RESULTS

### Trial 1: raman-fitting

| Field | Value |
|-------|-------|
| Job ID | single-20260414-071341 |
| Trial ID | raman-fitting__KVAwM9B |
| Reward | 0.0 |
| Tool calls used | 14 turns (well within 100 cap) |
| Duration | ~82s agent execution |
| Outcome | FAIL |

**What happened:** Agent completed in only 14 turns. It attempted a wavenumber conversion
but still produced wrong fitting parameters (x0=3745 for G peak vs expected ~1580 cm-1).
The agent referenced cm-1 units but used incorrect transformation logic. This is an
approach-quality failure, not a turn-cap failure. More turns did not help because the
agent naturally stopped at 14 turns after producing (wrong) results.

### Trial 2: write-compressor

| Field | Value |
|-------|-------|
| Job ID | single-20260414-072337 |
| Trial ID | write-compressor__oABfvjR |
| Reward | 0.0 |
| Exception | AgentTimeoutError (900s task timeout) |
| Duration | 900s (timed out) |
| Outcome | FAIL — REGRESSION |

**What happened:** The agent timed out at the 900s task budget. No events.jsonl was
produced (agent was still running when Harbor killed it). This is the same failure mode
that single-session was designed to fix (EXP-05). The 100-turn budget likely allowed the
agent to keep running iterations past the point where it would have naturally stopped
with 30 turns, consuming all available time budget before completing.

### Summary table

| Task | Baseline (single, 30 turns) | EXP-07 (single, 100 turns) | Delta |
|------|-----------------------------|------------------------------|-------|
| raman-fitting | 0/1 (0%) | 0/1 (0%) | No improvement |
| write-compressor | 3/3 (100%) | 0/1 (0%) | **REGRESSION** |

### Observations

1. **Hypothesis was wrong for raman-fitting**: The 30-turn cap was not the binding
   constraint. The agent completed in 14 turns with 100 turns available. The failure
   is approach quality — the agent applies an incorrect wavenumber transformation even
   with unlimited budget. This contradicts the architect's analysis that the single-session
   trial "hit --max-turns 30 cap."

2. **Critical regression on write-compressor**: The 100-turn budget caused write-compressor
   to time out. With 30 turns, the agent completed the task in time (3/3 passes). With
   100 turns, the agent over-iterated and consumed the entire 900s budget. The spec's
   "risk" section noted this but predicted it would be mitigated by the agent naturally
   stopping when done — that prediction was wrong.

3. **Turn budget vs task budget are in tension**: Tight-budget tasks (900s) need the
   agent to complete quickly. A higher turn ceiling enables more turns, which takes more
   wall-clock time. For tasks already passing with 30 turns, increasing to 100 turns
   introduces a new failure mode.

4. **The failing raman-fitting trial (vjzY8wS) used 26 tool calls**: The architect
   attributed this to the 30-turn cap. But this EXP-07 trial used only 14 turns with a
   100-turn cap. This suggests the 26-turn trial also terminated naturally (not cap-bound),
   and the architect's diagnosis was incorrect.

## VERDICT

```
VERDICT: NO-GO — revert to DEFAULT_MAX_TURNS=30
Reason:
  - Increasing to 100 turns caused a regression on write-compressor (0/1, timeout)
    where baseline was 3/3 (100%). The risk prediction was wrong: the agent does NOT
    naturally stop when done on this task — it over-iterates with a larger budget.
  - raman-fitting was not fixed: agent used 14/100 turns and still produced wrong
    results. The failure mode is approach quality, not turn budget.
  - Net: 0/2 tasks improved, 1/2 tasks regressed. Change is harmful.
Action: Revert DEFAULT_MAX_TURNS from 100 to 30.
Next step: raman-fitting failure requires prompt-level intervention to teach the
  agent the nm-to-wavenumber unit conversion, not a higher turn budget.
```

## STATUS

- [x] Fork created: `autofyn_agent_single/`
- [x] Change implemented (DEFAULT_MAX_TURNS: 30 -> 100)
- [x] Trial 1 (raman-fitting) completed — FAIL
- [x] Trial 2 (write-compressor) completed — FAIL (REGRESSION)
- [x] Results recorded
- [x] Verdict issued — NO-GO, revert
