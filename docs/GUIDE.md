# User Guide

Codex Autoresearch runs one experiment loop in one Git repository, and that's all it does. Codex does the thinking about the code. The skill does the bookkeeping: it measures, commits, rolls back, and keeps a record you can check later.

## Start A Run

Tell the skill the result you want, not how to get there:

```text
$codex-autoresearch reduce scripts/score.py error_count to 0
```

Codex looks through the repository and confirms seven things before it changes anything:

| Value | Meaning | Example |
|---|---|---|
| Goal | What you want to achieve | Eliminate type errors |
| Scope | Files or directories Codex may edit | `src`, `tests/types` |
| Metric | The number being improved | type error count |
| Direction | Whether lower or higher is better | lower |
| Verify | Command that prints the metric | `python3 scripts/score.py` |
| Target | The number that means done | `0` |
| Guard | Optional check that must keep passing | `npm test` |

You also pick foreground or background, and you can set an iteration limit.

Codex won't ask again about anything you've already decided. It asks only for what's missing, then keeps going without checking in after every experiment. Asking for status, history, or a report just shows you that; it doesn't start anything.

You need a clean, named branch, so commit or stash your changes first. Scope entries are paths, not globs: write `src`, not `src/**/*.ts`.

## Metric Output

The last non-empty stdout line must be a finite number:

```text
0
```

Or a JSON object, if you name the key to read:

```json
{"error_count": 0, "passed": 42}
```

Here Codex would use `error_count` as the metric key. The command must exit with code 0 whenever it measured successfully, even if the number is bad. If the same code gives different numbers from run to run, report an aggregate such as the median of several runs to reduce noise.

That's why a failing test command usually makes a better guard than a metric. To count errors, use a small score script that exits 0 when measurement succeeds and prints the count, even if some tests failed.

## Verify And Guard

Verify answers: **did the metric improve?**

Guard answers: **does the required behavior still work?**

```text
Verify: python3 scripts/score.py       -> JSON error_count
Guard:  python3 -m pytest -q          -> exit code 0
```

The guard is optional, but if you set one, it must pass before the run starts. An improvement that fails the guard is rolled back. A command timeout stops the run with diagnostics.

Keep the verify script and its data out of the scope, so experiments can't change how they are measured.

## Foreground

Foreground runs inside your current Codex task. Once you approve, the skill measures the baseline and sets up a Codex Goal, or reuses a matching one. The Goal keeps the loop going, and you pause and resume it the way you normally would in Codex.

Each experiment goes like this:

1. Codex looks at the measurements and earlier experiments and picks an idea to try.
2. Codex makes one coherent change inside the scope.
3. The control script commits it.
4. It runs verify, and the guard if the metric improved.
5. It keeps the commit or adds a revert commit.
6. It records the result, and the loop continues.

The Goal is marked complete only when the kept result reaches the target.

## Background

Background starts a separate controller and gives the TUI back to you. The controller runs one fresh `codex exec` worker per experiment, checks what it recorded, and starts the next one if the run is still active.

The chain looks like this:

```text
your Codex task -> controller -> one worker at a time
```

Background defaults to Full Access so workers can commit and revert. You can choose `workspace-write` instead, but if the sandbox blocks writes to `.git`, the run stops; it won't quietly switch permissions.

Workers use your Codex configuration; `--model` overrides the model for the run.

Leave the run's checkout alone until it stops. Anything you edit inside the scope gets committed with the current experiment, so if you want to keep working, use a separate `git worktree`.

Control the run through the skill:

```text
$codex-autoresearch show the background status
$codex-autoresearch stop the background run
$codex-autoresearch resume the background run
$codex-autoresearch resume with this direction: focus on parser allocation
```

Resume picks up the same experiment. Add a direction if you want to steer it. Your own Codex task doesn't need to keep watching the controller.

## Run States

| Status | Meaning |
|---|---|
| `not_initialized` | No run yet |
| `initialization_failed` | Setup failed; read the diagnostics and archive before retrying |
| `active` | More experiments can run |
| `complete` | The kept result reached the target |
| `stopped` | You stopped it, or it hit the iteration limit |
| `blocked` | It needs something from outside, such as credentials or data |
| `error` | A command, Git, the run record, or a worker went wrong |

An idea that doesn't improve the metric is a `discard`. A failed measurement is an `error`. Neither makes the run `blocked`.

In the background, `orphaned` means the record says the run is active but its controller is gone. Check the worker PID and runtime log that status reports. If no worker is still alive, `stop` closes the run. If one is, let it finish or kill it before you stop, resume, or archive.

## Artifacts

Everything lives under `autoresearch-results/`:

```text
autoresearch-results/
├── run.json
├── events.jsonl
├── logs/
├── runtime.json       # background only
├── runtime.log        # background only
└── report.html        # generated on request
```

`run.json` holds the settings you confirmed and never changes. `events.jsonl` records everything that happened and is only ever appended to. The logs keep the full output of every command and worker.

Please don't edit these files. If one is damaged or doesn't add up, the run stops instead of trying to rebuild it. To start a different goal, ask the skill to archive the current run first; old runs stay under `autoresearch-results/archive/`.

If the current run is still active, stop it first (background) or clear its Goal with `/goal clear` (foreground). Then ask the skill to archive it and start the new goal.

## History And Reports

These work for any run, active or finished:

```text
$codex-autoresearch show experiment history
$codex-autoresearch export experiment history as TSV
$codex-autoresearch generate an HTML report
```

History prints a table straight from the event log. Ask for TSV when you want the data in a spreadsheet or script. The HTML report is one self-contained file, `autoresearch-results/report.html`, with the metric over time, the keep/discard timeline, commits, and links to the logs.

None of these change `events.jsonl`, so you can delete or regenerate the report any time. It's a snapshot, though: run the command again to include newer experiments.

## Git History

A kept experiment:

```text
autoresearch: remove parser allocation
```

A discarded one:

```text
Revert "autoresearch: cache parser nodes"
autoresearch: cache parser nodes
```

The extra revert commit is the price of rolling back without rewriting history: you can always see what was tried. Autoresearch never stages its results folder, and it stops if someone switches branches, moves HEAD, or edits files outside the scope during a run.

## Errors And Recovery

Errors tell you exactly which rule was broken and, for commands, where the full log is. `status` also shows the expected and actual Git state and any changed files. Fix the cause, then resume.

- Bad metric output: make the last line a number, or name one JSON key.
- Verify exits nonzero: inspect the command log and fix the cause. Exit 0 only when measurement succeeds, even if the result is poor.
- Baseline guard fails: fix the code first, or choose a different guard.
- Dirty or out-of-scope files: put them back; don't widen the scope just to make the error go away.
- Command creates files: change it so measuring leaves the repository untouched.
- Worker records nothing: read its worker log. The controller stops instead of blindly starting another worker.
- Controller disappears: check in `status` whether the controller and worker are still alive before you recover.
- Rollback fails: fix Git by hand and archive the run. An experiment that was never verified can't become the starting point of a resumed run.

## Choosing A Task

Good tasks have a measurement you can repeat and a target that means something: zero failing cases, at least 90% coverage, p95 at most 200 ms, no critical findings from a deterministic scanner, or a project-specific score at or above a threshold.

For design taste, one-off migrations, releases, or deployments, use Codex normally. If the goal is still fuzzy, work with Codex to build a stable benchmark first, then start autoresearch.
