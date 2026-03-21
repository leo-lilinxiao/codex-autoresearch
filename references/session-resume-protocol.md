# Session Resume Protocol

Detect and recover from interrupted runs. Resume from the last consistent retained state instead of guessing from stale artifacts.

## JSON State File

The primary recovery source is `autoresearch-state.json`, an atomic-write snapshot updated after each main iteration. Schema:

```json
{
  "version": 1,
  "run_tag": "<run-tag>",
  "mode": "loop",
  "config": {
    "goal": "<goal text>",
    "scope": "<glob pattern>",
    "metric": "<metric name>",
    "direction": "lower | higher",
    "verify": "<verify command>",
    "guard": "<guard command or null>"
  },
  "state": {
    "iteration": 15,
    "baseline_metric": 47,
    "best_metric": 28,
    "best_iteration": 12,
    "current_metric": 28,
    "last_commit": "a1b2c3d",
    "last_trial_commit": "d4e5f6a",
    "last_trial_metric": 31,
    "keeps": 8,
    "discards": 5,
    "crashes": 1,
    "no_ops": 0,
    "blocked": 0,
    "splits": 0,
    "consecutive_discards": 2,
    "pivot_count": 0,
    "last_status": "discard"
  },
  "supervisor": {
    "recommended_action": "relaunch | stop | needs_human",
    "should_continue": true,
    "terminal_reason": "none | blocked | iteration_cap_reached | ...",
    "last_exit_kind": "turn_complete | session_split | terminal | ...",
    "last_turn_finished_at": "2026-03-19T08:20:10Z",
    "restart_count": 3,
    "stagnation_count": 0
  },
  "updated_at": "2026-03-19T08:15:32Z"
}
```

Write protocol: write to a uniquely named temporary file in the same directory, fsync, then rename to `autoresearch-state.json` (atomic). Never commit this file to git.

The `supervisor` object is optional. It is written by the runtime control plane (`autoresearch_runtime_ctl.py` and `autoresearch_supervisor_status.py`), is not required for normal session resume, and should be preserved if present.

## Detection Signals

At the start of every invocation, check for prior run artifacts in this order:

| Priority | Signal | File / Command | Weight |
|----------|--------|---------------|--------|
| 1 | **JSON state** | `autoresearch-state.json` exists and is valid JSON with `version` field | **primary** |
| 2 | Results log | `research-results.tsv` exists and has a baseline row | strong |
| 3 | Lessons file | `autoresearch-lessons.md` exists | moderate |
| 4 | Git history | Recent commits with `experiment:` prefix | moderate |
| 5 | Output dirs | `debug/`, `fix/`, `security/`, `ship/` directories with timestamped subdirectories | weak |

If none of these signals are present, proceed with a fresh run (normal wizard flow).

## Helper Script

Prefer the bundled helper script over ad hoc TSV/JSON parsing:

```bash
python3 <skill-root>/scripts/autoresearch_resume_check.py
```

Here `<skill-root>` is the directory containing the loaded `SKILL.md`. In the common repo-local install this is usually `.agents/skills/codex-autoresearch`.

It reconstructs retained state from the TSV, tolerates parallel worker rows, and returns one of four decisions:

- `full_resume`
- `mini_wizard`
- `tsv_fallback`
- `fresh_start`

The helper's decision is the single control-plane source for:

- `autoresearch_launch_gate.py`
- `autoresearch_health_check.py`
- `autoresearch_resume_prompt.py`
- any runtime-managed resume prompt generation inside `autoresearch_runtime_ctl.py`

Do not reimplement a second TSV/JSON reconciliation path in those scripts.

Use `--write-repaired-state` when TSV recovery is valid and you want to rewrite `autoresearch-state.json` before resuming.

## Recovery Priority Matrix

| # | Condition | Decision |
|---|-----------|----------|
| 1 | JSON valid + helper reports `full_resume` | **Full resume** (skip wizard) |
| 2 | JSON valid + helper reports `mini_wizard` | **Mini-wizard** (1 round) |
| 3 | JSON missing or unusable + helper reports `tsv_fallback` | **TSV fallback** |
| 4 | Helper reports `fresh_start` | **Fresh start** |

### Priority 1: Full Resume

When the helper reports `full_resume`:

1. Restore loop variables from the JSON `state` and `config`.
2. Print a resume banner:
   ```
   Resuming from iteration {state.iteration}, retained metric: {state.current_metric}, best metric: {state.best_metric}.
   {state.keeps} kept, {state.discards} discarded, {state.crashes} crashed so far.
   Source: autoresearch-state.json (validated against TSV main rows)
   ```
3. Skip the wizard entirely.
4. Read the lessons file if present.
5. Let the runtime preflight confirm that the configured verify command still resolves before continuing.
6. If the current metric drifted, log a `drift` row and continue from the recalibrated state.
7. Managed-runtime resume requires an existing `autoresearch-launch.json`. Runs that predate that manifest are no longer resumable under the detached runtime; start fresh through the single-entry launch flow instead of synthesizing compatibility artifacts.

