# Exec Workflow

Non-interactive mode for CI/CD pipelines and automated invocations. All configuration is provided upfront -- no wizard, no conversation, no user interaction.

## Purpose

Use this mode when codex-autoresearch is invoked from a CI job, cron task, or automation script where no human is available to answer wizard questions.

## Trigger

- `$codex-autoresearch Mode: exec`
- `codex exec` prompt that explicitly invokes `$codex-autoresearch` in `Mode: exec`
- Environment variable: `AUTORESEARCH_MODE=exec`

## Required Config (All Upfront)

All fields must be provided at invocation time. There is no wizard fallback.

| Field | Required | Source |
|-------|----------|--------|
| Goal | yes | prompt or env `AUTORESEARCH_GOAL` |
| Scope | yes | prompt or env `AUTORESEARCH_SCOPE` |
| Metric | yes | prompt or env `AUTORESEARCH_METRIC` |
| Direction | yes | prompt or env `AUTORESEARCH_DIRECTION` |
| Verify | yes | prompt or env `AUTORESEARCH_VERIFY` |
| Guard | no | prompt or env `AUTORESEARCH_GUARD` |
| Iterations | yes (always bounded) | prompt or env `AUTORESEARCH_ITERATIONS` |
| Execution policy | no | prompt or env `AUTORESEARCH_EXECUTION_POLICY` (`danger_full_access` by default) |
| Verify format | no | prompt or env `AUTORESEARCH_VERIFY_FORMAT` (`scalar` or `metrics_json`, default `scalar`) |
| Primary metric key | no | prompt or env `AUTORESEARCH_PRIMARY_METRIC_KEY` (defaults to the metric name; set it explicitly for `metrics_json` when the JSON key differs) |
| Acceptance criteria | no | prompt or env `AUTORESEARCH_ACCEPTANCE_CRITERIA` (JSON list of `{metric_key, operator, target}`) |
| Required keep criteria | no | prompt or env `AUTORESEARCH_REQUIRED_KEEP_CRITERIA` (JSON list of `{metric_key, operator, target}`) |

If any required field is missing, exit immediately with code 2 and a JSON error.

In Codex CLI, `codex exec` accepts a prompt. Do not assume a skill-specific `--skill` flag exists; invoke the skill in the prompt itself.

Before using `codex exec` in CI, configure Codex CLI authentication outside the skill itself. In controlled automation environments, this skill assumes `danger_full_access` by default, so prefer `codex exec --dangerously-bypass-approvals-and-sandbox ...` unless you intentionally want to test the sandboxed `workspace_write` path. For programmatic runs, API key authentication is the preferred option.

## Behavior Differences from Interactive Mode

| Aspect | Interactive | Exec |
|--------|------------|------|
| Wizard | 1-5 rounds | none |
| Iterations | bounded or unbounded | always bounded (required) |
| Output | human-readable text | structured JSON |
| Progress | every 5 iterations + completion | JSON line per iteration |
| Web search | available | disabled by default |
| Parallel | user opt-in | disabled by default |
| Lessons | read + write | read only (do not write in CI) |
| JSON state | `autoresearch-results/state.json` | scratch-only under `/tmp`, removed by the exec workflow before exit |
| Session resume | full | disabled (fresh start; prior JSON/TSV renamed to `.prev`) |
| Execution policy | chosen during launch | `danger_full_access` by default, `workspace_write` only when explicitly requested |

## JSON Output Format

### Per-Iteration Line (stdout)

```json
{"iteration": 1, "commit": "abc1234", "metric": 41, "delta": -6, "guard": "pass", "status": "keep", "description": "narrowed auth types"}
```

### Completion Summary (stdout, last line)

```json
{
  "status": "completed",
  "baseline": 47,
  "best": 38,
  "best_iteration": 5,
  "total_iterations": 10,
  "keeps": 4,
  "discards": 5,
  "crashes": 1,
  "improved": true,
  "exit_code": 0
}
```

### Error Output (stderr)

```json
{"error": "missing required field: Verify", "exit_code": 2}
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Improved -- best metric is better than baseline in the requested direction |
| 1 | No improvement -- ran all iterations without improving the baseline |
| 2 | Hard blocker -- could not start or encountered an unrecoverable error |

## CI Integration Examples

### GitHub Actions

```yaml
- name: Autoresearch optimization
  run: |
    codex exec --dangerously-bypass-approvals-and-sandbox <<'PROMPT'
    $codex-autoresearch
    Mode: exec
    Goal: Reduce type errors
    Scope: src/**/*.ts
    Metric: type error count
    Direction: lower
    Verify: tsc --noEmit 2>&1 | grep -c error
    Iterations: 20
    PROMPT
  continue-on-error: true
