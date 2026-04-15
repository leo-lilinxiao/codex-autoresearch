# Autonomous Loop Protocol

This is the detailed reference for the generic Codex research loop.

During active execution, keep `runtime-hard-invariants.md` plus the selected mode workflow in memory first. Use this file when you need the full setup, recovery, artifact, or escalation details behind the loop.

## Loop Modes

- `unbounded`: default. If the user does not specify `Iterations`, keep iterating until interrupted or another terminal condition is reached (goal/stop condition satisfied, soft-blocker handoff, or hard blocker).
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
- `Required keep labels` (when the run should only retain results from a specific mechanism, path, backend, or root-cause signal)
- `Required stop labels` (when the goal has a structural or causal success requirement, not just a numeric threshold)
- `Verify format` — `scalar` (default) or `metrics_json`; use `metrics_json` when the verify command outputs a JSON object with multiple metrics as its final line
- `Primary metric key` — which key in the metrics JSON to use as the TSV primary metric; defaults to the metric name
- `Acceptance criteria` — list of `{metric_key, operator, target}` thresholds the retained result must satisfy before the run can stop (see `references/results-logging.md` Metrics And Acceptance Contract)
- `Required keep criteria` — list of `{metric_key, operator, target}` hard gates every retained result must satisfy to enter `keep` state; use when some metrics must never regress regardless of primary metric improvement
- `Rollback policy` (required before launch if destructive rollback may be used)

For every new interactive loop, use the wizard contract from `references/interaction-wizard.md` to scan the repo, clarify with the user, and confirm the launch-ready config before the loop begins.

## Phase 0: Preconditions

Fail fast if the loop would be unsafe. Clarify first if the intent is unclear.

### Session Resume Check

Before anything else, check for a prior interrupted run per `references/session-resume-protocol.md`:

Use the launch gate first:

```bash
python3 <skill-root>/scripts/autoresearch_launch_gate.py --repo /path/to/repo
```

1. Resolve the current run through the git-local pointer and `autoresearch-results/context.json`, then check `autoresearch-results/state.json` first (primary recovery source), followed by `autoresearch-results/results.tsv`, `autoresearch-results/lessons.md`, and recent `experiment:` commits.
2. Apply the Recovery Priority Matrix from `session-resume-protocol.md`:
   - JSON valid + TSV consistent -> full resume (skip wizard).
   - JSON valid + TSV inconsistent -> mini-wizard (1 round).
   - JSON missing + TSV exists -> TSV fallback (reconstruct state, confirm, then create a fresh launch manifest).
   - JSON corrupt -> rename to `.bak`, fall back to TSV.
3. If no prior run is detected, proceed with fresh setup.

Launch-gate interpretation:
- `fresh` -> continue with the confirmation flow for a new launch.
- `resumable` -> resume from saved state without inventing a second operator entrypoint.
- `needs_human` / `blocked_start` -> report the issue or service the runtime-control request first.

Exec-mode exception:
- Do not resume a prior run.
- Rename prior persistent run-control artifacts to `.prev` and start fresh.
- Ignore any old exec scratch state except for cleanup at fresh start, and let the exec workflow remove the new scratch state before exit.

### Run Artifact Initialization

Do not create `autoresearch-results/results.tsv` or `autoresearch-results/state.json` before the baseline metric is known.

After Phase 2 establishes the baseline, initialize both artifacts together:

```bash
python3 <skill-root>/scripts/autoresearch_init_run.py --repo <primary_repo> --workspace-root <workspace_root> ...
```

This writes the baseline TSV row (`iteration = 0`) and the matching JSON snapshot in one step.

Here `<skill-root>` is the directory containing the loaded `SKILL.md`. In the common repo-local install this is usually `.agents/skills/codex-autoresearch`, so the exact command becomes `python3 .agents/skills/codex-autoresearch/scripts/...`.

Bundled helpers expose `--force` only as an internal maintenance override for tests or deliberate manual recovery. Normal skill flow should prefer explicit fresh-start archival instead of using `--force` to bypass legacy-layout or existing-artifact protection.

