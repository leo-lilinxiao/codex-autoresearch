# Examples

These examples show the user prompt and the measurement contract Codex should confirm. Users normally provide only the prompt; Codex discovers the commands from the repository.

## Fix Failing Cases

```text
$codex-autoresearch
Reduce `python3 scripts/score.py` error_count to 0 without changing the evaluation.
```

```text
Scope: src
Verify: python3 scripts/score.py
Metric parser: JSON key error_count
Direction: lower
Target: 0
Guard: none
```

The score script should exit zero and report a numeric count even before the defects are fixed. Add a separate regression guard only if it already passes at baseline.

## Remove Type Errors

```text
$codex-autoresearch
Eliminate TypeScript errors under src without changing generated clients.
```

Useful contract:

```text
Scope: src
Verify: node scripts/count-type-errors.mjs
Direction: lower
Target: 0
Guard: npm test
```

A project-owned counting script is more reliable than parsing changing compiler prose in the skill prompt.

## Raise Coverage

```text
$codex-autoresearch
Raise branch coverage for src/auth to at least 90% with meaningful tests.
```

```text
Scope: tests/auth, src/auth
Verify: python3 scripts/branch_coverage.py
Direction: higher
Target: 90
Guard: python3 -m pytest -q
```

Coverage is the metric; the full test suite is the guard.

## Reduce Latency

```text
$codex-autoresearch
Bring the search benchmark p95 below 200 ms without changing responses.
```

```text
Scope: src/search, migrations
Verify: python3 benchmarks/search_p95.py
Direction: lower
Target: 200
Guard: python3 -m pytest tests/search -q
```

Stabilize fixtures, warmup, sample count, and machine load before launch. A noisy benchmark produces untrustworthy keeps and discards.

## Optimize a Noisy Multi-Metric Scheduler

```text
$codex-autoresearch
Raise judge_score to at least 0.80 while keeping hard schedule conflicts at zero.
```

```text
Scope: src/scheduler, tests/cases
Verify: python3 scripts/schedule_metrics.py
Metric parser: JSON key judge_score
Direction: higher
Target: 0.80
Guard: python3 scripts/check_schedule_constraints.py
```

The verify command may emit other numeric fields for diagnosis, but only `judge_score` drives keep or discard. The guard enforces feasibility. Fix seeds and representative cases before optimizing so noise does not decide which experiments survive.

## Reduce Binary Size

```text
$codex-autoresearch
Reduce the release binary below 12 MB while all tests pass.
```

```text
Scope: src, Cargo.toml
Verify: cargo build --release --quiet && python3 scripts/binary_size_mb.py
Direction: lower
Target: 12
Guard: cargo test --quiet
```

The verify command may build artifacts, but it must not modify tracked or untracked project files seen by Git. Put build output in ignored directories.

## Reproducible Security Findings

```text
$codex-autoresearch
Reduce the deterministic critical finding count to 0 in src/api.
```

```text
Scope: src/api, tests/security
Verify: python3 scripts/critical_findings.py
Direction: lower
Target: 0
Guard: npm test
```

Use only a scanner or test harness whose numeric output is stable. A broad subjective audit is better handled as ordinary Codex work.

## Foreground With Steering

```text
You: $codex-autoresearch reduce parser allocations from 14 to 5
Codex: [shows baseline, target, scope, verify, guard, and mode]
You: Foreground. Go.
```

Pause through the normal Codex Goal controls when you want to redirect the strategy. On resume, the skill validates the event log before continuing.

## Background Overnight

```text
You: $codex-autoresearch get lint_warning_count to 0
Codex: [shows confirmed run]
You: Background with Full Access. Go.
```

Later:

```text
$codex-autoresearch show status
```

After a user stop, continue with:

```text
$codex-autoresearch resume
```

You can also supply a new direction. If blocked, first resolve the reported cause:

```text
$codex-autoresearch resume; generated files are authoritative, do not edit them
```

## Review A Run

```text
$codex-autoresearch show experiment history
```

The history table includes baselines, retained experiments, discarded trials, terminal events, metrics, and descriptions. For a shareable visual snapshot:

```text
$codex-autoresearch generate an HTML report
```

The report is regenerated from validated events and does not participate in resume or recovery.

## Metric Script Patterns

Scalar final line:

```python
print(error_count)
```

JSON final line:

```python
import json

print(json.dumps({"error_count": error_count, "passed": passed}))
```

The JSON form requires an explicit metric key such as `error_count`. Extra fields remain diagnostic and do not become hidden secondary acceptance rules.
