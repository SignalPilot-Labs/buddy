# Docker Containers Report

**Date:** 2026-04-08  
**Host Memory Limit:** 7.653 GiB

---

## Running Containers

| Container | Image | Status | CPU % | Memory Usage | Memory % | PIDs |
|-----------|-------|--------|-------|-------------|----------|------|
| autofyn-sandbox (session) | autofyn-sandbox | Up (healthy) | 6.05% | 246.2 MiB / 7.65 GiB | 3.14% | 33 |
| autofyn-dashboard | autofyn-dashboard | Up | 2.69% | 115.9 MiB / 7.65 GiB | 1.48% | 18 |
| autofyn-agent | autofyn-agent | Up (healthy) | 0.49% | 95.29 MiB / 7.65 GiB | 1.22% | 7 |
| autofyn-sandbox | autofyn-sandbox | Up (healthy) | 0.00% | 78.55 MiB / 7.65 GiB | 1.00% | 1 |
| timescaledb | timescale/timescaledb:latest-pg16 | Up 4 days | 0.00% | 47.02 MiB / 7.65 GiB | 0.60% | 9 |
| autofyn-db | postgres:16-alpine | Up (healthy) | 0.45% | 34.74 MiB / 7.65 GiB | 0.44% | 13 |

**Total Memory Used:** ~617.7 MiB (7.88% of 7.65 GiB)

---

## Network and Block I/O

| Container | Net I/O (In / Out) | Block I/O (Read / Write) |
|-----------|--------------------|--------------------------|
| autofyn-sandbox (session) | 7.19 MB / 204 kB | 131 kB / 6.84 MB |
| autofyn-dashboard | 869 kB / 284 kB | 32.8 kB / 152 kB |
| autofyn-agent | 43.4 kB / 59.9 kB | 1.7 MB / 229 kB |
| autofyn-sandbox | 1.04 kB / 0 B | 459 kB / 90.1 kB |
| timescaledb | 101 kB / 42.2 kB | 24.2 MB / 159 MB |
| autofyn-db | 87.7 kB / 747 kB | 3.07 MB / 332 kB |

---

## Docker Images

| Repository | Tag | Size |
|------------|-----|------|
| autofyn-sandbox | latest | 1.84 GB |
| timescale/timescaledb | latest-pg16 | 1.62 GB |
| autofyn-agent | latest | 938 MB |
| autofyn-dashboard | latest | 822 MB |
| postgres | 16-alpine | 388 MB |

**Total Image Size:** 12.55 GB (0% reclaimable -- all active)

---

## Volumes

### Active Volumes (linked to running containers)

| Volume Name | Size | Links |
|-------------|------|-------|
| autofyn_autofyn-db | 75.89 MB | 1 |
| dd68af56...b484ca (timescaledb data) | 70.91 MB | 1 |
| autofyn-repo-ff382334...b9cc0db | 12.58 MB | 1 |
| autofyn_agent-repo | 0 B | 1 |
| autofyn_claude-agent-sessions | 0 B | 1 |
| autofyn_autofyn-keys | 68 B | 1 |

### Orphan Volumes (not linked to any container)

| Volume Name | Size | Notes |
|-------------|------|-------|
| buddy_autofyn-db | 49 MB | Old stack data |
| buddy_agent-repo | 11.9 MB | Old stack data |
| buddy_claude-agent-sessions | 1.565 MB | Old stack data |
| buddy_autofyn-keys | 68 B | Old stack data |
| autofyn-repo-e2e-test | 27.06 kB | Test volume |
| autofyn-repo-session-test | 0 B | Test volume |
| autofyn-repo-session-test2 | 0 B | Test volume |
| autofyn-repo-test-123 | 0 B | Test volume |

**Total Volume Size:** 221.9 MB  
**Reclaimable (orphan volumes):** 62.49 MB (28%)

---

## Disk Usage Summary

| Category | Total Size | Reclaimable |
|----------|-----------|-------------|
| Images | 12.55 GB | 0 B (0%) |
| Containers | 1.274 MB | 0 B (0%) |
| Local Volumes | 221.9 MB | 62.49 MB (28%) |
| Build Cache | 10.24 GB | 10.24 GB (100%) |
| **Total** | **~23.0 GB** | **~10.3 GB (45%)** |

---

## Recommendations

1. **Build cache** is 10.24 GB and 100% reclaimable. Run `docker builder prune` to free space.
2. **Orphan volumes** (`buddy_*` and test volumes) hold 62.49 MB and are not linked to any running container. Run `docker volume prune` to clean up.
3. The **sandbox session container** is the heaviest at 246 MiB -- expected for an active Claude SDK session.
4. **timescaledb** has the most block I/O writes (159 MB) -- it has been running for 4 days.
