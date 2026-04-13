# Terminal-Bench Run 2 — AutoFyn vs claude-opus-4-5

## Goal

Full re-run of all 14 tasks with `claude-opus-4-5`, replacing `train-fasttext` (4x NonZeroAgentExitCodeError) with `fix-code-vulnerability`, `write-compressor`, and `cancel-async-tasks`.

## Changes from Run 1

| Change | Run 1 | Run 2 |
|--------|-------|-------|
| Model | claude-opus-4-6 | claude-opus-4-5 |
| Concurrency | `-n 3` | `-n 24` |
| train-fasttext | included | replaced with 3 hard 15-min tasks |

## Tasks (14 total, 4 trials each = 56 trials)

| Task | Difficulty | Agent Timeout | Expert Time |
|------|-----------|--------------|-------------|
| fix-git | easy | 15 min | 5 min |
| cobol-modernization | easy | 15 min | 20 min |
| overfull-hbox | easy | 12 min | 60 min |
| prove-plus-comm | easy | 15 min | 5 min |
| filter-js-from-html | medium | 30 min | 45 min |
| raman-fitting | medium | 15 min | 5 min |
| mteb-retrieve | medium | 30 min | 15 min |
| regex-log | medium | 15 min | 45 min |
| sqlite-db-truncate | medium | 15 min | 60 min |
| dna-assembly | hard | 30 min | 60 min |
| gpt2-codegolf | hard | 15 min | 2400 min |
| fix-code-vulnerability | hard | 15 min | — |
| write-compressor | hard | 15 min | — |
| cancel-async-tasks | hard | 15 min | — |

## Run Command

```bash
DAYTONA_API_KEY=<key> CLAUDE_CODE_OAUTH_TOKEN=<token> harbor run \
  --agent-import-path terminal_bench.agent:AutoFynAgent \
  --model anthropic/claude-opus-4-5 \
  --path tasks-run2 \
  --env daytona \
  -k 4 -n 24 -y
```

## Expected Duration

56 trials at `-n 24`. Longest timeout is 30 min (`mteb-retrieve`, `dna-assembly`).

**Estimated wall time: ~1h**

## Results

**Job:** `jobs-run2/2026-04-10__14-43-50`
**Trials:** 55 scored, 9 errors — **Mean score: 0.482** (27/56 on 14 tasks)

| Task | Score | Errors |
|------|-------|--------|
| fix-git | 4/4 (100%) | — |
| cobol-modernization | 4/4 (100%) | — |
| regex-log | 4/4 (100%) | — |
| sqlite-db-truncate | 4/4 (100%) | — |
| dna-assembly | 3/4 (75%) | — |
| write-compressor | 3/4 (75%) | 3x AgentTimeoutError¹ |
| cancel-async-tasks | 3/4 (75%) | — |
| overfull-hbox | 1/4 (25%) | 2x AgentTimeoutError |
| raman-fitting | 1/4 (25%) | — |
| filter-js-from-html | 0/3 (0%) | 1x VerifierTimeoutError |
| mteb-retrieve | 0/4 (0%) | 4x AgentTimeoutError |
| gpt2-codegolf | 0/4 (0%) | 4x AgentTimeoutError |
| fix-code-vulnerability | 0/4 (0%) | 4x AgentTimeoutError |
| prove-plus-comm | 0/4 (0%) | 4x NonZeroAgentExitCodeError |

### Error Types
- **AgentTimeoutError (17)** — agent ran out of time. `gpt2-codegolf`, `mteb-retrieve`, `fix-code-vulnerability` timed out on all trials; `overfull-hbox` on 2 of 4. Notably, 3 `write-compressor` trials also timed out but the agent had already written enough code for the verifier to pass — scored 1.0 despite the timeout.
- **NonZeroAgentExitCodeError (4)** — `prove-plus-comm`: Claude CLI process crashed on all 4 trials. Same infrastructure issue as Run 1. Scored 0.
- **VerifierTimeoutError (1)** — `filter-js-from-html`: verifier timed out on one trial. Not counted in the score (3 valid trials, 0 passed).
- **RewardFileNotFoundError (8)** — `hello-world` and `hello-world-2` smoke tests: verifier reward file not produced. Excluded from the 14-task score.

### Notes
- `write-compressor` is the standout result: 3 of the 4 passes were **AgentTimeoutError + reward 1.0** — the agent ran past the timeout but had already produced a working solution. Without caveman, the agent wrote enough code in time to pass but didn't finish cleanly.
- `prove-plus-comm` crashed again (4x NonZeroAgentExitCodeError), same as Run 1. This is what Run 3's caveman strategy was designed to fix.
- `dna-assembly` improved significantly from Run 1 (1/1 → 3/4), suggesting the Run 1 result wasn't a fluke even with more trials.

¹ Agent timed out but had already produced a correct solution; verifier scored it 1.0.
