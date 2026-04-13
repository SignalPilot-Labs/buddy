# Failure Taxonomy — Terminal Bench 2.0

Built from analysis of runs 1–4 eval reports and job trace examination (events.jsonl, result.json, verifier output).

## Category 1: Budget Exhaustion (Timeout)

**Mechanism:** Agent consumes entire timeout budget without producing a valid result. The multi-subagent orchestrator (planner → builder → reviewer loop) burns time on LLM round-trips, leaving insufficient time for actual work.

**Affected tasks:**
- `mteb-retrieve` (1800s budget, 0% all runs) — agent never produces `/app/result.txt`. No agent logs captured (exec_as_agent never returns). The correct solution runs in <2 minutes.
- `gpt2-codegolf` (900s budget, 0% all runs) — expert estimate 2400 min. Structurally unsolvable under 15-min budget regardless of approach.
- `fix-code-vulnerability` (900s budget, 0% runs 2-4) — expert estimate 120 min. Agent reads 3500-line bottle.py, multi-subagent overhead exhausts budget. Also has a verifier infra bug (network unreachable for pip install).
- `write-compressor` (900s budget, 75% run2 → 0% run4) — caveman overhead regression. Run2 (no caveman) barely finished at 877s. Caveman SKILL.md injected into every subagent prompt pushed it past 900s.

**Contributing factors:**
- Caveman SKILL.md appended to ALL 4 subagent prompts adds token overhead per round
- Missing `cwd=TASK_CWD` in caveman agent.py wastes early turns navigating to /app
- `AGENT_TIMEOUT_SEC=3600` in constants.py is irrelevant — Harbor enforces task.toml timeout (900-1800s)

## Category 2: Feedback Blindness

**Mechanism:** Agent produces output without verifying it against the actual success criteria. Passes surface-level checks but fails on precise constraints the test enforces.

**Affected tasks:**
- `overfull-hbox` (50% run4) — Agent substitutes words to fix LaTeX overfull warnings but doesn't check article agreement ("a"→"an" mismatch). The verifier does token-level comparison requiring all substitutions come from synonym families. Passing trials used shorter synonyms that avoided article changes.
- `raman-fitting` (25% run4) — Agent assumes x-axis is Raman shift cm⁻¹ when data is actually in nm (reciprocal: wavenumber = 1e7/x). Fits noise in wrong x-range. Passing trial (1 of 4) spent 50 exploratory steps discovering the unit mismatch before coding.

## Category 3: Wrong Abstraction

**Mechanism:** Agent picks an approach that is structurally misaligned with what the test expects, regardless of execution quality.

**Affected tasks:**
- `filter-js-from-html` (0% all runs) — Two independent failures:
  1. Agent preserves original HTML bytes (per instruction: "do not alter formatting") but test compares against `str(BeautifulSoup(original, "html.parser"))` normalization. Reference solution uses BeautifulSoup serialization.
  2. Agent's XSS filter misses exotic vectors from davidwagner testbed (IE conditional comments, SHIFT_JIS charset attacks, unusual URL-bearing attributes like CITE, malformed tag syntax).

## Category 4: Caveman Overhead Regression

**Mechanism:** Caveman SKILL.md appended to every subagent prompt adds per-round token overhead. Tasks that barely fit the timeout budget in run2 (no caveman) fail in run4 (caveman).

**Affected tasks:**
- `write-compressor`: 75% → 0% (run2 → run4)
- `dna-assembly`: 75% → 50% (run2 → run4)

## Category 5: Infrastructure Bugs

**Mechanism:** Failures caused by environment/harness issues, not agent quality.

**Affected tasks:**
- `fix-code-vulnerability` — Verifier container has no network access; `pip install pytest-json-ctrf` fails with "Network is unreachable". Even a perfect agent solution scores 0.
- `prove-plus-comm` — CLI crash (NonZeroAgentExitCodeError) in runs 1-3 due to context overflow. Caveman's disk checkpointing fixed this in run4 (100%).

## Category 6: Unsolvable Under Constraints

**Mechanism:** Task requirements exceed what any agent can achieve within the given time/resource budget.

**Affected tasks:**
- `gpt2-codegolf` — Expert estimate 2400 minutes, agent budget 15 minutes. No general-purpose improvement can bridge this gap.

---

## Summary Table

| Task | Difficulty | Best Score | Primary Failure | Fixable? |
|---|---|---|---|---|
| fix-git | easy | 100% | — | N/A (always passes) |
| cobol-modernization | easy | 100% | — | N/A (always passes) |
| regex-log | medium | 100% | — | N/A (always passes) |
| sqlite-db-truncate | medium | 100% | — | N/A (always passes) |
| prove-plus-comm | easy | 100% | Infra (fixed by caveman) | Already fixed |
| overfull-hbox | easy | 50% | Feedback blindness | Yes — verification |
| cancel-async-tasks | hard | 75% | Budget/inconsistency | Partially |
| dna-assembly | hard | 75% | Caveman overhead + model sensitivity | Yes — overhead reduction |
| write-compressor | hard | 75% | Caveman overhead + cwd bug | Yes — cwd fix + overhead |
| raman-fitting | medium | 25% | Feedback blindness + wrong assumption | Partially — exploration emphasis |
| filter-js-from-html | medium | 0% | Wrong abstraction | Hard — structural mismatch |
| mteb-retrieve | medium | 0% | Budget exhaustion | Partially — overhead reduction |
| fix-code-vulnerability | hard | 0% | Budget + infra bug | Partially (infra out of scope) |
| gpt2-codegolf | hard | 0% | Unsolvable under budget | No |