Exec-mode exception:
- Let the helper scripts use their scratch JSON state under `/tmp/codex-autoresearch-exec/...`.
- Clean that scratch state before exit with `python3 <skill-root>/scripts/autoresearch_exec_state.py --cleanup`.

### Environment Probe

Run environment detection per `references/environment-awareness.md`:

1. Detect CPU, RAM, disk, GPU/NPU, toolchains, container, and network availability.
2. Store the environment profile for hypothesis filtering in Phase 3.
3. Log the environment summary in the results log header.

### Ask-Before-Act

Before starting any interactive loop, ALWAYS:

1. Scan the repo to understand context.
2. Ask at least one round of clarifying questions based on what you found -- confirm scope, metric, verify command, run style (until interrupted vs bounded), and any rollback approval needed for unattended execution.
   - If the task spans multiple repos, confirm one primary repo plus any companion repos, each with an explicit per-repo scope.
3. Present a plain-language summary for the user to approve.
4. Only start the loop after the user explicitly says "go" / "start" / "launch" or equivalent.

Never silently infer all fields and start iterating. A 30-second confirmation is always cheaper than wasted iterations.

**Two-phase boundary:** All questions happen BEFORE launch. Before the user says "go", require an explicit run-mode choice: **foreground** or **background**. If the user chooses foreground, keep the loop in the same Codex session and use the shared helper scripts directly. If the user chooses background, call `autoresearch_runtime_ctl.py launch --repo <primary_repo> --workspace-root <workspace_root>` so the confirmed launch manifest and detached runtime are created in one script-level handoff. The launch manifest may describe either a single primary repo or a primary repo plus companion repos with separate scopes. Background runtime cycles launch non-interactive `codex exec` sessions with the generated runtime prompt supplied on stdin. Background launch manifests carry an `execution_policy`; this skill now defaults that policy to `danger_full_access`, so detached sessions normally run with `--dangerously-bypass-approvals-and-sandbox` unless a caller explicitly opts into sandboxed `workspace_write`. If that background `codex exec` session cannot be launched, the runtime must transition to `needs_human` instead of silently falling back to an idle state. If an explicit stop request cannot actually terminate the detached runner, the runtime must also transition to `needs_human` instead of claiming the run is fully stopped. After launch, NEVER pause to ask the user anything during the loop -- not for clarification, not for confirmation, not for permission. If you encounter ambiguity mid-loop, apply best practices, log your reasoning in the commit message, and keep iterating. The user may be asleep.

Exec-mode exception:
- Do not ask clarifying or launch questions.
- Treat the prompt/environment config as authoritative.
- After safety checks pass, launch immediately.
- If safety checks fail, emit the JSON error/blocker and exit with code 2.

### Safety Checks

1. Confirm the repo is under git if the workflow depends on commits.
2. Inspect `git status --porcelain`.
3. If unrelated user changes are present, do not start the commit/revert loop.
4. Confirm the scope resolves to real files.
5. Confirm the verify command exists and is plausible for this repo.
6. If a guard exists, confirm it is a pass/fail command.
7. If destructive rollback may be needed, get approval during setup before launch and prefer a dedicated experiment branch/worktree for unattended runs.

### Autoresearch-Owned Artifacts

Treat these files as experiment-owned artifacts, not unrelated user changes:

- `autoresearch-results/results.tsv`
- `autoresearch-results/state.json`
- `autoresearch-results/context.json`
- `autoresearch-results/lessons.md`
- `autoresearch-results/launch.json`
- `autoresearch-results/runtime.json`
- `autoresearch-results/runtime.log`
- `.tmp`, `.bak`, and `.prev` variants of those files

They may stay uncommitted between iterations and across resumes, but they must never be staged in experiment commits.

### Dirty Worktree Rule

The loop may commit and revert repeatedly. That is only safe when the workspace is isolated.

If `git status --porcelain` is non-empty **during Phase 0 (before launch)**:

- If the only changes are autoresearch-owned artifacts, continue.
- In interactive modes, otherwise ask the user during the wizard phase: "I see uncommitted changes. Are these part of the current experiment, or should I work on a clean branch?"

- If the user confirms the changes are part of the experiment, continue.
- If the user says no, suggest `plan` mode or a clean branch/worktree.
- In `exec` mode, any other pre-existing changes are a hard blocker. Do not ask; emit the blocker and exit with code 2.

