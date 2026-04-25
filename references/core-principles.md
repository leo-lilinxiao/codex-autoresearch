# Core Principles

These principles define the skill.

## 1. Constraint Enables Autonomy

Autonomous loops work when scope is small enough to fully understand.

- Prefer a bounded file set.
- Prefer a single metric.
- Prefer a fixed iteration cost.

## 2. Humans Set Direction, Agents Execute

The user defines the goal. Codex decides how to test ideas inside the declared boundaries.

## 3. Metrics Must Be Mechanical

If a command cannot decide whether the result improved, the loop is not ready.

Good metrics:

- test failure count
- coverage percentage
- bundle size
- response latency
- benchmark throughput
- validation metric such as `val_bpb`

Bad metrics:

- "looks better"
- "feels cleaner"
- "probably faster"

## 4. Fast Verification Wins

Use the fastest trustworthy check. Slow verification destroys iteration speed.

Prefer:

- targeted tests over full suites
- incremental builds over full rebuilds
- narrow benchmarks over end-to-end manual testing

## 5. One Change Per Iteration

Atomic experiments create causality. If the result changes, the agent knows why.

## 6. Git Is Memory

Kept experiments stay in history. Failed experiments are rolled back using the pre-approved experiment rollback strategy. The results log (`autoresearch-results/results.tsv`) records every experiment -- kept or discarded -- as the true audit trail.

## 7. Simplicity Is A Tiebreaker

Equal metric plus less complexity is a win. Tiny metric gains (< 1%) with significant code ugliness are not. Marginal improvement plus added complexity = discard. Metric unchanged plus simpler code = keep.

## 8. Honest Limits

If permissions, tooling, flakiness, or missing context make the loop unsafe, stop and say so. Planning cleanly is better than guessing.
