# Plan Workflow

Convert a goal into a validated, ready-to-launch `$codex-autoresearch` configuration.

**Two-phase boundary:** All clarifying questions happen before launch. If `--launch` is used to start a loop from the plan output, the loop follows the autonomous-loop-protocol and never pauses to ask the user.

## Purpose

Use this mode when the user knows what they want but not how to define the loop.

## Trigger

- `$codex-autoresearch Mode: plan`
- "help me set up autoresearch"
- "plan an autoresearch run"
- "what should my metric be"

## Inputs

Required:

- Goal

Derived or collected:

- Scope
- Metric
- Direction
- Verify
- Guard
- Iterations
- Required keep labels
- Required stop labels
- Verify format (`scalar` or `metrics_json`)
- Primary metric key (when `verify_format=metrics_json`)
- Acceptance criteria (when multi-metric stop gating is needed)
- Required keep criteria (when some metrics must never regress)

## Flags

| Flag | Purpose |
|------|---------|
| `--goal "<text>"` | Inline goal text |
| `--scope "<glob>"` | Pre-fill scope |
| `--metric "<name>"` | Pre-fill metric |
| `--direction higher|lower` | Pre-fill direction |
| `--verify "<command>"` | Pre-fill verify command |
| `--guard "<command>"` | Pre-fill guard |
| `--required-keep-label <label>` | Require retained-state eligibility labels before an improved result can become `keep` |
| `--required-stop-label <label>` | Require retained labels before a numeric stop condition can stop the run |
| `--verify-format scalar\|metrics_json` | Pre-fill verify output format (default `scalar`) |
| `--primary-metric-key <key>` | Pre-fill primary metric key for `metrics_json` mode |
| `--acceptance-criteria '<json>'` | Pre-fill acceptance criteria as JSON list of `{metric_key, operator, target}` |
| `--required-keep-criteria '<json>'` | Pre-fill required keep criteria as JSON list of `{metric_key, operator, target}` |
| `--launch` | Launch immediately after validation |
| `--iterations N` | Pre-fill bounded iteration count |

## Wizard

Use `interaction-wizard.md` to scan the repo and confirm the launch-ready plan before output or `--launch`.

Preferred field order:

1. Goal
2. Scope
3. Metric
4. Direction
5. Verify
6. Guard
7. Required keep labels (when only a specific mechanism/path/root cause should be allowed into retained state)
8. Required stop labels (when the success condition depends on mechanism/path/root cause, not just the number)
9. Launch

## Phases

### Phase 1: Capture Goal

Interpret the goal in one sentence.

Examples:

- "reduce type errors to zero"
- "improve p95 API latency"
- "raise coverage for auth middleware"

### Phase 2: Analyze Context

Inspect:

- repo structure,
- package and build files,
- test runners,
- benchmark scripts,
- lint and typecheck commands.

Run environment probes per `references/environment-awareness.md`:

- Detect available compute resources (CPU, RAM, GPU/NPU, disk).
- Detect installed toolchains and package managers.
- Use environment data to filter infeasible verify/guard commands and suggest resource-appropriate configurations.

### Phase 3: Suggest Scope

Produce 2-3 scope candidates when possible.

Rules:

- scope must resolve to at least one file,
- warn when scope is too broad,
- prefer implementation files over "entire repo" when a narrower scope is viable.

### Phase 4: Suggest Metric

Metric rules:

- outputs a number,
- can be parsed by a command,
- is stable enough to compare runs,
- is fast enough for iteration.

### Phase 5: Define Direction

Choose `higher` or `lower`.

### Phase 6: Construct Verify

The verify command must:

1. run the underlying tool,
2. expose the metric,
3. fail non-zero when the run crashes.

Dry-run the verify command when practical.

### Phase 7: Define Guard

Suggest a guard for regression-sensitive metrics.

Typical guards:

- tests
- typecheck
- build

### Phase 8: Confirm and Launch

Return a launch-ready block:

```text
$codex-autoresearch
Goal:
Scope:
Metric:
Direction:
Verify:
Guard:
Required keep labels:
Required stop labels:
Iterations:
```

When the analysis identifies a multi-metric scenario, the launch block should describe the acceptance thresholds in natural language inside the Goal field (e.g., "reduce bad_days, keeping hard_conflicts at 0 and saturday_events under 10") rather than exposing internal field names like `Verify format` or `Acceptance criteria`. The model translates these into the correct `--acceptance-criteria` and `--verify-format` flags internally when launching.

If the user says `launch`, switch to the generic loop with that config.

## Structured Output

Reply sections:

1. Goal
2. Suggested Scope
3. Suggested Metric
4. Verify Command
5. Guard
6. Required Keep Labels (when applicable)
7. Required Stop Labels (when applicable)
8. Launch Block

## Success Criteria

The workflow succeeds when the user can copy the generated block into `$codex-autoresearch` without ambiguity.
