# EXP-12: CWD Fix 2 — Infrastructure-Level Working Directory Detection

## HYPOTHESIS

```
Target failure mode: Infrastructure crash on non-/app containers (prove-plus-comm)
  AND prompt regression on /app containers (write-compressor)
Evidence:
  - EXP-10: prove-plus-comm 0/2 (exec_as_agent crash when cwd="/app" doesn't exist)
  - EXP-11 cwdfix: prove-plus-comm 2/2 (fixed) but write-compressor 0/3 (regressed)
  - Regression cause: prompt changes (discovery step, /app removal) altered agent approach
Root cause: CWD detection was done in the PROMPT layer (cwdfix), which polluted
  agent behavior. It should be in the INFRASTRUCTURE layer (harbor_agent.py).
Proposed change:
  1. Add _resolve_task_cwd() to harbor_agent.py — probes container for first
     existing candidate dir from [/app, /workspace, /home/user, /root, /]
  2. Use resolved CWD instead of static TASK_CWD for exec_as_agent cwd=
  3. Keep ALL prompts identical to single-session (no discovery step, /app refs stay)
Predicted outcome:
  - write-compressor: 2/2 pass (same as baseline 75%, prompts unchanged)
  - prove-plus-comm: 2/2 pass (infra finds /workspace, agent adapts from pwd output)
Generalization argument: "Infrastructure problems deserve infrastructure fixes.
  Prompt-layer workarounds pollute the agent's cognitive context and regress
  tasks that were working. Moving CWD detection to harbor_agent.py is zero-cost
  for /app tasks and fixes non-/app tasks without touching any prompt."
```

## Changes From Single-Session Fork

| File | Change |
|---|---|
| `constants.py` | No change (TASK_CWD="/app" stays, unused) |
| `prompts/*` | No changes (byte-identical to autofyn_agent_single) |
| `orchestrator.py` | No change |
| `pyproject.toml` | Name updated to `autofyn-terminal-bench-cwdfix2` |

## Shared Infrastructure Change (adapters/harbor_agent.py)

Added `CWD_PROBE_DIRS` module constant and `_resolve_task_cwd()` method:

```python
CWD_PROBE_DIRS: list[str] = ["/app", "/workspace", "/home/user", "/root", "/"]

async def _resolve_task_cwd(self, environment: BaseEnvironment) -> str:
    dirs_str = " ".join(CWD_PROBE_DIRS)
    probe_script = f'for d in {dirs_str}; do [ -d "$d" ] && echo "$d" && break; done'
    result = await self.exec_as_agent(environment, probe_script)
    stdout = (result.stdout or "").strip()
    if stdout:
        return stdout.splitlines()[0]
    return "/"
```

Key design decisions:
- Uses `[ -d "$d" ]` (existence check only) — /app does NOT exist on /workspace containers
  (different base image), so existence check is sufficient without non-empty check
- Probes /app FIRST — /app tasks get /app as CWD (matching prompt references)
- Probe runs WITHOUT cwd= parameter — uses container WORKDIR default (same pattern as _find_claude_bin)
- One exec_as_agent call, <1s overhead, invisible to prompts
- Probe script built from CWD_PROBE_DIRS constant (DRY)

## Decision Criteria

- write-compressor 2/2: GO — no regression, run prove-plus-comm
- write-compressor 1/2: BORDERLINE — run 2 more trials (n=4)
- write-compressor 0/2: NO-GO — infrastructure fix insufficient, deeper prompt issues remain
- prove-plus-comm 2/2: fix confirmed
- prove-plus-comm 0/2 or 1/2: agent cannot adapt from /workspace when prompt references /app

## Results

### write-compressor (regression check)

| Trial | Job ID | Result | Time | Notes |
|---|---|---|---|---|
| 1 | cwdfix2-20260414-124256 | 0.0 | 15m 20s | AgentTimeoutError (900s budget) |
| 2 | cwdfix2-20260414-125837 | 0.0 | 15m 18s | AgentTimeoutError (900s budget) |

**write-compressor score: 0/2 = 0%**

### prove-plus-comm (fix validation)

Not run — decision criteria requires write-compressor 1+/2 to proceed. At 0/2, this is NO-GO.

## VERDICT

```
VERDICT: NO-GO (write-compressor regression persists)
Reason: write-compressor 0/2 (0%) — both trials timed out at 900s. This matches
  the EXP-11 cwdfix pattern (0/3 = 0%) despite reverting ALL prompt changes.
  Only the pyproject.toml name and the infrastructure harbor_agent.py probe
  differ from single-session. Prompts are byte-identical to single-session baseline.
Surprising finding: Moving CWD detection to infrastructure (harbor_agent.py) and
  keeping prompts byte-identical to the working single-session fork (3/4=75%)
  did NOT fix the write-compressor regression. The regression is NOT caused by
  the prompt discovery step or /app reference removal.
Root cause hypothesis: The regression may be caused by something shared between
  cwdfix and cwdfix2 forks that differs from single-session. The only shared change
  between the two failing forks is harbor_agent.py itself — both use the same adapter.
  However, cwdfix2 adds a new harbor_agent.py change (the probe). The single-session
  baseline used TASK_CWD="/app" directly without probing.
Alternative hypothesis: The 900s harbor timeout is a hard cap regardless of agent
  speed. The single-session 3/4 pass rate may reflect task-specific variance where
  write-compressor occasionally solves quickly (<900s). The cwdfix2 probe adds ~1s
  overhead which should be irrelevant. More likely: task difficulty is borderline
  at the 900s limit and small implementation differences (e.g., extra log output
  from the probe) may affect token budget or scheduling.
Next step: Run single-session baseline again at n=2 to confirm it still passes
  at 75%+. If single-session also regresses, the issue is environmental (model
  changes, infra changes), not fork-specific.
```
