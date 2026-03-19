# Session Resume Protocol

Detect and recover from interrupted runs. Resumes from the last consistent state instead of restarting from scratch.

## Detection Signals

At the start of every invocation, check for prior run artifacts in this order:

| Signal | File / Command | Weight |
|--------|---------------|--------|
| Results log | `research-results.tsv` exists and has data rows | strong |
| Lessons file | `autoresearch-lessons.md` exists | moderate |
| Git history | Recent commits with `experiment:` prefix | moderate |
| Output dirs | `debug/`, `fix/`, `security/`, `ship/` directories with timestamped subdirectories | weak |

If none of these signals are present, proceed with a fresh run (normal wizard flow).

## State Assessment

When at least one strong signal is detected:

### 1. Parse Results Log

Read `research-results.tsv`:

- Extract the last iteration number.
- Extract the metric direction comment.
- Extract the best metric value and its iteration.
- Extract the current metric value (last row).
- Count keeps, discards, crashes.
- Identify the run tag if present.

### 2. Validate Git State

- Check if the commit hash from the last log entry matches a real commit.
- Check if HEAD is at or after the last logged commit.
- Check `git status --porcelain` for uncommitted changes.

### 3. Validate Verify Command

- Extract the verify command from the results log context or recent git history.
- Attempt a dry run to confirm it still works.

## Resume Decision Matrix

| Results Log | Git Consistent | Verify Works | Decision |
|-------------|---------------|--------------|----------|
| valid | yes | yes | **Full resume** |
| valid | no (diverged) | yes | **Mini-wizard** |
| valid | yes | no (broken) | **Mini-wizard** |
| valid | no | no | **Fresh start** |
| corrupt | - | - | **Fresh start** (rename corrupt log) |
| missing | - | - | **Fresh start** |

## Full Resume

When state is fully consistent:

1. Print resume banner:
   ```
   Resuming from iteration {N}, best metric: {value} (iteration {best_iter}).
   {keeps} kept, {discards} discarded, {crashes} crashed so far.
   ```
2. Skip the wizard entirely.
3. Read the lessons file if present.
4. Run the verify command to establish the current metric as a sanity check.
5. If the current metric matches the last logged value (within tolerance), continue from iteration N+1.
6. If the metric has drifted, log a `drift` entry and recalibrate baseline before continuing.

## Mini-Wizard

When state is partially consistent:

1. Print what was detected:
   ```
   Found a previous run (iterations 0-{N}, best: {value}).
   Some state has changed since the last run.
   ```
2. Show what changed (git divergence, verify command failure, etc.).
3. Ask a single confirmation:
   - "Resume from where I left off?" (re-confirm scope, metric, verify)
   - "Start fresh?" (ignore previous run)
4. If resuming, re-validate all config fields in one round.
5. If starting fresh, rename the old results log with a `.prev` suffix and proceed normally.

## Fresh Start

When no prior run is detected or the user chooses to start fresh:

1. Proceed with the normal wizard flow.
2. If a previous results log exists, rename it to `research-results.prev.tsv`.
3. If a previous lessons file exists, keep it (lessons carry across runs).

## Edge Cases

### Multiple Previous Runs

If multiple `.prev` results files exist, keep the lessons file but do not attempt to merge results logs. Each run has its own log.

### Corrupted Results Log

If the results log exists but is unparseable:
1. Rename to `research-results.corrupt.tsv`.
2. Proceed as fresh start.
3. Preserve the lessons file if it is independently valid.

### Different Goal

If the detected previous run has a clearly different goal than the current request:
1. Treat as a fresh start.
2. Rename the old results log with `.prev` suffix.
3. Keep the lessons file (cross-goal learning is valid).

## Integration Points

- **autonomous-loop-protocol.md (Phase 0):** Session resume check runs before safety checks.
- **lessons-protocol.md:** Lessons file is a detection signal and is preserved across runs.
- **results-logging.md:** Results log is the primary detection signal.
- **interaction-wizard.md:** Mini-wizard is a reduced version of the full wizard (1 round max).
- **SKILL.md:** Load order includes session resume check before wizard.
