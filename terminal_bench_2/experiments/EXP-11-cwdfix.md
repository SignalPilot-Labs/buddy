# EXP-11: CWD Fix — Dynamic Working Directory Discovery

## HYPOTHESIS

```
Target failure mode: Agent bootstrap crash — `cd: /app: No such file or directory`
Evidence:
  - EXP-10: prove-plus-comm scored 0.0 in both trials (25s and 15s — instant crash)
  - harbor_agent.py:88 calls exec_as_agent(cwd=TASK_CWD) where TASK_CWD="/app"
  - prove-plus-comm container uses WORKDIR /workspace (not /app)
  - Caveman fork passed prove-plus-comm by using _run_agent_commands which does NOT pass cwd
Root cause: TASK_CWD="/app" hardcoded in constants.py prevents the agent from starting
  on any task container whose WORKDIR is not /app.
Proposed change:
  1. Set TASK_CWD="/" in constants.py — root always exists, bootstrap never crashes.
  2. Add discovery step 0 in single_session.md: probe /workspace /app /home/user /root .
     using [ "$(ls -A "$d" 2>/dev/null)" ] (non-empty check, not just directory existence).
  3. Remove all hardcoded /app references from single_session.md, system.md, builder.md.
Predicted outcome:
  - prove-plus-comm: 100% (2/2 trials) — agent now reaches /workspace and runs Coq proof
  - write-compressor, overfull-hbox: unchanged — /app still discovered via discovery step
```

## Changes From Single-Session Fork

| File | Change |
|---|---|
| `constants.py` | `TASK_CWD="/app"` → `TASK_CWD="/"` |
| `prompts/single_session.md` | Added step 0 (discovery), removed all `/app` hardcodes |
| `prompts/system.md` | Added step 0 (discovery), removed all `/app` hardcodes |
| `prompts/subagents/builder.md` | Replaced `ls /app/test*` with `ls test* *test*` |
| `pyproject.toml` | Name updated to `autofyn-terminal-bench-cwdfix` |

## Discovery Step

```bash
for d in /workspace /app /home/user /root .; do
  [ "$(ls -A "$d" 2>/dev/null)" ] && echo "FOUND: $d" && break
done
```

Key design decisions:
- Uses `[ "$(ls -A ...)" ]` not `[ -d ... ]` — avoids false positives from empty dirs
- Probes `/workspace` first (prove-plus-comm pattern)
- Falls back to `.` (current dir, resolves to `/` from TASK_CWD) as last resort
- `/root` added to cover minimal Docker images with `/root` as WORKDIR

## Results

### prove-plus-comm (2 trials)

| Trial | Job ID | Result | Time | Notes |
|---|---|---|---|---|
| 1 | cwdfix-20260414-113801 | 1.0 | 56s | Agent discovered /workspace, completed Coq proof |
| 2 | cwdfix-20260414-113903 | 1.0 | 48s | Same — consistent result |

### Summary

| Metric | Value |
|---|---|
| prove-plus-comm score | 2/2 = 100% |
| Bootstrap crash | Fixed — agent starts at `/`, discovers `/workspace` |
| EXP-10 comparison | Was 0/2 (instant crash) → now 2/2 (full success) |

### write-compressor regression check (1 trial)

| Trial | Job ID | Result | Time | Notes |
|---|---|---|---|---|
| 1 | cwdfix-20260414-114104 | 0.0 | 15m 19s | AgentTimeoutError (900s budget) |

Note: single-session fork had 3/4 pass rate on write-compressor (1 timeout in 4 trials = 25% timeout rate). A single timeout at n=1 is within expected variance and does not confirm regression. The discovery step adds ~5s overhead which should not be the cause of a 900s timeout.

### write-compressor regression check (Round 13 — 2 more trials, n=3 total)

| Trial | Job ID | Result | Time | Notes |
|---|---|---|---|---|
| 2 | cwdfix-20260414-120218 | 0.0 | 15m 20s | AgentTimeoutError (900s budget) |
| 3 | cwdfix-20260414-121805 | 0.0 | 15m 20s | AgentTimeoutError (900s budget) |

**Combined write-compressor score: 0/3 = 0%** (all three trials timed out at 900s)

Baseline single-session was 3/4 = 75%. cwdfix at 0/3 = confirmed regression.

Observation: The write-compressor task description already contains `/app/decomp.c` references in the
prompt itself (task.yaml `instruction`), so the cwdfix discovery step is not the failure cause — the
agent is finding `/app` correctly. The timeouts appear to be caused by the complexity of the
write-compressor task itself (range coding + LZ77 reverse engineering) exhausting the 900s budget.
However, since the baseline single-session fork achieved 3/4 on this exact task, something in the
cwdfix agent changes (discovery step overhead, prompt wording changes, or cwd difference "/" vs "/app")
must be degrading performance. Phase 2 NOT run per stop criteria.

## VERDICT

```
VERDICT: NO-GO (write-compressor regression confirmed)
Reason: write-compressor 0/3 (0%) vs baseline 3/4 (75%). All three trials
  timed out at 900s. Phase 2 swing tasks not run per decision protocol.
Root cause hypothesis: cwdfix starts at TASK_CWD="/" and the discovery step
  adds overhead and context that may shift the agent's approach. The agent
  may be spending time on the discovery loop and subsequent cd, then hitting
  the 900s limit before solving the complex compression algorithm.
  Alternatively, prompt changes to system.md/single_session.md that removed
  /app references may have changed the agent's initial approach to the task.
Next step: Identify what changed between single-session (3/4) and cwdfix
  (0/3) for write-compressor. Compare prompts. Consider targeted fix:
  - Option A: Start TASK_CWD at task-specific CWD from task.yaml WORKDIR
  - Option B: Keep cwdfix but optimize discovery to be faster/less intrusive
  - Option C: Revert TASK_CWD change, only fix discovery for non-/app tasks
```
