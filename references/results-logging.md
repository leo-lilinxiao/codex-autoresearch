# Results Logging

Use a plain TSV log so the agent can learn from prior iterations.

## Generic Log File

Default filename:

```text
research-results.tsv
```

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
| `description` | One-sentence explanation of the iteration |

For multi-repo runs, the TSV `commit` column still records the **primary repo** commit. Per-repo commit provenance for companion repos lives in `autoresearch-state.json` (`state.last_repo_commits` and `state.last_trial_repo_commits`) so the primary audit trail stays compact while the JSON snapshot preserves cross-repo detail.

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

- `python3 <skill-root>/scripts/autoresearch_init_run.py ...`
  Initializes `research-results.tsv` and `autoresearch-state.json` together from the baseline measurement. Interactive runs record `config.session_mode` explicitly; foreground is the default, while background initialization should pass `--session-mode background`. `execution_policy` is only persisted for paths that actually spawn nested Codex sessions: background managed runs and exec. In exec mode it also archives the configured results log plus any repo-root `autoresearch-state.json` to `.prev` variants, clears stale default scratch state, and enforces the prelaunch commit gate. With the default repo-root filenames this means `research-results.prev.tsv` and `autoresearch-state.prev.json`; callers should let the helper perform that archival instead of manually renaming those files first. Multi-repo runs may add repeated `--repo-commit PATH=COMMIT` flags to persist companion-repo baseline provenance in JSON state.
- `python3 <skill-root>/scripts/autoresearch_set_session_mode.py --repo <repo> ...`
  Internal/scripted helper that synchronizes an existing interactive run's shared JSON state to `foreground` or `background` before the next iteration. Use it only for scripted recovery flows; the normal human-facing skill entrypoint should handle this sync internally, and background `start` already performs the same sync automatically when it resumes existing results/state.
- `python3 <skill-root>/scripts/autoresearch_record_iteration.py ...`
  Appends one authoritative main iteration row and updates JSON state atomically. Multi-repo runs may add repeated `--repo-commit PATH=COMMIT` flags to update companion-repo commit provenance while the TSV `commit` column continues to track the primary repo.
- `python3 <skill-root>/scripts/autoresearch_resume_check.py --repo <repo>`
  Reconstructs retained state from the TSV and decides `full_resume`, `mini_wizard`, `tsv_fallback`, or `fresh_start`.
- `python3 <skill-root>/scripts/autoresearch_select_parallel_batch.py --batch-file ...`
  Logs worker rows, runs the batch-boundary health/worktree preflight, appends the main batch row, and updates JSON state once per batch. Worker batch items may include `repo_commits` for companion-repo provenance.
- `python3 <skill-root>/scripts/autoresearch_exec_state.py`
  Prints the deterministic exec scratch-state path under `/tmp` and cleans it up on `--cleanup`.
- `python3 <skill-root>/scripts/autoresearch_supervisor_status.py --repo <repo>`
  Computes whether the runtime control plane should relaunch, stop, or ask for human help after a finished turn.

In exec mode, the helper scripts keep JSON state in scratch storage by default instead of repo-root `autoresearch-state.json`. The exec workflow must clean that scratch state before exiting so exec persists only `research-results.tsv`.

## Rules

- Create the log only after the baseline metric is known.
- Append after every iteration, including crashes, no-ops, refines, pivots, and searches.
- Never commit the log.
- Treat the log, JSON state, and lessons file as autoresearch-owned artifacts: leave them unstaged and ignore them when checking experiment scope.
- Re-read the latest entries before choosing the next idea.
- The standalone health-check helper reports warnings/blockers as JSON. Append a TSV row only when the runtime explicitly decides to log a blocker or recovery event.

## Cross-Validation with JSON State

`autoresearch-state.json` is the primary recovery source for session resume (see `references/session-resume-protocol.md`). The TSV log and the JSON state file serve complementary roles:

| Aspect | `research-results.tsv` | `autoresearch-state.json` |
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

During session resume, `python3 <skill-root>/scripts/autoresearch_resume_check.py --repo <repo>` reconstructs the retained state from the TSV and compares it with `autoresearch-state.json`. Any mismatch triggers a mini-wizard rather than a silent full resume.