```

### GitLab CI

```yaml
optimize:
  script:
    - |
      codex exec --dangerously-bypass-approvals-and-sandbox <<'PROMPT'
      $codex-autoresearch
      Mode: exec
      Goal: Raise test coverage
      Scope: src/
      Metric: coverage percentage
      Direction: higher
      Verify: pytest --cov=src --cov-report=term 2>&1 | grep TOTAL | awk '{print $NF}'
      Guard: ruff check .
      Iterations: 15
      PROMPT
  allow_failure: true
```

Most exec runs should stay on the default scalar metric path. Only switch to `AUTORESEARCH_VERIFY_FORMAT=metrics_json` when the verify command already emits a final-line JSON metrics map and the goal truly needs multiple thresholds. In that mode, keep stop/retention thresholds in `AUTORESEARCH_ACCEPTANCE_CRITERIA` and `AUTORESEARCH_REQUIRED_KEEP_CRITERIA`; use `Guard` only for regression checks such as tests, typecheck, or a smoke build.

## Artifact Handling

Exec mode always starts fresh:
- If `autoresearch-results/results.tsv` already exists from a prior run, archive it before writing the new log.
- Exec mode does not write or update `autoresearch-results/state.json`; it uses scratch state only.
- If `autoresearch-results/lessons.md` exists, read it for hypothesis filtering but never modify it.
- Do not revert prior experiment commits (assume external cleanup between CI runs).

When using the bundled helper scripts in exec mode:
Here `<skill-root>` is the directory containing the loaded `SKILL.md`. In the common repo-local install this is usually `.agents/skills/codex-autoresearch`.

- `python3 <skill-root>/scripts/autoresearch_init_run.py --repo <primary_repo> --workspace-root <workspace_root> --mode exec ...` defaults its JSON state to a deterministic scratch file under `/tmp/codex-autoresearch-exec/...`.
- In that default helper flow, do not manually rename old `autoresearch-results/results.tsv` or `autoresearch-results/state.json` first. `autoresearch_init_run.py` performs the fresh-start archival it owns.
- The initialized `autoresearch-results/results.tsv` header includes `# mode: exec`, so `autoresearch_resume_check.py` can rediscover the matching scratch state without a manual `--state-path`.
- `python3 <skill-root>/scripts/autoresearch_record_iteration.py ...` and `python3 <skill-root>/scripts/autoresearch_select_parallel_batch.py ...` automatically reuse that scratch state when the workspace JSON state file is absent.
- Before exiting, run `python3 <skill-root>/scripts/autoresearch_exec_state.py --cleanup` so exec mode removes scratch JSON state and leaves the persistent workspace-owned audit artifacts in place: `autoresearch-results/results.tsv` plus inactive canonical context metadata (`autoresearch-results/context.json` and the repo's git-local pointer).
- Treat that cleanup as the **final serial helper step**. Do not run it in parallel with `autoresearch_record_iteration.py`, `autoresearch_select_parallel_batch.py`, or any other helper that still needs the scratch state.
- If you override `--state-path` manually, you are responsible for removing that custom scratch file before exit.

## Constraints

- Always bounded: the `Iterations` field is mandatory to prevent runaway CI jobs.
- No wizard: if config is incomplete, fail fast with exit code 2.
- No launch question: do not ask for "go" or any extra confirmation; the prompt/env config is the approval.
- No web search: CI environments should not make unexpected network calls.
- No parallel: CI resource limits are unpredictable; use serial mode only.
- No session resume: every CI run starts fresh. When using the default helper flow, let `autoresearch_init_run.py --repo <primary_repo> --workspace-root <workspace_root> --mode exec ...` perform the archival automatically instead of hand-renaming artifacts.
- Dirty worktree: `autoresearch_init_run.py --repo <primary_repo> --workspace-root <workspace_root>` runs the prelaunch commit gate in exec mode. If `git status --porcelain` shows anything beyond autoresearch-owned artifacts before launch, it emits a blocker and exits with code 2 instead of asking.
- Lessons: read `autoresearch-results/lessons.md` if it exists in the workspace (useful for persistent learning across CI runs), but **never create or modify it** during exec mode -- not even after keep or pivot decisions. Exec mode is read-only for lessons.

## Integration Points

- **SKILL.md:** Listed as the 7th mode in the mode table.
- **modes.md:** Added to the mode index.
- **structured-output-spec.md:** JSON output templates for exec mode.
- **environment-awareness.md:** Probes still run to filter infeasible hypotheses.
- **health-check-protocol.md:** The standalone helper remains available, but exec mode does not automatically invoke the detached-runtime health preflight. CI wrappers may call `autoresearch_health_check.py --repo <primary_repo>` explicitly if they want the same structured integrity report before running.
