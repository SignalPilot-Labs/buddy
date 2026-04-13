# EXP-06: Instruction Pass-Through to Builder (Handoff Loss Fix)

## HYPOTHESIS

```
Target failure mode: Handoff failure / Communication (between orchestrator and builder)
Evidence:
  - overfull-hbox (50%): Builder substitutes words but misses article agreement constraint.
    The instruction says "do not alter formatting" but the planner's spec may not
    relay this precisely. Builder never reads the original instruction.
  - raman-fitting (25%): Builder assumes x-axis units without checking. The instruction
    specifies the data file but the planner abstracts away details the builder needs.
  - filter-js-from-html (0%): Builder misses subtle formatting preservation requirement.
    "do not alter formatting" in instruction → planner spec → builder loses fidelity.
  - In ALL tasks: the builder receives only /tmp/current-spec.md. It never reads the 
    original task instruction. Information is lossy through the planner abstraction.
Root cause: Builder operates from a planner-authored spec that may omit, simplify, or
  misinterpret constraints from the original instruction. The builder has no way to
  cross-check against the source-of-truth task instruction.
Proposed change: Modify system.md to instruct the orchestrator to write the original
  task instruction to /tmp/task-instruction.md on first round setup. Modify builder.md
  to read /tmp/task-instruction.md in addition to /tmp/current-spec.md, using it as
  a cross-reference for constraint validation.
Predicted outcome:
  - overfull-hbox: 50% -> 75%+ (builder catches formatting constraints the planner missed)
  - raman-fitting: 25% -> 50%+ (builder reads data format details from instruction)
  - filter-js-from-html: 0% -> 25%+ (builder sees "do not alter formatting" directly)
  - No regressions on passing tasks — more information only helps
Generalization argument: "Any multi-agent system where an intermediary summarizes
  requirements before passing to the implementer risks losing fidelity. Giving the
  implementer access to the original requirements as a cross-reference is a standard
  software engineering practice (developers read the ticket, not just the tech lead's
  summary)."
```

## SCOPE

Test tasks (chosen from evidence):
1. **overfull-hbox** — instruction has specific constraints planner may not fully relay
2. **raman-fitting** — data format details in instruction matter for correct implementation

## CHANGE

Type: COMMUNICATION (how subagents receive task context)

Two files changed: system.md (write instruction file), builder.md (read it).

### system.md change
Add step 4 to first-round setup:
```
4. Write the task instruction to `/tmp/task-instruction.md` for subagent reference.
```

### builder.md change
Add to the Process section:
```
0. **Read the task instruction.** Read `/tmp/task-instruction.md` to understand the
   original task requirements. Cross-reference against the spec to ensure no constraints
   were lost. If you notice the spec omits a requirement from the instruction, implement
   it anyway.
```

## MEASUREMENT PLAN

- overfull-hbox pass rate: baseline 50% -> target 75%+
- raman-fitting pass rate: baseline 25% -> target 50%+
- Check for regressions on already-passing tasks

## STATUS

- [ ] Fork created: `autofyn_agent_instruct/`
- [ ] Changes implemented
- [ ] Run completed
- [ ] Results recorded
- [ ] Verdict issued
