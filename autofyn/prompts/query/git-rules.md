## Git

- Do NOT run git write commands (`git commit`, `git add`, `git push`, etc.) — the Python round loop handles all commits and pushes from the orchestrator's round summary.
- Do NOT create, switch, or reset branches. You are already on the correct branch.
- Do NOT open PRs — teardown handles that from `/tmp/rounds.json`.