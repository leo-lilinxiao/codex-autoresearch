# Exec Workflow

Non-interactive mode for CI/CD pipelines and automated invocations. All configuration is provided upfront -- no wizard, no conversation, no user interaction.

## Purpose

Use this mode when codex-autoresearch is invoked from a CI job, cron task, or automation script where no human is available to answer wizard questions.

## Trigger

- `$codex-autoresearch Mode: exec`
- `codex exec` with autoresearch skill context
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

If any required field is missing, exit immediately with code 2 and a JSON error.

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
| Session resume | full | disabled (always fresh start) |

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
    codex exec --skill codex-autoresearch \
      --goal "Reduce type errors" \
      --scope "src/**/*.ts" \
      --metric "type error count" \
      --direction lower \
      --verify "tsc --noEmit 2>&1 | grep -c error" \
      --iterations 20
  continue-on-error: true
```

### GitLab CI

```yaml
optimize:
  script:
    - codex exec --skill codex-autoresearch
        --goal "Raise test coverage"
        --scope "src/"
        --metric "coverage percentage"
        --direction higher
        --verify "pytest --cov=src --cov-report=term 2>&1 | grep TOTAL | awk '{print $NF}'"
        --guard "ruff check ."
        --iterations 15
  allow_failure: true
```

## Artifact Handling

Exec mode always starts fresh:
- If `research-results.tsv` exists from a prior run, rename it to `research-results.prev.tsv`.
- If `autoresearch-lessons.md` exists, read it for hypothesis filtering but never modify it.
- Do not revert prior experiment commits (assume external cleanup between CI runs).

## Constraints

- Always bounded: the `Iterations` field is mandatory to prevent runaway CI jobs.
- No wizard: if config is incomplete, fail fast with exit code 2.
- No web search: CI environments should not make unexpected network calls.
- No parallel: CI resource limits are unpredictable; use serial mode only.
- No session resume: every CI run starts fresh. Rename old results log to `.prev` if one exists.
- Lessons: read `autoresearch-lessons.md` if it exists in the repo (useful for persistent learning across CI runs), but **never create or modify it** during exec mode -- not even after keep or pivot decisions. Exec mode is read-only for lessons.

## Integration Points

- **SKILL.md:** Listed as the 7th mode in the mode table.
- **modes.md:** Added to the mode index.
- **structured-output-spec.md:** JSON output templates for exec mode.
- **environment-awareness.md:** Probes still run to filter infeasible hypotheses.
- **health-check-protocol.md:** Health checks still run but warnings go to stderr as JSON.
