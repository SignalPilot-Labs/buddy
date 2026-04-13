# AutoFyn Leaderboard — Task-Subset Comparison

Benchmark agents are scored on **only the tasks AutoFyn ran**, so the comparison is apples-to-apples. Only agents with results for all tasks in a given set are included.

---

## Summary

| Run | Model | Task Set | AutoFyn Score | Field Rank |
|-----|-------|----------|:-------------:|:----------:|
| Run 1 | claude-opus-4-6 | 14 tasks (original) | **42.9%** (6.0/14) | **13 / 33** |
| Run 2 | claude-opus-4-5 | 14 tasks (modified) | **48.2%** (6.75/14) | **22 / 33** |
| Run 3 | claude-opus-4-6 (post-nerf) | 14 tasks (modified) | **37.5%** (5.25/14) | **24 / 33** |
| Run 4 | claude-opus-4-5 + caveman | 14 tasks (modified) | **50.0%** (7.0/14) | **18 / 33** |

> Runs 2–4 use the same task set (dropped `video-processing`, `sam-cell-seg`, `train-fasttext`; added `fix-code-vulnerability`, `write-compressor`, `cancel-async-tasks`). Run 3 tested `claude-opus-4-6` on the same setup as Run 2 and revealed a model regression — Anthropic appears to have updated the model in the 2nd week of April, degrading its coding performance. Run 4 reverted to `claude-opus-4-5` and added the caveman token-save strategy.

---

## Run 1 — claude-opus-4-6 (original 14 tasks)

**AutoFyn: 42.9% — Rank 13/33**

> 11 of 24 errors were DaytonaErrors (sandbox failed to start due to disk limits at `-n 3` concurrency). Daytona's resource limits were increased in subsequent runs to fix this. The leaderboard score uses valid trials only, so the 42.9% reflects actual agent performance — but the mean (32.1%) is dragged down by those dead trials.

| Rank | Agent | Model | Org | Score | Overall |
|------|-------|-------|-----|:-----:|:-------:|
| 1 | ForgeCode | GPT-5.4 | ForgeCode | 67.1% | 81.8% |
| 2 | Ante | Gemini 3 Pro | Antigma Labs | 57.7% | 69.4% |
| 3 | Crux | Claude Opus 4.6 | Roam | 57.1% | 66.9% |
| 4 | Simple Codex | GPT-5.3-Codex | OpenAI | 54.3% | 75.1% |
| 5 | MAYA-V2 | Claude 4.6 Opus | ADYA | 50.0% | 72.1% |
| 5 | OpenCode | Claude Opus 4.5 | Anomaly Innovations | 50.0% | 51.7% |
| 7 | Abacus AI Desktop | Multiple | Abacus.AI | 48.6% | 58.4% |
| 7 | Terminus-KIRA | Gemini 3.1 Pro | KRAFTON AI | 48.6% | 74.8% |
| 9 | Droid | GPT-5.3-Codex | Factory | 47.1% | 77.3% |
| 9 | Junie CLI | Gemini 3 Flash | JetBrains | 47.1% | 64.3% |
| 11 | SageAgent | GPT-5.3-Codex | OpenSage | 45.7% | 78.4% |
| 11 | TongAgents | Gemini 3.1 Pro | BIGAI | 45.7% | 80.2% |
| **13** | **AutoFyn** | **claude-opus-4-6** | **AutoFyn** | **42.9%** | **—** |
| 13 | Capy | Claude Opus 4.6 | Capy | 42.9% | 75.3% |
| 13 | II-Agent | Gemini 3 Pro | Intelligent Internet | 42.9% | 61.8% |
| 16 | CodeBrain-1 | GPT-5.3-Codex | Feeling AI | 41.4% | 70.3% |
| 17 | Deep Agents | GPT-5.2-Codex | LangChain | 40.0% | 66.5% |
| 17 | IndusAGI Coding Agent | GPT-5.3-Codex | Varun Israni | 40.0% | 69.1% |
| 19 | Letta Code | Claude Opus 4.5 | Letta | 38.6% | 59.1% |
| 20 | Warp | Multiple | Warp | 37.1% | 61.2% |
| 21 | Mux | GPT-5.3-Codex | Coder | 35.7% | 74.6% |
| 22 | CAMEL-AI | Claude Sonnet 4.5 | CAMEL-AI | 32.9% | 46.5% |
| 23 | grok-cli | Grok 4.20 Reasoning | Vibe Kit | 30.7% | 57.3% |
| 24 | spoox-m | GPT-5-Mini | TUM | 30.0% | 34.8% |
| 25 | cchuter | minimax-m2.5 | teamblobfish.com | 26.1% | 42.7% |
| 26 | Dakou Agent | Qwen 3 Coder 480B | iflow | 25.7% | 27.2% |
| 26 | Goose | Claude Opus 4.5 | Block | 25.7% | 54.3% |
| 28 | Gemini CLI | Gemini 3 Flash | Google | 24.3% | 47.4% |
| 29 | Claude Code | Claude Opus 4.6 | Anthropic | 20.0% | 58.0% |
| 30 | Codex CLI | GPT-5.2 | OpenAI | 11.4% | 62.9% |
| 30 | OpenHands | Claude Opus 4.5 | OpenHands | 11.4% | 51.9% |
| 32 | Mini-SWE-Agent | Claude Sonnet 4.5 | Princeton | 2.9% | 42.5% |
| 33 | Terminus 2 | GPT-5.3-Codex | AfterQuery | 1.4% | 64.7% |