If the worktree becomes dirty **after launch** (external modification mid-loop):

- Log a hard blocker: "External changes detected in worktree. Stopping to prevent data loss."
- Do not ask the user (two-phase boundary). Stop the loop and report.

Never absorb unrelated user edits into experiment commits.

## Phase 1: Read

Before the first edit:

1. Read all in-scope files.
2. Read configuration or build files that influence verification.
3. Read the latest results log if one exists.
4. Read recent git history relevant to the scoped files.
5. Read `autoresearch-results/lessons.md` if it exists (see `references/lessons-protocol.md`).

Before every later iteration:

1. Re-read the changed files.
2. Read the last 10-20 results rows.
3. Read recent commits or diffs to avoid repeating bad ideas.
4. Consult lessons for relevant insights on the current strategy direction.

## Phase 2: Baseline

Run the verify command on the current state before making changes.

Record:

- baseline metric value,
- guard result,
- current commit hash,
- a short baseline description.

Immediately after the baseline is known, initialize the run artifacts with `<skill-root>/scripts/autoresearch_init_run.py --repo <primary_repo> --workspace-root <workspace_root>`.

If the baseline itself fails unpredictably, do not enter the optimization loop. Either repair the setup first or switch to `debug` or `fix` mode.

## Phase 3: Ideate

Choose one concrete hypothesis. When parallel mode is active (see `references/parallel-experiments-protocol.md`), generate N hypotheses instead of one.

### Hypothesis Filtering

Before committing to a hypothesis, filter against environment constraints per `references/environment-awareness.md`. Do not attempt hypotheses that require resources the environment lacks (e.g., GPU optimization without GPU, package installation without network).

### Multi-Perspective Reasoning

Apply the four-lens framework from `references/hypothesis-perspectives.md` when appropriate:
- **Optimist:** most impactful change?
- **Skeptic:** why might this fail? (cross-check results log)
- **Historian:** what do past results and lessons say?
- **Minimalist:** simpler version possible?

Skip perspectives for obvious, mechanical fixes.

### Lessons Consultation

Consult `autoresearch-results/lessons.md` (see `references/lessons-protocol.md`):
- Prefer strategies that succeeded in similar contexts.
- Avoid strategies that consistently failed.
- Adapt successful strategies from related goals.

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
3. try an untested idea informed by lessons and perspectives,
4. simplify while preserving the metric,
5. attempt a larger directional change when small ideas stall.

## Phase 4: Modify

Make one focused change within scope.

Rules:

- the change should fit in one sentence,
- do not edit guard artifacts merely to satisfy the guard,
- do not broaden scope mid-iteration. If a change requires out-of-scope files, abandon the hypothesis, log the limitation, and try a different approach that stays within scope.

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
- never stage autoresearch-owned artifacts,
- inspect the staged file list before committing,
- if there is no diff, log `no-op` and move on (counts toward the consecutive-discard threshold for stuck recovery),
- prefer descriptive `experiment:` commit messages.

Commit failure policy:

- if `git commit` reports "nothing to commit", treat the attempt as `no-op` with no retry;
- if `git commit` fails because of a transient repo-plumbing issue (for example `index.lock` or another temporary git file lock), re-read `git status` and retry once;
- if the retry still fails, or a pre-commit hook / repository policy rejects the diff, treat the attempt as `crash`; fix only trivial issues if the hypothesis is still valid, retry at most 2 quick times, otherwise restore a clean worktree with the approved rollback strategy and log `crash`;
- if the repository itself is broken (permissions, corrupt index, disk full), treat it as a hard blocker.

If the workspace is not safe for commits, log a hard blocker and stop the loop. Do not ask -- report the situation in the completion summary.

## Phase 6: Verify

Run the mechanical verify command.

Capture:

- metric value,
- relevant stderr or stdout excerpt,
- wall clock duration,
- crash signal if any.

Metric parsing contract:

