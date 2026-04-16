# AutoFyn — Terminal Benchmark 2.0 Research

You are a research engineer running controlled ablation experiments on AutoFyn — an autonomous coding agent harness. Your goal is to improve its **general-purpose resolution rate** on Terminal Benchmark 2.0 by identifying and fixing systemic failure mechanisms.

---

## What you are NOT doing

- Solving benchmark tasks
- Writing task-specific hints, recipes, or domain heuristics
- Adding conditionals that reference task names
- Injecting known solutions as "category guidance"
- Optimizing for the 14 known tasks specifically

If a proposed change would stop helping if the task list were completely different, it is overfit. Discard it.

---

## Context

**Baseline agent:** `terminal_bench_2/autofyn_agent/`
This is your control. Do not modify it. All experiments fork from it.

**Benchmark data available:**
- `terminal_bench_2/evals/` — human-readable run reports (run1–run4)
- `terminal_bench_2/evals/leaderboard.md` — current standings
- `terminal_bench_2/jobs/` — raw execution artifacts: `events.jsonl`, `claude-stream.jsonl`, test outcomes per trial

**Task sets:**
- `tasks-run1/` — original 14 tasks
- `tasks-run2/` — modified 14 tasks (use this for experiments)

**Daytona sandbox limits:** 4 vCPU / 8 GiB RAM / 10 GiB storage per sandbox. 600 sandbox creations/min.

---

## Cost discipline

One full 14-task run ≈ 5h of Claude usage. You cannot afford that per experiment.

**Rule:** Each experiment runs on **2–4 tasks maximum** — the minimal subset that exercises the specific failure mode under study. Choose tasks based on evidence, not convenience.

Full 14-task runs are reserved for validating a final candidate change only.

---

## Hold-out set

Before starting any experiments, designate **3 tasks as hold-out**. Never run experiments on them. Use them only to validate a finalized change.

Pick hold-out tasks that cover diverse failure modes (one timeout failure, one systematic-zero failure, one inconsistency failure). Write them here before proceeding:

```
HOLD-OUT TASKS:
1. _______________
2. _______________
3. _______________
```

---

## Research protocol

For every experiment, before writing any code or modifying any prompt:

### Step 1 — Diagnose

Read `evals/terminal-bench-run*.md` and sample relevant `jobs/jobs-runN/<task>/agent/events.jsonl` files.

Produce a **failure taxonomy**: what actually went wrong in the tool-call trace, not what the task requires. Categories to look for:

- **Context overflow** — agent loses state, context window fills, crashes
- **Feedback blindness** — agent completes steps but never verifies output, doesn't self-correct
- **Tool loop** — agent repeats the same tool call without changing approach
- **Budget exhaustion** — legitimate work runs out of turns/time before finishing
- **Wrong abstraction** — agent picks an approach that structurally cannot solve the problem class
- **Handoff failure** — subagent produces output the next subagent misinterprets or ignores

### Step 2 — Hypothesize

Write a formal hypothesis before touching any file:

```
HYPOTHESIS:
Target failure mode: [one of the categories above]
Evidence: [specific events.jsonl line references or eval observations]
Root cause: [mechanism, not symptom]
Proposed change: [what you'll modify — prompt / orchestration / memory / tool use / budget]
Predicted outcome: [what changes on which tasks, and why]
Generalization argument: "A coding agent working on a completely different
  domain would also benefit from this change because..."
```

If you cannot write a credible generalization argument, redesign the change.

### Step 3 — Scope

Identify the **minimum task subset** that exercises this failure mode. Justify each task selection from evidence in the job logs, not from assumed difficulty.

### Step 4 — Experiment

Fork a new directory from `autofyn_agent/`:

```
terminal_bench_2/autofyn_agent_<experiment_name>/
```

Make **one change per experiment**. Do not bundle multiple fixes. Document the exact diff in `experiments/EXP-N.md` before running.

Experiment types — rotate through these, do not default to prompt editing every time:

| Type | What changes |
|---|---|
| PROMPT | How a subagent reasons or structures its output |
| ORCHESTRATION | Turn limits, escalation logic, subagent routing |
| MEMORY | How state is checkpointed and recovered |
| TOOL USE | How agents invoke tools, parse results, handle errors |
| BUDGET | Token/time allocation across subagents |
| COMMUNICATION | How subagents hand off context to each other |

### Step 5 — Measure

Compare against the baseline on the same task subset. Record:

- Did the predicted outcome match reality?
- If not, what does the delta tell you about the actual failure mechanism?
- Is the change safe (no regressions on previously passing tasks)?

### Step 6 — Generalize or discard

Before shipping a change, complete:

```
VERDICT: [GO / NO-GO]
Reason: [one sentence]
Generalization: "This would also help when..."
Risk: "This could regress when..."
```

A NO-GO experiment is not a failure — it is evidence. Update your failure taxonomy and continue.

---

## Experiment log

Maintain `terminal_bench_2/experiments/` with one file per experiment:

```
experiments/
  EXP-01-<name>.md
  EXP-02-<name>.md
  ...
```

Each file contains the full hypothesis, scope, diff summary, results, and verdict.

---

## Start here

1. Read `evals/leaderboard.md` and all four `evals/terminal-bench-run*.md` files
2. Read `jobs/` traces for tasks with systematic failures (0% across all runs)
3. Build your failure taxonomy
4. Designate your hold-out set
5. Write your first hypothesis in `experiments/EXP-01.md`
6. Read `SETUP.md` before running any harbor command

Do not write a single line of agent code until steps 1–5 are complete.

---

## Baseline (Run 3 — `autofyn_agent`, opus-4-6)

Run 3 is the control baseline. It uses the unmodified agent with `claude-opus-4-6`.
**Overall score: 37.5%** — job: `jobs/jobs-run3/2026-04-10__16-08-48`

| Task | Score | Primary failure |
|------|:-----:|----------------|
| `fix-git` | 100% | — |
| `cobol-modernization` | 100% | — |
| `regex-log` | 100% | — |
| `sqlite-db-truncate` | 100% | — |
| `overfull-hbox` | 50% | Inconsistent |
| `cancel-async-tasks` | 50% | Inconsistent |
| `write-compressor` | 25% | AgentTimeoutError (3/4 trials) |
| `raman-fitting` | 0% | AgentTimeoutError |
| `filter-js-from-html` | 0% | Wrong abstraction |
| `prove-plus-comm` | 0% | NonZeroAgentExitCodeError (all 4 trials) |
| `mteb-retrieve` | 0% | AgentTimeoutError (all 4 trials) |
| `dna-assembly` | 0% | AgentTimeoutError (all 4 trials) |
| `gpt2-codegolf` | 0% | AgentTimeoutError — expert time 2400 min |
| `fix-code-vulnerability` | 0% | AgentTimeoutError (all 4 trials) |

**Field rank 1 (Ante, Gemini 3 Pro): 74.8%** — gap to close: ~37pp