### Per-Task: Run 1

| Task | Diff | AutoFyn | ForgeCode | Ante | Crux | Simple Codex | MAYA-V2 |
|------|------|:-------:|:---------:|:----:|:----:|:------------:|:-------:|
| fix-git | easy | 100% | 100% | 100% | 100% | 100% | 100% |
| cobol-modernization | easy | 100% | 100% | 100% | 100% | 100% | 100% |
| overfull-hbox | easy | 100%¹ | 100% | 100% | 60% | 100% | 0% |
| prove-plus-comm | easy | **0%**² | 100% | 100% | 100% | 100% | 0% |
| regex-log | medium | 100% | 100% | 100% | 50% | 100% | 100% |
| sqlite-db-truncate | medium | 100%¹ | 100% | 100% | 100% | 100% | 0% |
| dna-assembly | hard | 100%¹ | 40% | 60% | 20% | 80% | 0% |
| filter-js-from-html | medium | 0% | 0% | 0% | 20% | 0% | 100% |
| raman-fitting | medium | 0% | 0% | 10% | 75% | 0% | 100% |
| mteb-retrieve | medium | 0% | 100% | 78% | 25% | 40% | 0% |
| video-processing | hard | 0% | 100% | 40% | 40% | 40% | 0% |
| gpt2-codegolf | hard | 0% | 80% | 10% | 50% | 0% | 100% |
| train-fasttext | hard | **0%**² | 0% | 10% | 0% | 0% | 100% |
| sam-cell-seg | hard | 0% | 20% | 0% | 60% | 0% | 0% |
| **Total** | | **42.9%** | **67.1%** | **57.7%** | **57.1%** | **54.3%** | **50.0%** |

¹ Fewer valid trials than 4 (remaining were DaytonaError infra failures); shown score is on valid trials only.  
² Zero valid trials — all trials were infra crashes (NonZeroAgentExitCodeError or DaytonaError). Score treated as 0.

---

## Run 2 — claude-opus-4-5 (modified 14 tasks)

**AutoFyn: 48.2% — Rank 22/33**

Same task set as Run 3. No caveman strategy. The field is identical to Run 3's leaderboard — only AutoFyn's row changes.

