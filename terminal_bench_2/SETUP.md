# Terminal-Bench 2 — Environment Setup

## Paths

| What | Where |
|------|-------|
| Harbor binary (NOT in PATH) | `/home/agentuser/.local/bin/harbor` |
| Working directory | `/home/agentuser/repo/terminal_bench_2` |
| Tasks | `/home/agentuser/repo/terminal_bench_2/tasks/tasks-run2` |

## Env vars

Already set in sandbox — pass through, do not hardcode:

```
DAYTONA_API_KEY
CLAUDE_CODE_OAUTH_TOKEN
```

---

## Installing a new agent fork

Each new agent directory needs a one-time pip install before harbor can import it:

```bash
pip install -e /home/agentuser/repo/terminal_bench_2/<your_agent_dir>
```

The base `autofyn_agent` is already installed. Only run this when creating a new fork.

---

## Running an experiment

```bash
cd /home/agentuser/repo/terminal_bench_2 && \
DAYTONA_API_KEY=$DAYTONA_API_KEY \
CLAUDE_CODE_OAUTH_TOKEN=$CLAUDE_CODE_OAUTH_TOKEN \
/home/agentuser/.local/bin/harbor run \
  --agent-import-path terminal_bench.agent:AutoFynAgent \
  --model anthropic/claude-opus-4-5 \
  --path /home/agentuser/repo/terminal_bench_2/tasks/tasks-run2 \
  --env daytona \
  -k 1 \
  -n 3 \
  --jobs-dir /home/agentuser/repo/terminal_bench_2/<your_agent_dir>/jobs \
  --include-task-name <task1> \
  --include-task-name <task2> \
  > /tmp/harbor-<exp>.log 2>&1
```

**Key flags:**
- `-k 1` — 1 trial per task; use `-k 3` for validation
- `-n 3` — 3 concurrent workers
- `--include-task-name` — repeat per task; omit to run all 14 (expensive, avoid)

**Always set `run_in_background: true` on the Bash tool call.**

---

## Harbor produces no output while running

Harbor buffers everything. You will see nothing for 10–20 minutes per task. **This is normal. Do not re-run.**

Check it's alive:
```bash
ps aux | grep harbor
```

Tail the log:
```bash
tail -f /tmp/harbor-<exp>.log
```

---

## Reading results

```bash
python3 -c "
import json, glob
for f in glob.glob('/home/agentuser/repo/terminal_bench_2/<your_agent_dir>/jobs/**/**/result.json', recursive=True):
    d = json.load(open(f))
    print(d.get('score', '?'), d.get('task_name', '?'))
"
```

---

## Common mistakes

- **`harbor` not in PATH** — always use the full path `/home/agentuser/.local/bin/harbor`
- **Relative `--path`** — harbor can't find tasks; always use the absolute path
- **Running from repo root** — must `cd /home/agentuser/repo/terminal_bench_2` first
- **No log redirect** — harbor will block your tool call with no output; always redirect to `/tmp/harbor-*.log`
- **Re-running on empty output** — harbor is running; check `ps aux`, don't re-run
