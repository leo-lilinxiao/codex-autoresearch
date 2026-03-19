# Health Check Protocol

Self-monitoring system that validates environment and run integrity at iteration boundaries. Catches problems before they corrupt results.

## Check Frequency

### Every Iteration Boundary (Lightweight)

Run between Phase 8 (Log) and Phase 9 (Repeat):

| Check | How | Failure Action |
|-------|-----|----------------|
| Disk space | `df -m . \| awk 'NR==2{print $4}'` >= 500MB | Warning at <1GB, hard blocker at <500MB |
| Git state | `git status --porcelain` shows only expected files | Warning if unexpected files; hard blocker if repo is corrupt |
| Verify health | Last verify completed without timeout or crash | Warning if last 2 verifies timed out; hard blocker if verify command missing |
| Log integrity | Results TSV has expected number of rows | Hard blocker if rows are missing or file is corrupt |
| Wall-clock | Current iteration time vs rolling average | Warning if >3x average (possible resource contention) |

### Every 10 Iterations (Deep Check)

Run at iterations 10, 20, 30, etc.:

| Check | How | Failure Action |
|-------|-----|----------------|
| External modifications | `git log --oneline -5` matches expected commit sequence | Warning if unexpected commits appeared |
| Scope integrity | All in-scope files still exist | Hard blocker if scope files deleted |
| Environment drift | Re-check disk space, verify GPU if initially detected | Warning on degradation |
| Verify consistency | Run verify twice, compare results | Warning if results differ (flaky verify) |
| Guard consistency | Run guard once, confirm still passes on current state | Warning if guard started failing without code changes |

## Response Actions

### Auto-Recovery (Safe)

These issues can be resolved without user intervention:

| Issue | Recovery |
|-------|----------|
| Disk < 1GB but > 500MB | Log warning, continue with smaller changes |
| Unexpected files in worktree | Ignore if outside scope, log warning |
| Single verify timeout | Retry once, continue if successful |
| Wall-clock spike (single) | Log timing anomaly, continue |

### Warning (Log and Continue)

These issues are logged but do not stop the loop:

```
[HEALTH] iteration {N}: {description}
```

Warnings are appended to the results log description column with a `[HEALTH]` prefix.

After 3 consecutive warnings of the same type, escalate to a soft blocker announcement (continue iterating but print a prominent warning).

### Hard Blocker (Stop)

These issues stop the loop immediately:

| Issue | Reason |
|-------|--------|
| Disk < 500MB | Cannot safely commit or create files |
| Results log corrupted or missing | Cannot track progress |
| Git repo in broken state | Cannot commit or revert |
| Verify command no longer exists | Cannot measure progress |
| All scope files deleted | Nothing to modify |

On hard blocker:
1. Attempt to revert the last uncommitted change if one is in progress.
2. Log the blocker in the results TSV with status `blocked`.
3. Print a completion summary with the blocker reason.
4. Stop the loop.

## Wall-Clock Tracking

Track iteration timing to detect resource contention or environment degradation:

```
iteration_times = [t1, t2, t3, ...]
rolling_avg = average(last 5 iterations)
current_time = time of current iteration
```

Thresholds:
- Warning: current_time > 3x rolling_avg
- Concern: 3 consecutive iterations > 2x rolling_avg
- No hard blocker for timing alone (could be legitimate workload variation)

## Integration Points

- **autonomous-loop-protocol.md:** Runs as Phase 8.5 between Log and Repeat.
- **environment-awareness.md:** Initial probes establish baselines for drift detection.
- **parallel-experiments-protocol.md:** Check worktree health before each parallel batch.
- **results-logging.md:** Health warnings are logged in the description column.
- **SKILL.md:** Listed in the load order for iterating modes.
