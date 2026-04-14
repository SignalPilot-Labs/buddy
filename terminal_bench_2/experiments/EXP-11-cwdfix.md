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

## VERDICT

```
VERDICT: GO (conditional on write-compressor validation)
Reason: prove-plus-comm fixed from 0/2 crash to 2/2 pass. write-compressor
  n=1 timeout is within baseline variance (single-session was 3/4). Need n=2+
  more write-compressor trials to confirm no regression from discovery step.
Generalization: "An agent that discovers its working directory dynamically
  works on any container layout. Hardcoding paths is a reliability bug."
Risk: "Discovery step could add enough overhead to regress tight-budget tasks
  if the 5s overhead compounds with slow LLM starts."
```
