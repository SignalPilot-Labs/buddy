## Mission

> {original_prompt}

Everything you plan must serve this mission.

---

## State

- **Round:** {round_num} | **Time:** {elapsed} of {duration} ({pct_complete}%)
- **Cost:** ${cost_so_far}
- **Files touched:** {files_changed}
- **Commits:** {commits}

### What happened last round:
{round_summary}

## Round {prev_round_num} Plan

Read `/tmp/current-spec.md` for the round {prev_round_num} spec.

## Round {prev_round_num} Review

Read `/tmp/current-review.md` for the reviewer's feedback on the round {prev_round_num} spec.

{operator_section}

---

Read the relevant code, then plan the next step.

**Write the spec to `/tmp/current-spec.md` using the Write tool. Do not return it as a message.**
