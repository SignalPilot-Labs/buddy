Review the round {round_num} changes against the round {round_num} spec in `/tmp/current-spec.md`.

1. Run typechecker and linter.
2. `git diff` to see what changed.
3. Check: does the implementation match the spec's design decisions?
4. Check: correctness, security, code quality.
5. If the design itself is wrong (even if builder followed the spec), flag it as a design concern.

**Write your round {round_num} review to `/tmp/current-review.md` using the Write tool. Do not return it as a message.**

{extra_context}