- if `verify_format=scalar`, the final non-empty verify output line must be a single numeric scalar parseable as the metric value;
- if `verify_format=metrics_json`, follow the final-line JSON contract in `references/results-logging.md`;
- do not guess from banner text, earlier lines, or arbitrary regex scraping during the loop; if output is noisy, tighten the verify command during setup instead;
- if verify output is unparseable, rerun verify once only to rule out transient truncation or shell noise; if the second run is still unparseable, treat the attempt as `crash`;
- if the baseline itself cannot be parsed, do not launch the loop; fix the verify command first or stop with a blocker.

Timeout rule:

- if verification takes more than 2x the established baseline time without a good reason, treat it as a failed iteration.

## Phase 6.5: Guard

Guard is a separate gate from Verify, not part of it. The execution sequence is strictly: Phase 6 (Verify) -> Phase 6.5 (Guard) -> Phase 7 (Decide).

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

Rollback follows the strategy approved during setup:

```bash
git reset --hard HEAD~1
```

- Use `git reset --hard HEAD~1` only when the run is isolated in a dedicated experiment branch/worktree and that destructive rollback was explicitly approved before launch.
- Otherwise use `git revert --no-edit HEAD`.
- Never roll back unrelated user changes or autoresearch-owned artifacts.

The results log (`autoresearch-results/results.tsv`) serves as the true audit trail for all experiments, including discarded ones.

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
- delta vs the retained metric before the row,
- guard outcome,
- status,
- one-line description.

The results log stays uncommitted.

### JSON State Update

Do not hand-edit `autoresearch-results/results.tsv` or `autoresearch-results/state.json`.

- For serial/main rows, prefer:
  ```bash
  python3 <skill-root>/scripts/autoresearch_record_iteration.py ...
  ```
- For parallel batches, prefer:
  ```bash
  python3 <skill-root>/scripts/autoresearch_select_parallel_batch.py --batch-file ...
  ```

These helpers keep two key semantics consistent:

1. `state.current_metric` is the retained metric after the keep/discard decision.
2. `state.last_trial_metric` is the metric from the latest attempted main iteration.
3. Parallel batch merges reuse the same lightweight health/worktree preflight before updating the authoritative run state.

In exec mode, this JSON state is scratch-only. It must not remain in the repo after completion.

## Phase 9: Repeat

For bounded runs:

- stop after `Iterations` completes,
- or earlier if the goal is achieved and the user asked to stop on success.

For unbounded runs:

- NEVER ask "should I continue?" after launch. The user may be asleep.
- NEVER pause to ask any question during the loop. If something is unclear, apply best practices and keep going.
- Continue iterating until the goal is reached, the user explicitly interrupts, the configured iteration cap is reached, a true blocker appears, or the run reaches the documented soft-blocker handoff.
- If you run out of obvious ideas, revisit the results log for patterns, try combinations, or attempt bolder changes. Pausing to ask is not an option.

### PIVOT / REFINE Stuck Recovery

Replace the simple "5 discards -> re-read" with the graduated escalation system from `references/pivot-protocol.md`:

- **3 consecutive discards -> REFINE:** Adjust within current strategy. Consult lessons, change parameters or target files, log as `refine`.
- **5 consecutive discards -> PIVOT:** Abandon current strategy entirely. Re-read everything, choose a fundamentally different approach, log as `pivot`.
- **2 PIVOTs without improvement -> Web Search:** Escalate to web search per `references/web-search-protocol.md` (if available and not disabled).
- **3 PIVOTs without improvement -> Soft Blocker:** Print a warning, stop the current run, and report that human review / broader scope / a better metric is needed.

A single `keep` resets all escalation counters to zero.

After every PIVOT, extract a lesson per `references/lessons-protocol.md`.

### Lessons Extraction

After every `keep` decision, `autoresearch_record_iteration.py` appends a positive lesson immediately after the authoritative TSV/JSON update. After every PIVOT, the same helper appends a strategic lesson the same way. At managed-runtime completion, `autoresearch_runtime_ctl.py` appends a summary lesson when no lesson was written in the last 5 iterations of the same run. See `references/lessons-protocol.md` for structure and persistence.

## Phase 8.5: Health Check

Health Check runs strictly between Log (Phase 8) and Phase 8.7 (Re-Anchoring). The execution sequence is: Phase 8 (Log) -> Phase 8.5 (Health Check) -> Phase 8.7 (Re-Anchoring) -> Phase 9 (Repeat).