| Rank | Agent | Model | Org | Score | Overall |
|------|-------|-------|-----|:-----:|:-------:|
| 1 | Ante | Gemini 3 Pro | Antigma Labs | 74.8% | 69.4% |
| 2 | Terminus-KIRA | Gemini 3.1 Pro | KRAFTON AI | 68.6% | 74.8% |
| 3 | SageAgent | GPT-5.3-Codex | OpenSage | 67.1% | 78.4% |
| 3 | Simple Codex | GPT-5.3-Codex | OpenAI | 67.1% | 75.1% |
| 5 | Crux | Claude Opus 4.6 | Roam | 66.1% | 66.9% |
| 6 | ForgeCode | GPT-5.4 | ForgeCode | 65.7% | 81.8% |
| 6 | Junie CLI | Gemini 3 Flash | JetBrains | 65.7% | 64.3% |
| 8 | Abacus AI Desktop | Multiple | Abacus.AI | 64.3% | 58.4% |
| 8 | Droid | GPT-5.3-Codex | Factory | 64.3% | 77.3% |
| 10 | II-Agent | Gemini 3 Pro | Intelligent Internet | 61.4% | 61.8% |
| 10 | TongAgents | Gemini 3.1 Pro | BIGAI | 61.4% | 80.2% |
| 12 | Capy | Claude Opus 4.6 | Capy | 58.6% | 75.3% |
| 12 | CodeBrain-1 | GPT-5.3-Codex | Feeling AI | 58.6% | 70.3% |
| 14 | OpenCode | Claude Opus 4.5 | Anomaly Innovations | 57.1% | 51.7% |
| 15 | IndusAGI Coding Agent | GPT-5.3-Codex | Varun Israni | 54.3% | 69.1% |
| 16 | Letta Code | Claude Opus 4.5 | Letta | 51.4% | 59.1% |
| 16 | Warp | Multiple | Warp | 51.4% | 61.2% |
| 18 | Deep Agents | GPT-5.2-Codex | LangChain | 50.0% | 66.5% |
| 18 | MAYA-V2 | Claude 4.6 Opus | ADYA | 50.0% | 72.1% |
| 18 | Mux | GPT-5.3-Codex | Coder | 50.0% | 74.6% |
| 21 | grok-cli | Grok 4.20 Reasoning | Vibe Kit | 48.6% | 57.3% |
| **22** | **AutoFyn** | **claude-opus-4-5** | **AutoFyn** | **48.2%** | **—** |
| 23 | spoox-m | GPT-5-Mini | TUM | 41.4% | 34.8% |
| 24 | CAMEL-AI | Claude Sonnet 4.5 | CAMEL-AI | 40.0% | 46.5% |
| 25 | cchuter | minimax-m2.5 | teamblobfish.com | 37.5% | 42.7% |
| 26 | Goose | Claude Opus 4.5 | Block | 32.9% | 54.3% |
| 27 | Dakou Agent | Qwen 3 Coder 480B | iflow | 30.0% | 27.2% |
| 28 | Claude Code | Claude Opus 4.6 | Anthropic | 28.6% | 58.0% |
| 29 | Gemini CLI | Gemini 3 Flash | Google | 27.1% | 47.4% |
| 30 | Codex CLI | GPT-5.2 | OpenAI | 14.3% | 62.9% |
| 31 | OpenHands | Claude Opus 4.5 | OpenHands | 12.9% | 51.9% |
| 32 | Mini-SWE-Agent | Claude Sonnet 4.5 | Princeton | 5.7% | 42.5% |
| 33 | Terminus 2 | GPT-5.3-Codex | AfterQuery | 2.6% | 64.7% |

### Per-Task: Run 2

