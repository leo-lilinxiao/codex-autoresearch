# Parallel Experiments Protocol

Run multiple hypotheses concurrently using subagent workers in isolated git worktrees. The orchestrator picks the best result and merges it back.

**Scope limitation:** Parallel mode requires that each worker can independently run the verify command without resource contention. For CPU-bound verify commands, this is straightforward. For GPU/NPU workloads, parallel mode is only safe when enough free devices exist to run multiple experiments simultaneously without contention.

## Applicability

### When Parallel Mode Is Safe

- **CPU-bound verify commands** (always safe):
  - Eliminating type errors (`tsc --noEmit`)
  - Raising test coverage (`pytest --cov`)
  - Reducing lint warnings (`eslint`, `ruff`, `clippy`)
  - Shrinking bundle size (build + measure)
  - Fixing broken tests
  - Code-only optimizations

- **GPU/NPU workloads with sufficient devices** (safe with constraints):
  - 16 GPUs, each experiment uses 8 -> 2 parallel experiments possible
  - 8 NPUs, each experiment uses 2 -> up to 3 parallel experiments (capped by protocol max)
  - Single GPU, each experiment uses 1 -> serial only (no spare device)

### When Parallel Mode MUST NOT Be Used

- Total available devices < 2x devices required per experiment
- Verify command requires ALL available devices (e.g., full-node distributed training)
- Performance profiling that depends on exclusive system-wide access
- Any verify command that acquires system-wide exclusive locks
- Any verify command that binds to a fixed network port without per-worker override

### Device-Aware Parallelism

For GPU/NPU workloads, the maximum parallelism is determined by device availability:

```
devices_per_experiment = detected or user-specified during wizard
total_devices = detected via nvidia-smi / npu-smi / rocm-smi
max_device_workers = floor(total_devices / devices_per_experiment)
max_workers = min(3, user_specified, max_device_workers)
```

Each parallel worker must be assigned a non-overlapping set of devices:

| Worker | Devices (example: 16 GPUs, 8 per experiment) |
|--------|----------------------------------------------|
| worker-a | `CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7` |
| worker-b | `CUDA_VISIBLE_DEVICES=8,9,10,11,12,13,14,15` |

For Ascend NPU, use the equivalent `ASCEND_RT_VISIBLE_DEVICES` environment variable.

The environment probe (see `references/environment-awareness.md`) detects accelerator count. During the wizard phase, if GPU/NPU is detected, ask:

- "Each experiment uses how many GPUs/NPUs? (I detected {N} total)"

If the user does not specify, assume each experiment requires ALL detected devices (conservative default -> serial mode).

## Architecture

```
Orchestrator (main agent, main worktree)
  |
  +-- Worker A (subagent, worktree-a) -> hypothesis 1
  +-- Worker B (subagent, worktree-b) -> hypothesis 2
  +-- Worker C (subagent, worktree-c) -> hypothesis 3
```

- The orchestrator generates N hypotheses and dispatches them.
- Each worker applies one hypothesis, runs verify, and reports results.
- The orchestrator compares results, merges the best, and discards the rest.
- **All of this is fully autonomous.** No user interaction occurs during parallel execution. The user approved parallel mode during the wizard phase (before "go"). After "go", the orchestrator and workers operate silently.

## Activation

### User Opt-In (Wizard Phase Only)

During the wizard phase (before "go"), ask:

- "Test multiple ideas in parallel? (faster but uses more CPU/disk; GPU/NPU runs only support this when enough free devices are available)"
- Default: serial (single hypothesis per iteration)

This question is asked **once, before launch**. After the user says "go", parallel mode is locked in and cannot be changed mid-run. This respects the two-phase boundary.

### Automatic Activation Suggestion

If environment probes show:
- CPU cores >= 4
- RAM >= 8GB
- Disk free >= 5GB

Then suggest parallel mode during the wizard. For GPU/NPU workloads, also check:
- Total devices >= 2x devices per experiment

Never auto-enable without confirmation.

### Automatic Disablement

Parallel mode is automatically disabled (with a log message) if:
- Total available devices < 2x devices required per experiment (GPU/NPU workloads)
- The verify command binds to a specific port without per-worker override
- The environment has < 2 CPU cores
- Disk space is insufficient for additional worktrees

## Parallelism Limits

For CPU-bound workloads:

```
max_workers = min(3, user_specified, floor(cpu_cores / 2))
```

For GPU/NPU workloads:

```
max_workers = min(3, user_specified, floor(total_devices / devices_per_experiment))
```

- Hard cap: 3 concurrent workers.
- Each worker needs its own worktree (~1x repo size disk).
- Each worker gets a non-overlapping device assignment via environment variables.
- If disk is tight, reduce parallelism or fall back to serial.

## Workflow

### 1. Orchestrator: Generate Hypotheses

At the start of each parallel iteration batch:

1. Generate N hypotheses (where N = max_workers).
2. Each hypothesis must be independent (no shared state beyond the base commit).
3. Use the hypothesis perspectives protocol if enabled to diversify approaches.
4. Assign each hypothesis a worker ID: `worker-{a,b,c}`.

### 2. Dispatch Workers

For each hypothesis, launch a subagent with:

