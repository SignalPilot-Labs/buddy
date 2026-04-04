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

{last_plan_section}

{review_section}

{operator_section}

---

Read the relevant code, then plan the next step. Write the spec to `/tmp/current-spec.md`.