| Task | Diff | AutoFyn | Ante | Terminus-KIRA | SageAgent | Simple Codex | Crux |
|------|------|:-------:|:----:|:-------------:|:---------:|:------------:|:----:|
| fix-git | easy | 100% | 100% | 100% | 100% | 100% | 100% |
| cobol-modernization | easy | 100% | 100% | 100% | 100% | 100% | 100% |
| overfull-hbox | easy | 25% | 100% | 100% | 100% | 100% | 60% |
| prove-plus-comm | easy | 0%¹ | 100% | 100% | 100% | 100% | 100% |
| regex-log | medium | 100% | 100% | 100% | 100% | 100% | 50% |
| sqlite-db-truncate | medium | 100% | 100% | 100% | 100% | 100% | 100% |
| raman-fitting | medium | 25% | 10% | 0% | 20% | 0% | 75% |
| filter-js-from-html | medium | 0% | 0% | 0% | 0% | 0% | 20% |
| mteb-retrieve | medium | 0% | 78% | 0% | 0% | 40% | 25% |
| dna-assembly | hard | 75% | 60% | 60% | 20% | 80% | 20% |
| cancel-async-tasks | hard | 75% | 100% | 100% | 100% | 20% | 100% |
| gpt2-codegolf | hard | 0% | 10% | 0% | 0% | 0% | 50% |
| fix-code-vulnerability | hard | 0% | 100% | 100% | 100% | 100% | 100% |
| write-compressor | hard | **75%** | 90% | 100% | 100% | 100% | 25% |
| **Total** | | **48.2%** | **74.8%** | **68.6%** | **67.1%** | **67.1%** | **66.1%** |

¹ All 4 trials were NonZeroAgentExitCodeError (Claude CLI crash). Scored 0 — same infra issue as Run 1; caveman fixed this in Run 3.

---

## Run 3 — claude-opus-4-6 post-nerf (modified 14 tasks)

**AutoFyn: 37.5% — Rank 24/33**

Same setup as Run 2, model swapped to `claude-opus-4-6`. Expected an improvement; got a regression. Anthropic appears to have updated `claude-opus-4-6` in the 2nd week of April — the model was noticeably slower and timed out on tasks that `claude-opus-4-5` handled comfortably within the same budgets (`dna-assembly`, `raman-fitting`). Run 4 reverts to opus-4-5.

| Rank | Agent | Model | Org | Score | Overall |
|------|-------|-------|-----|:-----:|:-------:|
| 1 | Ante | Gemini 3 Pro | Antigma Labs | 74.8% | 69.4% |
| 2 | Terminus-KIRA | Gemini 3.1 Pro | KRAFTON AI | 68.6% | 74.8% |
| 3 | SageAgent | GPT-5.3-Codex | OpenSage | 67.1% | 78.4% |
| 3 | Simple Codex | GPT-5.3-Codex | OpenAI | 67.1% | 75.1% |
| 5 | Crux | Claude Opus 4.6 | Roam | 66.1% | 66.9% |
| 6 | ForgeCode | GPT-5.4 | ForgeCode | 65.7% | 81.8% |
| 6 | Junie CLI | Gemini 3 Flash | JetBrains | 65.7% | 64.3% |
| 8 | Abacus AI Desktop | Multiple | Abacus.AI | 64.3% | 58.4% |
| 8 | Droid | GPT-5.3-Codex | Factory | 64.3% | 77.3% |
| 10 | II-Agent | Gemini 3 Pro | Intelligent Internet | 61.4% | 61.8% |
| 10 | TongAgents | Gemini 3.1 Pro | BIGAI | 61.4% | 80.2% |
| 12 | Capy | Claude Opus 4.6 | Capy | 58.6% | 75.3% |
| 12 | CodeBrain-1 | GPT-5.3-Codex | Feeling AI | 58.6% | 70.3% |
| 14 | OpenCode | Claude Opus 4.5 | Anomaly Innovations | 57.1% | 51.7% |
| 15 | IndusAGI Coding Agent | GPT-5.3-Codex | Varun Israni | 54.3% | 69.1% |
| 16 | Letta Code | Claude Opus 4.5 | Letta | 51.4% | 59.1% |
| 16 | Warp | Multiple | Warp | 51.4% | 61.2% |
| 18 | Deep Agents | GPT-5.2-Codex | LangChain | 50.0% | 66.5% |
| 18 | MAYA-V2 | Claude 4.6 Opus | ADYA | 50.0% | 72.1% |
| 18 | Mux | GPT-5.3-Codex | Coder | 50.0% | 74.6% |
| 21 | grok-cli | Grok 4.20 Reasoning | Vibe Kit | 48.6% | 57.3% |
| 22 | spoox-m | GPT-5-Mini | TUM | 41.4% | 34.8% |
| 23 | CAMEL-AI | Claude Sonnet 4.5 | CAMEL-AI | 40.0% | 46.5% |
| **24** | **AutoFyn** | **claude-opus-4-6 (post-nerf)** | **AutoFyn** | **37.5%** | **—** |
| 24 | cchuter | minimax-m2.5 | teamblobfish.com | 37.5% | 42.7% |
| 26 | Goose | Claude Opus 4.5 | Block | 32.9% | 54.3% |
| 27 | Dakou Agent | Qwen 3 Coder 480B | iflow | 30.0% | 27.2% |
| 28 | Claude Code | Claude Opus 4.6 | Anthropic | 28.6% | 58.0% |
| 29 | Gemini CLI | Gemini 3 Flash | Google | 27.1% | 47.4% |
| 30 | Codex CLI | GPT-5.2 | OpenAI | 14.3% | 62.9% |
| 31 | OpenHands | Claude Opus 4.5 | OpenHands | 12.9% | 51.9% |
| 32 | Mini-SWE-Agent | Claude Sonnet 4.5 | Princeton | 5.7% | 42.5% |
| 33 | Terminus 2 | GPT-5.3-Codex | AfterQuery | 2.6% | 64.7% |