Run health checks per `references/health-check-protocol.md`:

- **Every managed-runtime cycle boundary:** before each detached `codex exec` session (and therefore before every relaunch), `autoresearch_runtime_ctl.py` runs `autoresearch_health_check.py` for disk space, git state, verify command existence, and resume-helper-based TSV/JSON integrity.
- **Commit safety at the same boundary:** when the managed repos are git-backed, `autoresearch_runtime_ctl.py` also runs `autoresearch_commit_gate.py` with the launch-manifest repo list and per-repo scopes before each detached session. Relaunch is blocked if staged autoresearch artifacts or out-of-scope worktree changes are present in any managed repo.
- **Extended review:** scope integrity, environment drift, verify/guard consistency, and context health when the workflow explicitly schedules the protocol-level extended checks.
- Log integrity should use the helper-script reconstruction of main rows and retained state, not raw TSV row counts.
- `autoresearch_health_check.py` only returns structured `ok / warn / block` findings. Any retries, repairs, or blocker logging must be implemented by the caller.
- Within a live Codex session, the model must still honor the same scope-aware commit rule before creating a trial commit; the runtime controller can only enforce these checks between detached sessions.

## Phase 8.7: Protocol Re-Anchoring

Re-Anchoring runs between Health Check (Phase 8.5) and Repeat (Phase 9). It defends against context drift caused by long-running sessions where automatic context compaction may discard protocol instructions.

### Trigger

Run the Protocol Fingerprint Check when any of the following is true:

- `iteration % 10 == 0`
- A context compaction warning was observed since the last check
- The agent notices it cannot recall a runtime checklist item or the selected mode workflow

### Protocol Fingerprint Check

A zero-token self-check. Use `runtime-hard-invariants.md` plus the selected mode workflow as the source of truth. Internally verify the exact Protocol Fingerprint Check published in `runtime-hard-invariants.md`; do not maintain a second, looser copy of the checklist here.

### On Failure

If any fingerprint item fails:

1. Re-read `references/runtime-hard-invariants.md`, `references/core-principles.md`, and the selected mode workflow from disk.
2. Re-read `references/autonomous-loop-protocol.md` only if the missing item concerns detailed escalation, recovery, or health-check behavior.
3. In the next TSV row's description, include the `[RE-ANCHOR]` tag to mark that a re-anchoring event occurred.
4. Continue the loop from Phase 9.

### Compaction Counter

Track the number of context compaction events observed during the session:

- **0 compactions (default):** Fingerprint check every 10 iterations.
- **1 compaction:** Fingerprint check every 5 iterations.
- **2 compactions:** Run the fingerprint check every iteration until stability returns. Re-read protocol files immediately on any failure.
- **3+ compactions:** Soft drift warning. Keep the loop running, run the fingerprint check every iteration, and re-anchor from disk on any failure.

## Progress Reporting

Every 5 iterations and at completion, summarize:

- baseline vs best metric,
- keep/discard/crash counts,
- the last few statuses,
- the next likely direction.

## Stop Conditions

A **hard blocker** is any condition that makes continued iteration unsafe or meaningless:

- the verify command no longer exists, or its final metric line remains unparseable after one clean retry,
- scope files have been deleted externally,
- the git repository is in a broken state,
- disk space is exhausted,
- the same crash appears 5+ times in a row with no variation,
- the repo is not safe for iterative commits,
- verification cannot produce a mechanical metric,
- the environment is too flaky to trust the results,
- the user interrupts,
- or the loop requires external actions not approved during the pre-launch wizard.

Stop immediately if any hard blocker appears. Do not ask the user -- log the blocker in the completion summary.

On hard blocker, log the blocker reason in TSV with status `blocked` and stop. Keep the retained-state fields in `autoresearch-results/state.json` unchanged (`current_metric`, `best_metric`, `best_iteration`, `last_commit`), but it is acceptable to advance audit counters such as `iteration`, `blocked`, `last_status`, and `last_trial_*` so the JSON snapshot stays aligned with the blocked TSV row. This preserves session resume without pretending the blocker improved the retained result.
