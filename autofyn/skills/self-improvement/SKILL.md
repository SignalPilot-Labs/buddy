---
description: "Use when updating project documentation, saving learnings, or running retrospectives. Covers CLAUDE.md updates, memory persistence, and cross-session learning."
---

# Self-Improvement

You have two persistence mechanisms. Use the right one.

## CLAUDE.md — Project Knowledge

`CLAUDE.md` lives in the repo root, gets committed, and is loaded into every future session. Use it for knowledge that **any engineer (human or AI) working on this repo** would benefit from.

Add to CLAUDE.md when you discover:
- Build commands, test commands, linter config not in README
- Architectural patterns and module boundaries
- Environment setup steps that weren't obvious
- Conventions the codebase follows but nobody documented
- Gotchas that caused you to waste time

Update it directly — don't create a separate doc. Keep entries concise. If something is already in README, don't duplicate it.

**When to update:** After Phase 0 (env setup) if setup was non-obvious. After a round where you hit an undocumented convention. After fixing a bug caused by missing context.

## ~/.claude/ Memory — Agent Knowledge

The `~/.claude/` directory persists across sessions (Docker volume). Claude Code's memory system stores files here. Use it for knowledge that **future agent sessions** need but doesn't belong in the repo.

Save to memory when you learn:
- Build quirks specific to the agent environment (e.g. "pyright needs X flag in sandbox")
- Recurring failure patterns and their solutions
- Repo-specific architectural decisions and their rationale
- Which subagent works best for which type of task in this repo
- User preferences for this repo (commit style, PR format, review strictness)

Do NOT save:
- Run-specific details (what you did this session)
- Things already in CLAUDE.md or README
- Things derivable from reading current code
- Debugging steps that led nowhere

**How:** Use Claude Code's built-in memory tools to write to `~/.claude/memory/`.

## Retrospectives

After round 3, before calling the architect:
1. Read `/tmp/review/round-*` to see what reviewers flagged across rounds
2. If the same issue keeps appearing — tell the architect explicitly
3. If a subagent keeps failing at the same thing — adjust your delegation (more context, different agent, spec review first)
4. If you learned something reusable — decide: CLAUDE.md (for everyone) or memory (for agent only)

## After Failures

When a round fails (build breaks, review rejects):
1. Understand WHY it failed — don't just retry
2. Missing convention? → Add to CLAUDE.md
3. Agent-specific pattern? → Save to memory
4. One-off issue? → Fix and move on, don't document