### Per-Task: Run 3

| Task | Diff | AutoFyn | Ante | Terminus-KIRA | SageAgent | Simple Codex | Crux |
|------|------|:-------:|:----:|:-------------:|:---------:|:------------:|:----:|
| fix-git | easy | 100% | 100% | 100% | 100% | 100% | 100% |
| cobol-modernization | easy | 100% | 100% | 100% | 100% | 100% | 100% |
| overfull-hbox | easy | 50% | 100% | 100% | 100% | 100% | 60% |
| prove-plus-comm | easy | 0%¹ | 100% | 100% | 100% | 100% | 100% |
| regex-log | medium | 100% | 100% | 100% | 100% | 100% | 50% |
| sqlite-db-truncate | medium | 100% | 100% | 100% | 100% | 100% | 100% |
| raman-fitting | medium | 0% | 10% | 0% | 20% | 0% | 75% |
| filter-js-from-html | medium | 0% | 0% | 0% | 0% | 0% | 20% |
| mteb-retrieve | medium | 0% | 78% | 0% | 0% | 40% | 25% |
| dna-assembly | hard | 0% | 60% | 60% | 20% | 80% | 20% |
| cancel-async-tasks | hard | 50% | 100% | 100% | 100% | 20% | 100% |
| gpt2-codegolf | hard | 0% | 10% | 0% | 0% | 0% | 50% |
| fix-code-vulnerability | hard | 0% | 100% | 100% | 100% | 100% | 100% |
| write-compressor | hard | 25% | 90% | 100% | 100% | 100% | 25% |
| **Total** | | **37.5%** | **74.8%** | **68.6%** | **67.1%** | **67.1%** | **66.1%** |

¹ All 4 trials were NonZeroAgentExitCodeError (CLI crash) — same infra issue as Run 2, unfixed without caveman.

---

## Run 4 — claude-opus-4-5 + caveman (modified 14 tasks)

**AutoFyn: 50.0% — Rank 18/33**

Reverts to `claude-opus-4-5` after Run 3's regression. Adds the caveman token-save strategy. Task set unchanged from Runs 2–3.

