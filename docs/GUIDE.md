# User Guide

Codex Autoresearch runs one measurable experiment loop in one Git repository. It is deliberately smaller than a general task orchestrator: Codex reasons about the code, while the skill enforces measurement, commit ownership, rollback, and a durable audit trail.

## Start A Run

Invoke the skill with a result, not an implementation plan:

```text
$codex-autoresearch reduce scripts/score.py error_count to 0
```

Codex scans the repository and confirms seven values before writing:

| Value | Meaning | Example |
|---|---|---|
| Goal | Desired repository outcome | Eliminate type errors |
| Scope | Relative files or directories it may edit | `src`, `tests/types` |
| Metric | Numeric outcome | type error count |
| Direction | Whether lower or higher is better | lower |
| Verify | Command that prints the metric | `python3 scripts/score.py` |
| Target | Number that means done | `0` |
| Guard | Optional baseline-passing regression check | `npm test` |

You also choose foreground or background and may set an iteration limit.

Choices and approval already given carry forward. Codex asks about missing launch decisions, then continues without repeated confirmation. Requests for status, history, or a report go directly to the requested result.

Autoresearch requires a clean named branch. Commit or stash existing changes before launch. Scope entries are path prefixes, not globs: use `src` rather than `src/**/*.ts`.

## Metric Output

The final non-empty stdout line must be a finite number:

```text
0
```

Or it may be a JSON object when one key is selected explicitly:

```json
{"error_count": 0, "passed": 42}
```

In that case Codex configures `error_count` as the metric key. The command must exit zero when measurement succeeds, even if the metric is currently poor.

A failing test command is therefore usually a guard, not a scalar metric command. For error-reduction work, prefer a small project-owned score script that always exits zero and reports the count.

## Verify And Guard

Verify answers: **did the target metric improve?**

Guard answers: **did the trial preserve required behavior?**

```text
Verify: python3 scripts/score.py       -> JSON error_count
Guard:  python3 -m pytest -q          -> exit code 0
```

The guard is optional, but if configured it must pass at baseline. An improved metric with a failing guard is reverted.

## Foreground

Foreground stays in the current Codex task. After you approve the run, the skill initializes the baseline and creates or reuses an official Codex Goal. Goal continuation keeps the loop moving and supports Codex's normal pause and resume experience.

Each iteration:

1. Codex uses the measured results and previous experiments to choose a hypothesis.
2. Codex changes one coherent thing inside scope.
3. The control script creates a trial commit.
4. It runs verify and, for an improvement, the guard.
5. It keeps the commit or creates a revert commit.
6. It appends the result and continues.

The Goal is marked complete only after the retained metric reaches the confirmed target.

## Background

Background launches a detached controller and returns the TUI to you. The controller starts one fresh `codex exec` worker for one experiment, validates its event, then starts the next worker if the run remains active.

This process hierarchy is intentional:

```text
your Codex task -> controller -> one worker at a time
```

Background defaults to Full Access so the worker can commit and revert. You may explicitly choose `workspace-write`, but sandbox restrictions around `.git` can stop the run. There is no automatic permission fallback.

Use the skill itself for control:

```text
$codex-autoresearch show the background status
$codex-autoresearch stop the background run
$codex-autoresearch resume the background run
$codex-autoresearch resume with this direction: focus on parser allocation
```

Resume continues the existing configuration. Add a direction when you want to steer the strategy. The foreground task does not need to poll the controller.

## Run States

| Status | Meaning |
|---|---|
| `not_initialized` | No current run exists |
| `initialization_failed` | Baseline setup failed; inspect diagnostics and archive before retrying |
| `active` | More experiments may run |
| `complete` | Retained metric reached target |
| `stopped` | User stop or iteration limit |
| `blocked` | Progress requires an external change |
| `error` | A command, Git, state, or worker contract failed |

An unsuccessful hypothesis is `discard`, not `blocked`. Background `orphaned` means events still say active but the recorded controller is gone. Inspect the reported worker PID and runtime log. If no worker is alive, stop can close the event state; a live orphaned worker must exit or be terminated before stop, resume, or archive.

## Artifacts

All state is under `autoresearch-results/`:

```text
autoresearch-results/
├── run.json
├── events.jsonl
├── logs/
├── runtime.json       # background only
├── runtime.log        # background only
└── report.html        # generated on request
```

`run.json` is immutable configuration. `events.jsonl` is the append-only source of truth for current state. Logs contain complete command and worker output.

Do not edit these files. A malformed or inconsistent file stops the run instead of being reconstructed. To start a different goal, ask the skill to archive the current run first; archives remain below `autoresearch-results/archive/`.

If the current run is still active, stop a background run first. For foreground, clear the old Codex Goal with `/goal clear`, then ask the skill to archive the run and start the new goal.

## History And Reports

Use the same skill entry to inspect any initialized run:

```text
$codex-autoresearch show experiment history
$codex-autoresearch export experiment history as TSV
$codex-autoresearch generate an HTML report
```

History renders a terminal table from the fully validated event log. TSV is emitted on request for spreadsheets or scripts. The HTML command writes a self-contained snapshot to `autoresearch-results/report.html` with the metric trajectory, keep/discard timeline, commits, and log links.

These views never replace or update `events.jsonl`. Delete or regenerate the HTML report at any time; an active run requires a fresh report command to include later iterations.

## Git History

Kept trial:

```text
autoresearch: remove parser allocation
```

Discarded trial:

```text
Revert "autoresearch: cache parser nodes"
autoresearch: cache parser nodes
```

The extra revert commit is the cost of a non-destructive, traceable rollback. Autoresearch never stages its result directory and rejects concurrent branch, HEAD, or out-of-scope changes.

## Errors And Recovery

Errors name the exact invariant and, for commands, the full log path. Status also reports expected/current Git state and dirty paths. Fix the cause before resume.

- Bad metric output: make the final line a scalar or configure one JSON key.
- Verify exits nonzero: make measurement success return zero.
- Baseline guard fails: repair the baseline or choose a valid guard.
- Dirty or out-of-scope files: restore ownership boundaries; do not widen scope merely to hide the problem.
- Command creates files: change the command so measurement is side-effect-free.
- Worker produces no event: inspect its worker log; the controller stops rather than relaunching blindly.
- Controller disappears: inspect both controller and worker liveness in status before recovery.
- Rollback fails: recover Git manually and archive the run. An unverified trial cannot be resumed as retained state.

## Choosing A Task

Good tasks have a repeatable metric and a meaningful target. Examples include zero failing cases, at least 90% coverage, p95 below 200 ms, no critical findings in a deterministic scanner, or a project-specific score above a threshold.

For subjective design, one-time migrations, releases, or deployment, use ordinary Codex. If the goal is open-ended, first work with Codex to define a stable benchmark, then invoke autoresearch.
