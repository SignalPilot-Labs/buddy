---
description: "Use when the task involves performance — optimizing slow code, fixing resource leaks, profiling, caching, reducing latency or startup time."
---

# Performance

Don't guess. Measure first, then fix what's actually slow.

## How to Approach

1. **Reproduce the problem.** Find the slow path — which endpoint, query, or operation.
2. **Profile.** Use the project's tools or add instrumentation. Identify the bottleneck.
3. **Fix the bottleneck.** Not the code around it.
4. **Verify the fix.** Measure again. If you can't measure, at least reason about the complexity change.

## Common Bottlenecks

**Database**
- N+1 queries — fetching related records in a loop. Join or batch.
- Missing indexes — `EXPLAIN ANALYZE` the slow query, add the index.
- Pool churn — creating/destroying connections per request. Use a persistent pool.
- Unbounded queries — no `LIMIT`, fetching entire tables. Paginate.

**I/O**
- Sync in async — blocking calls inside async functions starve the event loop. Use async alternatives.
- Sequential when parallelizable — multiple independent API/DB calls done one after another. Use `asyncio.gather` / `Promise.all`.
- No connection reuse — creating new HTTP clients per request. Reuse the client.

**Compute**
- Repeated work — same computation on every request. Cache it (in-memory, Redis, or HTTP cache headers).
- O(n^2) or worse — nested loops, repeated list scans. Use sets, dicts, or better algorithms.
- Heavy imports at startup — lazy-load large dependencies that aren't always needed.

**Frontend**
- Massive bundles — tree-shake, code-split, lazy-load routes.
- Unthrottled re-renders — missing memoization, state updates in loops.
- Blocking the main thread — heavy computation should be in a worker.

## Profiling

```bash
# Python
python -m cProfile -s cumulative script.py
py-spy top -- python script.py  # live, zero overhead

# Node
node --prof app.js
clinic doctor -- node app.js

# General
time curl -s http://localhost:3000/slow-endpoint > /dev/null
```

## Rules

- Don't optimize code that runs once at startup unless startup time is the problem.
- Don't add caching without understanding invalidation.
- Prefer simpler algorithms over clever micro-optimizations.
- If the fix makes code significantly harder to read, document why it's worth it.