| Rank | Agent | Model | Org | Score | Overall |
|------|-------|-------|-----|:-----:|:-------:|
| 1 | Ante | Gemini 3 Pro | Antigma Labs | 74.8% | 69.4% |
| 2 | Terminus-KIRA | Gemini 3.1 Pro | KRAFTON AI | 68.6% | 74.8% |
| 3 | SageAgent | GPT-5.3-Codex | OpenSage | 67.1% | 78.4% |
| 3 | Simple Codex | GPT-5.3-Codex | OpenAI | 67.1% | 75.1% |
| 5 | Crux | Claude Opus 4.6 | Roam | 66.1% | 66.9% |
| 6 | ForgeCode | GPT-5.4 | ForgeCode | 65.7% | 81.8% |
| 6 | Junie CLI | Gemini 3 Flash | JetBrains | 65.7% | 64.3% |
| 8 | Abacus AI Desktop | Multiple | Abacus.AI | 64.3% | 58.4% |
| 8 | Droid | GPT-5.3-Codex | Factory | 64.3% | 77.3% |
| 10 | II-Agent | Gemini 3 Pro | Intelligent Internet | 61.4% | 61.8% |
| 10 | TongAgents | Gemini 3.1 Pro | BIGAI | 61.4% | 80.2% |
| 12 | Capy | Claude Opus 4.6 | Capy | 58.6% | 75.3% |
| 12 | CodeBrain-1 | GPT-5.3-Codex | Feeling AI | 58.6% | 70.3% |
| 14 | OpenCode | Claude Opus 4.5 | Anomaly Innovations | 57.1% | 51.7% |
| 15 | IndusAGI Coding Agent | GPT-5.3-Codex | Varun Israni | 54.3% | 69.1% |
| 16 | Letta Code | Claude Opus 4.5 | Letta | 51.4% | 59.1% |
| 16 | Warp | Multiple | Warp | 51.4% | 61.2% |
| **18** | **AutoFyn** | **claude-opus-4-5 + caveman** | **AutoFyn** | **50.0%** | **—** |
| 18 | Deep Agents | GPT-5.2-Codex | LangChain | 50.0% | 66.5% |
| 18 | MAYA-V2 | Claude 4.6 Opus | ADYA | 50.0% | 72.1% |
| 18 | Mux | GPT-5.3-Codex | Coder | 50.0% | 74.6% |
| 22 | grok-cli | Grok 4.20 Reasoning | Vibe Kit | 48.6% | 57.3% |
| 23 | spoox-m | GPT-5-Mini | TUM | 41.4% | 34.8% |
| 24 | CAMEL-AI | Claude Sonnet 4.5 | CAMEL-AI | 40.0% | 46.5% |
| 25 | cchuter | minimax-m2.5 | teamblobfish.com | 37.5% | 42.7% |
| 26 | Goose | Claude Opus 4.5 | Block | 32.9% | 54.3% |
| 27 | Dakou Agent | Qwen 3 Coder 480B | iflow | 30.0% | 27.2% |
| 28 | Claude Code | Claude Opus 4.6 | Anthropic | 28.6% | 58.0% |
| 29 | Gemini CLI | Gemini 3 Flash | Google | 27.1% | 47.4% |
| 30 | Codex CLI | GPT-5.2 | OpenAI | 14.3% | 62.9% |
| 31 | OpenHands | Claude Opus 4.5 | OpenHands | 12.9% | 51.9% |
| 32 | Mini-SWE-Agent | Claude Sonnet 4.5 | Princeton | 5.7% | 42.5% |
| 33 | Terminus 2 | GPT-5.3-Codex | AfterQuery | 2.6% | 64.7% |

### Per-Task: Run 3

| Task | Diff | AutoFyn | Ante | Terminus-KIRA | SageAgent | Simple Codex | Crux |
|------|------|:-------:|:----:|:-------------:|:---------:|:------------:|:----:|
| fix-git | easy | 100% | 100% | 100% | 100% | 100% | 100% |
| cobol-modernization | easy | 100% | 100% | 100% | 100% | 100% | 100% |
| overfull-hbox | easy | 50% | 100% | 100% | 100% | 100% | 60% |
| prove-plus-comm | easy | 100% | 100% | 100% | 100% | 100% | 100% |
| regex-log | medium | 100% | 100% | 100% | 100% | 100% | 50% |
| sqlite-db-truncate | medium | 100% | 100% | 100% | 100% | 100% | 100% |
| raman-fitting | medium | 25% | 10% | 0% | 20% | 0% | 75% |
| filter-js-from-html | medium | 0% | 0% | 0% | 0% | 0% | 20% |
| mteb-retrieve | medium | 0% | 78% | 0% | 0% | 40% | 25% |
| dna-assembly | hard | 50% | 60% | 60% | 20% | 80% | 20% |
| cancel-async-tasks | hard | 75% | 100% | 100% | 100% | 20% | 100% |
| gpt2-codegolf | hard | 0% | 10% | 0% | 0% | 0% | 50% |
| fix-code-vulnerability | hard | **0%** | 100% | 100% | 100% | 100% | 100% |
| write-compressor | hard | **0%** | 90% | 100% | 100% | 100% | 25% |
| **Total** | | **50.0%** | **74.8%** | **68.6%** | **67.1%** | **67.1%** | **66.1%** |