### Priority 2: Mini-Wizard

When JSON exists but the helper reports `mini_wizard`:

1. Show what was detected:
   - prior run tag, iteration count, retained metric, and last status from JSON,
   - the helper's mismatch reasons (for example retained-metric mismatch, missing main iteration row, or stale counters).
2. Ask exactly one question:
   - resume from JSON state, or
   - start fresh and archive old artifacts.
3. If resuming, use JSON `config` as the authoritative config and re-confirm it in a single block.
4. If starting fresh, archive prior persistent run-control artifacts with `.prev` suffixes and proceed with the full wizard. In the managed-runtime path, this should happen through `autoresearch_runtime_ctl.py launch --fresh-start ...`.

### Priority 3: TSV Fallback

When JSON is missing or unusable but the helper reports `tsv_fallback`:

1. Reconstruct retained state from integer main rows in `research-results.tsv`.
2. If the user wants to resume, prefer:
   ```bash
   python3 <skill-root>/scripts/autoresearch_resume_check.py --write-repaired-state
   ```
3. Present one condensed confirmation block sourced from the reconstructed state.
4. After confirmation, create a fresh launch manifest and continue from the next main iteration.
5. Do not start the detached runtime directly from bare TSV fallback without a confirmed launch manifest.

### Priority 4: Fresh Start

When the helper reports `fresh_start`:

1. Proceed with the normal wizard flow.
2. Rename prior persistent run-control artifacts to `.prev` variants if they exist. In the managed-runtime path, this archival is performed by `autoresearch_runtime_ctl.py launch --fresh-start ...`. This includes `research-results.tsv`, `autoresearch-state.json`, `autoresearch-launch.json`, `autoresearch-runtime.json`, and `autoresearch-runtime.log`.
3. Keep `autoresearch-lessons.md` unless it is clearly corrupt.

## Edge Cases

### Corrupt JSON

If `autoresearch-state.json` exists but is not valid JSON, treat it as unusable. Rename to `.bak` if you need to preserve it, then rely on TSV fallback or fresh start.

### Corrupt Results Log

If `research-results.tsv` is missing a baseline row, has a broken header, or contains unparsable metric cells, treat it as corrupt and start fresh.

### Different Goal

If the recovered config clearly belongs to a different goal than the current request, start fresh and archive the old run-control artifacts to `.prev` through `autoresearch_runtime_ctl.py launch --fresh-start ...`.

## Session Splitting

Long-running sessions accumulate context that may be compacted by the CLI, causing protocol drift. Session splitting is a controlled shutdown that preserves all state for automatic resumption in a fresh session.

### When to Split

Split the session when any of the following is true:

- Context compaction has occurred 2 or more times in the current session
- The iteration counter has reached 40 or higher
- The Protocol Fingerprint Check (Phase 8.7) has failed 3 or more times in the current session
- 10 or more iterations have passed since the last compaction with no improvement in fingerprint check reliability

### How to Split

1. Confirm that `autoresearch-state.json`, `research-results.tsv`, and `autoresearch-lessons.md` are consistent and up to date.
2. Log a TSV row with status `split` and description `[SESSION-SPLIT] <reason>` (e.g., `[SESSION-SPLIT] compaction count 2, iteration 42`).
3. Print a completion summary that includes:
   - Current iteration, retained metric, best metric
   - Reason for splitting
   - Instructions: "Re-invoke the skill to resume automatically."
4. Stop the loop. Do not continue iterating.

### Operator Guidance

The public human entry stays `$codex-autoresearch`.

- New interactive run: answer the confirmation questions, then reply `go`.
- After approval, Codex writes `autoresearch-launch.json` and starts the detached runtime controller automatically.
- Later `status`, `stop`, and `resume` requests should still come through the same skill entrypoint.

Advanced backend commands are available when scripting or debugging the controller:

```bash
python3 <skill-root>/scripts/autoresearch_runtime_ctl.py status --repo /path/to/repo
python3 <skill-root>/scripts/autoresearch_runtime_ctl.py stop --repo /path/to/repo
```


## Integration Points

- **autonomous-loop-protocol.md:** Run the launch gate before the wizard. Initialize new run artifacts only after baseline is measured.
- **results-logging.md:** Main integer rows define retained state; worker rows are audit detail only.
- **interaction-wizard.md:** Mini-wizard uses helper mismatch reasons instead of raw row counts.
- **health-check-protocol.md:** Deep integrity checks use the resume helper, not row-count heuristics.
- **exec-workflow.md:** Exec mode skips session resume, archives the configured results log plus repo-root state artifacts, and requires the workflow to clean up its scratch JSON state before exit.