- Task: apply hypothesis, run verify command, run guard command, report metric.
- Isolation: git worktree (created from current HEAD).
- Context: current goal, scope, metric, direction, verify command, guard command, current best metric (best value achieved before this parallel batch, or baseline if no keeps exist yet).
- Device assignment (GPU/NPU workloads only): set `CUDA_VISIBLE_DEVICES`, `ASCEND_RT_VISIBLE_DEVICES`, or equivalent environment variable to the worker's non-overlapping device slice.
- Constraint: one focused change only, same rules as serial mode.
- **No user interaction:** Workers operate fully autonomously. They never ask questions, never pause for confirmation, never output to the user. They report results only to the orchestrator.

Worker prompt template:

```
You are a parallel experiment worker for codex-autoresearch.

Goal: {goal}
Scope: {scope}
Hypothesis: {hypothesis_description}
Verify: {verify_command}
Guard: {guard_command}
Metric direction: {direction}
Current best metric: {current_best}

Instructions:
1. Apply the hypothesis as a single focused change.
2. Commit the change.
3. Run the verify command and record the metric.
4. Run the guard command.
5. Report back: commit hash, metric value, guard pass/fail, description.

Do NOT modify files outside scope. Do NOT run multiple changes.
Do NOT ask any questions. Do NOT interact with the user.
```

### 3. Collect Results

Wait for all workers to complete (with a timeout of 2x the expected verify duration). If a worker hangs beyond the timeout, kill it, discard its result, and log `[PARALLEL worker-{id}] timeout`. Each worker returns:

```
worker_id: a
commit: abc1234
metric: 38
guard: pass
description: narrowed type annotations in auth module
status: keep | discard | crash
```

### 4. Orchestrator: Select Best

Selection rules:

1. Discard any result where guard failed.
2. Discard any result where metric moved in the wrong direction.
3. Among remaining results, pick the one with the best metric improvement.
4. If multiple results have identical improvement, prefer the smaller diff.
5. If no result improved, discard all (count as a single discard for pivot tracking).

### 5. Merge Best Result

1. Cherry-pick the winning commit from the worker's worktree branch.
2. Verify the cherry-pick applies cleanly.
3. If cherry-pick conflicts: attempt three-way merge with the base commit. If three-way merge also fails, discard the result and log as `merge-conflict`. Do not manually apply patches -- maintaining atomic commits is required.
4. Run verify + guard on the merged result to confirm.
5. If post-merge verification fails, discard and log as `merge-verify-fail`.
6. If the best result cannot be merged, try the second-best result. If no result can be merged, count the entire batch as a single discard for pivot tracking.

### 6. Cleanup

- Remove all worker worktrees.
- Delete worker branches.
- Log all worker results in the results TSV (one line per worker per batch).

## Results Logging

Parallel iterations use a batch notation:

```tsv
iteration	commit	metric	delta	guard	status	description
5a	abc1234	38	-3	pass	keep	[PARALLEL worker-a] narrowed auth types
5b	-	42	+1	pass	discard	[PARALLEL worker-b] wrapper approach
5c	-	41	0	-	crash	[PARALLEL worker-c] timeout after 20m
5	abc1234	38	-3	pass	keep	[PARALLEL batch] selected worker-a: narrowed auth types
```

- Worker rows (`5a`, `5b`, `5c`) are audit detail.
- The integer main row (`5`) is the authoritative retained-state update for the whole batch.
- Prefer `python3 <skill-root>/scripts/autoresearch_select_parallel_batch.py --batch-file ...` so worker rows, the authoritative main row, batch-boundary preflight checks, JSON state, and any resulting keep lesson stay aligned. Here `<skill-root>` is the directory containing the loaded `SKILL.md`.

### JSON State Update for Parallel Batches

After a parallel batch completes and the best result is merged (or all results are discarded):

1. Update `autoresearch-results/state.json` once per batch, not once per worker.
2. Increment `state.iteration` by 1 (the batch counts as a single main iteration).
3. Set `state.current_metric` to the selected worker's metric, or leave it unchanged if all workers are discarded.
4. Set `state.last_trial_metric` to the batch's selected metric, or to the best discarded attempt if no worker is kept.
5. Count the batch as 1 keep or 1 discard regardless of worker count.

## Fallback to Serial

Switch to serial mode if:

- Git worktrees are not supported (bare repo, shallow clone, etc.).
- Disk space is insufficient for additional worktrees.
- The first parallel batch fails due to environment issues.
- Available devices < 2x devices required per experiment (GPU/NPU workloads).
- A worker hangs or crashes on the first batch.
- The user opts out.

When falling back:

1. Log: `[PARALLEL -> SERIAL] reason: {reason}`.
2. Continue with standard single-hypothesis iterations.
3. Do not retry parallel mode in the same run.

## Integration Points

- **interaction-wizard.md:** Add parallel mode question to wizard (before "go" only).
- **autonomous-loop-protocol.md:** Phase 3 (Ideate) generates multiple hypotheses when parallel is active.
- **environment-awareness.md:** Resource probes inform parallelism limits; for GPU/NPU workloads they only permit parallel mode when enough free devices exist.
- **pivot-protocol.md:** A parallel batch with zero keeps counts as one discard toward pivot thresholds.
- **lessons-protocol.md:** Keep worker rows as audit detail and append the resulting interactive keep lesson only for the authoritative selected main row.
- **health-check-protocol.md:** `autoresearch_select_parallel_batch.py` runs the lightweight health + worktree preflight before it merges a completed batch into the authoritative TSV/JSON state.