---

## Run-over-Run Progress

| Task | Diff | Run 1 (opus-4-6) | Run 2 (opus-4-5) | Run 3 (opus-4-6 nerf) | Run 4 (opus-4-5 + caveman) |
|------|------|:----------------:|:----------------:|:---------------------:|:--------------------------:|
| fix-git | easy | 100% | 100% | 100% | 100% |
| cobol-modernization | easy | 100% | 100% | 100% | 100% |
| overfull-hbox | easy | 100%¹ | 25% | 50% | 50% |
| prove-plus-comm | easy | 0%² | 0%² | 0%² | 100% |
| regex-log | medium | 100% | 100% | 100% | 100% |
| sqlite-db-truncate | medium | 100%¹ | 100% | 100% | 100% |
| raman-fitting | medium | 0% | 25% | 0% | 25% |
| filter-js-from-html | medium | 0% | 0% | 0% | 0% |
| mteb-retrieve | medium | 0% | 0% | 0% | 0% |
| dna-assembly | hard | 100%¹ | 75% | 0% | 50% |
| gpt2-codegolf | hard | 0% | 0% | 0% | 0% |
| video-processing | hard | 0% | *not run* | *not run* | *not run* |
| sam-cell-seg | hard | 0% | *not run* | *not run* | *not run* |
| train-fasttext | hard | 0%² | *not run* | *not run* | *not run* |
| fix-code-vulnerability | hard | *not run* | 0% | 0% | 0% |
| write-compressor | hard | *not run* | **75%** | 25% | 0% |
| cancel-async-tasks | hard | *not run* | 75% | 50% | 75% |
| **Score** | | **42.9%** | **48.2%** | **37.5%** | **50.0%** |

**Run 3 (opus-4-6 post-nerf) vs Run 2:**
- Across the board regression. `dna-assembly` 75%→0%, `raman-fitting` 25%→0%, `cancel-async-tasks` 75%→50%, `write-compressor` 75%→25%. All consistent with a slower model hitting timeouts that opus-4-5 cleared comfortably. Anthropic appears to have updated `claude-opus-4-6` in the 2nd week of April.

**Key caveman gains (Run 2→Run 4):**
- `prove-plus-comm` +100%: CLI crashes (NonZeroAgentExitCodeError) eliminated entirely — caveman's disk checkpointing avoids the context-overflow that caused them.
- `overfull-hbox` +25% and `raman-fitting` stays at 25%: small consistency improvements.

**Caveman regression (Run 2→Run 4):**
- `write-compressor` −75%: Run 2 passed 3/4 trials (agents timed out but had already written enough code). In Run 4 caveman overhead consumed the budget before the solution was complete — 0/4.
- `dna-assembly` −25%: 75%→50%, same pattern.

**Run 1 context:**  
Run 1's high scores on `overfull-hbox` (100%), `sqlite-db-truncate` (100%), and `dna-assembly` (100%) are inflated — DaytonaError infra failures reduced the trial count to 1–2, and those happened to pass. Runs 2–4 with full 4-trial sets reveal the true consistency.

¹ Fewer than 4 valid trials in Run 1 (rest were DaytonaError infra failures) — score is on valid trials only.  
² All trials were infra crashes (NonZeroAgentExitCodeError / DaytonaError). Score treated as 0.
