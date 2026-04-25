# Results Logging

This is the detailed reference for TSV/state semantics. During normal loop execution, treat `autoresearch_record_iteration.py` or `autoresearch_select_parallel_batch.py` as the authoritative closeout step instead of reopening this file.

## Workspace-Owned Results Directory

Default user-visible directory:

```text
<workspace_root>/autoresearch-results/
```

Fixed files:

```text
results.tsv
state.json
launch.json
runtime.json
runtime.log
lessons.md
context.json
```

### `context.json` Schema

`context.json` is the canonical run context written by `autoresearch_workspace.py`. It replaces the former `autoresearch-hook-context.json` and serves as the single source of truth for session hooks and control-plane helpers to locate the active run's artifacts.

```json
{
  "version": 2,
  "active": true,
  "session_mode": "foreground",
  "workspace_root": "/abs/path/to/workspace",
  "artifact_root": "/abs/path/to/workspace/autoresearch-results",
  "primary_repo": "/abs/path/to/repo",
  "repo_targets": [
    {"path": "/abs/path/to/repo", "scope": "src/**/*.ts", "role": "primary"},
    {"path": "/abs/path/to/companion", "scope": "lib/**/*.py", "role": "companion"}
  ],
  "verify_cwd": "workspace_root",
  "results_path": "/abs/path/to/workspace/autoresearch-results/results.tsv",
  "state_path": "/abs/path/to/workspace/autoresearch-results/state.json",
  "launch_path": "/abs/path/to/workspace/autoresearch-results/launch.json",
  "runtime_path": "/abs/path/to/workspace/autoresearch-results/runtime.json",
  "log_path": "/abs/path/to/workspace/autoresearch-results/runtime.log",
  "updated_at": "2026-04-15T12:00:00Z"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `version` | `int` | Schema version, currently `2` |
| `active` | `bool` | Whether this run context is active |
| `session_mode` | `string \| null` | `"foreground"`, `"background"`, or `null` |
| `workspace_root` | `string` | Absolute path to the workspace root |
| `artifact_root` | `string` | Absolute path to `autoresearch-results/` |
| `primary_repo` | `string` | Absolute path to the primary git repo |
| `repo_targets` | `array` | List of managed repos with path, scope, and role |
| `verify_cwd` | `string \| null` | `"workspace_root"` or `"primary_repo"` |
| `results_path` | `string` | Absolute path to `results.tsv` |
| `state_path` | `string` | Absolute path to `state.json` |
| `launch_path` | `string \| null` | Absolute path to `launch.json` (background only) |
| `runtime_path` | `string \| null` | Absolute path to `runtime.json` (background only) |
| `log_path` | `string \| null` | Absolute path to `runtime.log` (background only) |
| `updated_at` | `string` | ISO 8601 UTC timestamp |

Each managed repo also stores a git-local pointer at `.git/codex-autoresearch/pointer.json` that references back to the workspace-owned `context.json`.

Add a direction comment at the top:

```text
# metric_direction: higher
```

or

```text
# metric_direction: lower
```

## Header Comments

The first comment line declares the metric direction. Additional comment lines may include:

```text
# environment: cpu=8 ram=16384MB gpu=A100(40GB) python=3.11 container=docker
# metric_direction: lower
# mode: loop
# run_tag: any-types-v2
# parallel: serial
# web_search: enabled
```

## Generic Schema

```tsv
iteration	commit	metric	delta	guard	status	description
```

## Columns

| Column | Meaning |
|--------|---------|
| `iteration` | Integer main iteration counter starting at `0` for the baseline. Parallel worker detail rows use suffix notation (`5a`, `5b`, `5c`) |
| `commit` | Short hash for the kept or attempted commit. Use `-` only for meta rows that did not test a committed trial (for example `pivot`, `search`, or a strategy-only `refine`) |
| `metric` | Parsed metric value for that row's attempt or recalibration |
| `delta` | `metric - retained_metric_before_row` |
| `guard` | `pass`, `fail`, or `-` |
| `status` | See Status Values below |
| `description` | One-sentence explanation of the iteration. Structured keep/stop-gating labels may prefix the sentence as `[labels: foo, bar] ...` |

For multi-repo runs, the TSV `commit` column still records the **primary repo** commit. Per-repo commit provenance for companion repos lives in `state.json` (`state.last_repo_commits` and `state.last_trial_repo_commits`) so the primary audit trail stays compact while the JSON snapshot preserves cross-repo detail.

## Metrics And Acceptance Contract

The metrics model is intentionally small:

- `verify_format = scalar | metrics_json`
- `primary_metric_key`
- `acceptance_criteria`
- `required_keep_criteria`

`acceptance_criteria` and `required_keep_criteria` are lists of criterion objects:

```json
[
  {"metric_key": "accuracy", "operator": ">=", "target": 0.9}
]
```

Do not use legacy `metric` / `op` / `value` fields, an `all` wrapper, or the `!=` operator.

When `verify_format=scalar`, the verify command must emit a single numeric metric as its final non-empty output line. Do not heuristically scrape banner text, earlier lines, or arbitrary regex matches during the loop. If the command is noisy, tighten the verify command during setup so the final line is mechanically parseable.

When `verify_format=metrics_json`, the verify command must print a JSON object as its final non-empty output line. That JSON object is the metrics map used by the helpers. It must include `primary_metric_key` plus every metric referenced by `acceptance_criteria` and `required_keep_criteria`. Helpers must not synthesize missing metrics from the scalar primary metric in this mode.

`results.tsv` records only the primary metric. Structured metrics and acceptance states live in `state.json`.

## Structured Labels For Keep / Stop Gating

Some goals need more than a numeric threshold. Example: "Only retain improvements from the production path, and stop only when latency <= 120 ms and the retained keep uses the required production path and real backend."

For those runs:

- persist `config.required_keep_labels` when retention itself has a structural requirement
- persist `config.required_stop_labels` in JSON config/state
- record structured iteration labels with `autoresearch_record_iteration.py --label ...`
- let the helper write a canonical TSV prefix like:

```text
[labels: production-path, real-backend] optimized query path preserved real backend behavior
```

Would-be `keep` rows that miss `required_keep_labels` are mechanically downgraded to `discard` before they can update retained state.

The supervisor only treats a retained result as terminal when the configured final gates are satisfied:

- if `acceptance_criteria` is configured, the retained result satisfies it,
- if `stop_condition` is configured, the retained result satisfies it,
- the retained keep labels cover every `required_stop_labels` entry.

This keeps causal or implementation-specific success criteria machine-checkable instead of leaving them in free-form prose.

## Status Values

| Status | Meaning |
|--------|---------|
| `baseline` | Initial measurement before any changes |
| `keep` | Change improved the metric and passed guard |
| `discard` | Change did not improve or failed guard |
| `crash` | Verification crashed or produced an error |
| `no-op` | No actual diff was produced |
| `blocked` | Hard blocker encountered, loop stopped |
| `refine` | Strategy adjustment within current approach (see `pivot-protocol.md`) |
| `pivot` | Strategy abandoned, fundamentally new approach (see `pivot-protocol.md`) |
| `search` | Web search performed for external knowledge (see `web-search-protocol.md`) |
| `drift` | Metric drifted from expected value during session resume |

## Example

```tsv
# metric_direction: lower
iteration	commit	metric	delta	guard	status	description
0	a1b2c3d	14	0	-	baseline	current pytest failure count
1	b2c3d4e	9	-5	pass	keep	reduce fixture startup overhead
2	c3d4e5f	11	+2	-	discard	expand retries in API client
3	d4e5f6a	0	0	-	crash	refactor parser with bad import
4	e5f6a7b	9	0	fail	discard	inline auth cache but break regression guard
```

## Parallel Batch Notation

When parallel experiments are active (see `references/parallel-experiments-protocol.md`), log worker detail rows first, then append one authoritative main row for the batch:

```tsv
5a	abc1234	38	-3	pass	keep	[PARALLEL worker-a] narrowed auth types
5b	-	42	+1	pass	discard	[PARALLEL worker-b] wrapper approach
5c	-	41	0	-	crash	[PARALLEL worker-c] timeout after 20m
5	abc1234	38	-3	pass	keep	[PARALLEL batch] selected worker-a: narrowed auth types
```

Only integer rows (`0`, `1`, `2`, `5`) define the retained state. Worker rows are audit detail and never increment `state.iteration` by themselves.

## Helper Scripts

Prefer the bundled helper scripts for stateful artifact updates:

These helper scripts live in the skill bundle. Do not confuse them with the target repo's own `scripts/` directory.

Define `<skill-root>` as the directory that contains the loaded `SKILL.md`. In the common repo-local install this is usually `.agents/skills/codex-autoresearch`, so the exact command becomes `python3 .agents/skills/codex-autoresearch/scripts/...`.

- `python3 <skill-root>/scripts/autoresearch_init_run.py --repo <primary_repo> --workspace-root <workspace_root> ...`
  Initializes `autoresearch-results/results.tsv` and `autoresearch-results/state.json` together from the baseline measurement, writes canonical `context.json`, and writes git-local pointers for every managed repo. Interactive runs record `config.session_mode` explicitly; foreground is the default, while background initialization should pass `--session-mode background`. `execution_policy` is only persisted for paths that actually spawn nested Codex sessions: background managed runs and exec. Multi-repo runs may add repeated `--repo-commit PATH=COMMIT` flags to persist companion-repo baseline provenance in JSON state. Runs with structural success criteria may add repeated `--required-keep-label LABEL` flags to protect retained state and repeated `--required-stop-label LABEL` flags so the supervisor only stops when the retained keep also carries those labels.
- `python3 <skill-root>/scripts/autoresearch_set_session_mode.py --repo <repo> ...`
  Internal/scripted helper that synchronizes an existing interactive run's shared JSON state to `foreground` or `background` before the next iteration. Use it only for scripted recovery flows; the normal human-facing skill entrypoint should handle this sync internally, and background `start` already performs the same sync automatically when it resumes existing results/state.
- `python3 <skill-root>/scripts/autoresearch_record_iteration.py ...`
  Appends one authoritative main iteration row and updates JSON state atomically. Multi-repo runs may add repeated `--repo-commit PATH=COMMIT` flags to update companion-repo commit provenance while the TSV `commit` column continues to track the primary repo. Repeated `--label LABEL` flags record structured keep/stop-gating labels on the attempted row and retained state.
- `python3 <skill-root>/scripts/autoresearch_resume_check.py --repo <repo>`
  Reconstructs retained state from the TSV and decides `full_resume`, `mini_wizard`, `tsv_fallback`, or `fresh_start`.
- `python3 <skill-root>/scripts/autoresearch_select_parallel_batch.py --batch-file ...`
  Logs worker rows, runs the batch-boundary health/worktree preflight, appends the main batch row, and updates JSON state once per batch. Worker batch items may include `repo_commits` for companion-repo provenance and `labels` for structured keep/stop gating.
- `python3 <skill-root>/scripts/autoresearch_exec_state.py`
  Prints the deterministic exec scratch-state path under `/tmp` and cleans it up on `--cleanup`.
- `python3 <skill-root>/scripts/autoresearch_supervisor_status.py --repo <repo>`
  Computes whether the runtime control plane should relaunch, stop, or ask for human help after a finished turn.

In exec mode, the helper scripts keep JSON state in scratch storage by default and must clean that scratch state before exiting.

## Rules

- Create the log only after the baseline metric is known.
- Record every completed experiment before starting the next one.
- In normal loop execution, do that closeout through the bundled helper scripts rather than by hand.
- Append after every iteration, including crashes, no-ops, refines, pivots, and searches.
- Never commit the Results directory.
- Treat `autoresearch-results/` and git-local pointers as autoresearch-owned artifacts: leave them unstaged and ignore them when checking experiment scope.
- Re-read the latest entries before choosing the next idea.
- The standalone health-check helper reports warnings/blockers as JSON. Append a TSV row only when the runtime explicitly decides to log a blocker or recovery event.

## Cross-Validation with JSON State

`autoresearch-results/state.json` is the primary recovery source for session resume (see `references/session-resume-protocol.md`). The TSV log and the JSON state file serve complementary roles:

| Aspect | `autoresearch-results/results.tsv` | `autoresearch-results/state.json` |
|--------|----------------------|--------------------------|
| **Purpose** | Full audit trail of every iteration | Compact snapshot for fast resume |
| **Content** | One main row per iteration, plus optional worker detail rows | Aggregated counters and config |
| **Recovery role** | Fallback when JSON is missing | Primary recovery source |
| **Cross-validation** | Reconstruct retained state from integer main rows | Must match the reconstructed retained state |

### Consistency Rules

- **Main iteration match:** `state.iteration` must equal the highest integer iteration label in the TSV.
- **Retained metric match:** `state.current_metric` must equal the retained metric after replaying the integer main rows. After a `discard`, the TSV row records the attempted metric, but `state.current_metric` stays at the last kept metric.
- **Last trial match:** `state.last_trial_metric` must equal the metric on the latest integer main row.
- **Multi-repo provenance:** when `state.last_repo_commits` or `state.last_trial_repo_commits` are present, they are auxiliary JSON-only provenance keyed by repo path. They are not reconstructed from the TSV and therefore do not participate in TSV/JSON consistency blocking.
- **Parallel tolerance:** Worker rows (`5a`, `5b`, `5c`) are ignored for `state.iteration` matching. They provide audit detail only.

During session resume, `python3 <skill-root>/scripts/autoresearch_resume_check.py --repo <repo>` reconstructs the retained state from the TSV and compares it with `autoresearch-results/state.json`. Any mismatch triggers a mini-wizard rather than a silent full resume.
