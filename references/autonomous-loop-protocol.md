# Autonomous Loop Protocol

This is the detailed protocol for the generic Codex research loop.

## Loop Modes

- `unbounded`: default. If the user does not specify `Iterations`, keep iterating until interrupted or a hard blocker appears.
- `bounded`: when the user explicitly sets `Iterations: N`.

## Required Inputs

Before entering the loop, confirm these are known:

- `Goal`
- `Scope`
- `Metric`
- `Direction`
- `Verify`

Optional:

- `Guard`
- `Iterations`
- `Run tag`
- `Stop condition`

If any required input is missing, use the wizard contract from `references/interaction-wizard.md` to scan the repo and clarify with the user.

## Phase 0: Preconditions

Fail fast if the loop would be unsafe. Clarify first if the intent is unclear.

### Ask-Before-Act

Before starting any loop, ALWAYS:

1. Scan the repo to understand context.
2. Ask at least one round of clarifying questions based on what you found -- confirm scope, metric, verify command, guard, and iteration count with the user.
3. Present a plain-language summary for the user to approve.
4. Only start the loop after the user explicitly says "go" / "start" / "launch" or equivalent.

Never silently infer all fields and start iterating. A 30-second confirmation is always cheaper than wasted iterations.

**Two-phase boundary:** All questions happen BEFORE launch. Once the user says "go", the loop becomes fully autonomous. NEVER pause to ask the user anything during the loop -- not for clarification, not for confirmation, not for permission. If you encounter ambiguity mid-loop, apply best practices, log your reasoning in the commit message, and keep iterating. The user may be asleep.

### Safety Checks

1. Confirm the repo is under git if the workflow depends on commits.
2. Inspect `git status --porcelain`.
3. If unrelated user changes are present, do not start the commit/revert loop.
4. Confirm the scope resolves to real files.
5. Confirm the verify command exists and is plausible for this repo.
6. If a guard exists, confirm it is a pass/fail command.

### Dirty Worktree Rule

The loop may commit and revert repeatedly. That is only safe when the workspace is isolated.

If `git status --porcelain` is non-empty:

- continue only if the changes are clearly part of the current run and the user has approved continuing,
- otherwise switch to `plan` mode or ask the user for a clean branch or worktree.

Never absorb unrelated user edits into experiment commits.

## Phase 1: Read

Before the first edit:

1. Read all in-scope files.
2. Read configuration or build files that influence verification.
3. Read the latest results log if one exists.
4. Read recent git history relevant to the scoped files.

Before every later iteration:

1. Re-read the changed files.
2. Read the last 10-20 results rows.
3. Read recent commits or diffs to avoid repeating bad ideas.

## Phase 2: Baseline

Run the verify command on the current state before making changes.

Record:

- baseline metric value,
- guard result,
- current commit hash,
- a short baseline description.

If the baseline itself fails unpredictably, do not enter the optimization loop. Either repair the setup first or switch to `debug` or `fix` mode.

## Phase 3: Ideate

Choose one concrete hypothesis.

Good hypotheses:

- "Reduce retries from 5 to 2 to lower latency without changing behavior."
- "Add tests for uncovered auth edge cases to raise coverage."
- "Inline the hot path to reduce allocations."

Bad hypotheses:

- "Refactor several modules and see what happens."
- "Clean things up."

Priority order:

1. stabilize flaky setup,
2. exploit the last successful direction,
3. try an untested idea,
4. simplify while preserving the metric,
5. attempt a larger directional change when small ideas stall.

## Phase 4: Modify

Make one focused change within scope.

Rules:

- the change should fit in one sentence,
- do not edit guard artifacts merely to satisfy the guard,
- do not broaden scope mid-iteration unless the user agrees.

## Phase 5: Commit

Commit before verification when the workspace is safe to isolate.

Recommended sequence:

```bash
git add -- <scoped-files>
git diff --cached --name-only
git commit -m "experiment: <what changed and why>"
```

Rules:

- stage only files owned by the experiment,
- inspect the staged file list before committing,
- if there is no diff, log `no-op` and move on,
- prefer descriptive `experiment:` commit messages.

If the workspace is not safe for commits, do not force an iterative git loop. Stop and ask for isolation.

## Phase 6: Verify

Run the mechanical verify command.

Capture:

- metric value,
- relevant stderr or stdout excerpt,
- wall clock duration,
- crash signal if any.

Timeout rule:

- if verification takes more than 2x the established baseline time without a good reason, treat it as a failed iteration.

## Phase 6.5: Guard

If `Guard` is defined, run it after a metric improvement.

Interpretation:

- verify answers "did the target metric improve?"
- guard answers "did the change break anything important?"

If guard fails:

1. revert the experiment,
2. log the result as discarded because of guard failure,
3. optionally attempt up to 2 reworks if the failure is clearly fixable without changing tests or the guard.

## Phase 7: Decide

### Keep

Keep the commit when:

- the metric improved in the requested direction,
- the guard passed or no guard exists,
- and the complexity cost is justified.

### Discard

Discard the iteration when:

- the metric stayed flat or regressed,
- the guard failed,
- or the change added too much complexity for too little gain.

#### Simplicity Override

- Marginal improvement (< 1%) combined with significant complexity increase = discard.
- Metric unchanged but code becomes simpler = keep.

Preferred rollback:

```bash
git reset --hard HEAD~1
```

This keeps the git history clean across many iterations. The results log (`research-results.tsv`) serves as the true audit trail for all experiments, including discarded ones.

Fallback: if `git reset --hard HEAD~1` fails (e.g., merge conflicts or unusual state), use `git revert --no-edit HEAD` instead.

### Crash

If the run crashes:

1. inspect the error,
2. fix trivial mistakes if the hypothesis is still valid,
3. retry at most 3 quick times,
4. otherwise revert and log `crash`.

## Phase 8: Log

Append the outcome to the results log defined in `references/results-logging.md`.

Always log:

- iteration number,
- commit hash or `-`,
- metric,
- delta vs best known result,
- guard outcome,
- status,
- one-line description.

The results log stays uncommitted.

## Phase 9: Repeat

For bounded runs:

- stop after `Iterations` completes,
- or earlier if the goal is achieved and the user asked to stop on success.

For unbounded runs:

- NEVER STOP. NEVER ASK "should I continue?". The user may be asleep.
- NEVER pause to ask any question during the loop. If something is unclear, apply best practices and keep going.
- Continue iterating until explicitly interrupted or a hard blocker appears.
- If you run out of obvious ideas, revisit the results log for patterns, try combinations, or attempt bolder changes. Pausing to ask is not an option.

### Stuck Recovery

If 5 consecutive iterations are discarded:

1. Re-read all in-scope files from scratch.
2. Re-read the original goal.
3. Review the entire results log for patterns -- what worked, what failed, what correlates.
4. Try combining elements from previously successful changes.
5. Try the opposite of recently failed directions.
6. Attempt a bolder, architecture-level change.

## Progress Reporting

Every 5 iterations and at completion, summarize:

- baseline vs best metric,
- keep/discard/crash counts,
- the last few statuses,
- the next likely direction.

## Stop Conditions

Stop immediately if:

- the repo is not safe for iterative commits,
- verification cannot produce a mechanical metric,
- the environment is too flaky to trust the results,
- the user interrupts,
- or the loop requires external actions the user has not approved.
