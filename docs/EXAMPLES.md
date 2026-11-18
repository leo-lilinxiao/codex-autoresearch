# Examples

Each example shows what you type and the setup Codex should confirm with you. Usually you only write the prompt; Codex finds the commands in your repository.

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

The score script should exit 0 and print a count even while the defects are still there. Add a separate guard only if it already passes before the run starts.

## Remove Type Errors

```text
$codex-autoresearch
Eliminate TypeScript errors under src without changing generated clients.
```

```text
Scope: src
Verify: node scripts/count-type-errors.mjs
Direction: lower
Target: 0
Guard: npm test
```

A small counting script in your project is more reliable than having Codex read compiler messages, which change from version to version.

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
Bring the search benchmark p95 to at most 200 ms without changing responses.
```

```text
Scope: src/search, migrations
Verify: python3 benchmarks/search_p95.py
Direction: lower
Target: 200
Guard: python3 -m pytest tests/search -q
```

Pin down fixtures, warmup, sample count, and machine load before you start. With a noisy benchmark, changes get kept or discarded by luck, so report the median of several runs (see the patterns at the end).

## Optimize a Noisy Multi-Metric Scheduler

```text
$codex-autoresearch
Raise judge_score to at least 0.80 while keeping hard schedule conflicts at zero.
```

```text
Scope: src/scheduler
Verify: python3 scripts/schedule_metrics.py
Metric parser: JSON key judge_score
Direction: higher
Target: 0.80
Guard: python3 scripts/check_schedule_constraints.py
```

The verify command can print other numbers for diagnosis, but only `judge_score` decides keep or discard. The guard makes sure every schedule stays feasible. Fix the seeds and keep the test cases out of the scope, so neither noise nor edited cases decide which experiments survive.

## Reduce Binary Size

```text
$codex-autoresearch
Reduce the release binary to at most 12 MB while all tests pass.
```

```text
Scope: src, Cargo.toml
Verify: cargo build --release --quiet && python3 scripts/binary_size_mb.py
Direction: lower
Target: 12
Guard: cargo test --quiet
```

The verify command may build things, but it must not change any file Git can see, tracked or untracked. Put build output in ignored directories.

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

Only use a scanner or test harness that gives the same number every time. A broad, judgment-heavy audit is better done with Codex directly.

## Foreground With Steering

```text
You: $codex-autoresearch reduce parser allocations from 14 to 5
Codex: [shows baseline, target, scope, verify, guard, and mode]
You: Foreground. Go.
```

Pause with the normal Codex Goal controls whenever you want to change direction. When you resume, the skill checks the event log before carrying on.

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

You can also give it a new direction. If the run is blocked, fix the reported cause first:

```text
$codex-autoresearch resume; generated files are authoritative, do not edit them
```

## Review A Run

```text
$codex-autoresearch show experiment history
```

The history table shows the baseline, every kept or discarded experiment with its numbers and description, and how the run ended. For something you can share:

```text
$codex-autoresearch generate an HTML report
```

The report is rebuilt from the event log each time and plays no part in resume or recovery.

## Metric Script Patterns

A number on the last line:

```python
print(error_count)
```

JSON on the last line:

```python
import json

print(json.dumps({"error_count": error_count, "passed": passed}))
```

With JSON, you name the metric key, such as `error_count`. The other fields are only for diagnosis; they never quietly turn into extra pass/fail rules.

The median of several runs, for noisy measurements:

```python
import statistics

print(statistics.median(run_benchmark() for _ in range(5)))
```
