# Experiment Workflow

## Start A Run

1. Locate the Git repository and run `status --repo <repo>`. Only `not_initialized` is fresh; handle existing runs below.
2. Inspect the relevant code and commands. Establish a repeatable baseline and choose the configuration below.
3. Show the conditions in one concise confirmation. Reuse choices and authorization already given; ask only for missing launch decisions.
4. If foreground work remains, check that Goal tools are available and that no different unfinished Goal conflicts with this run. Surface a conflict before writing run artifacts.
5. Initialize or launch with the approved values.

Configuration:

- Goal: the user's intended research or engineering outcome.
- Scope: repository-relative file or directory prefixes; no globs. Initialization requires a clean named branch and a working Git identity.
- Verify: a repeatable command whose final non-empty stdout line is a finite number, or a JSON object with one explicit `--metric-key`.
- Direction and target: lower or higher, and the number that means the user's goal is reached.
- Guard: optional pass/fail command protecting behavior outside the metric; it must pass at baseline.
- Mode: foreground with a Codex Goal, or background with a detached controller. Include the Goal and background Full Access policy in the corresponding launch confirmation.
- Iteration limit: only when requested.

The verify command must exit zero when measurement succeeds, even if the result is poor. Verify and guard must emit UTF-8 and leave Git-visible project files unchanged; ignored build output is fine. Stabilize datasets, evaluation, and per-experiment compute budgets so comparisons remain meaningful. Keep measurement and guard behavior fixed during experiments.

A useful confirmation is:

```text
Goal: ...
Scope: ...
Metric: ... (baseline ..., target ..., lower/higher is better)
Verify: ...
Guard: ... / none
Mode: foreground (Codex Goal) / background (Full Access)
Stop: target ..., iteration limit ..., or user stop
Failed trials are committed and reverted.
```

An explicit request to execute a fully specified experiment is approval; no special keyword is required. Obtain any missing launch approval, including the mode, before writing project files, initializing artifacts, or creating a Goal or controller. If measurement needs setup, include that work in the approval.

## Foreground

Initialize once:

```bash
python3 <control> init \
  --repo <repo> --goal <goal> --scope <path> \
  --metric-name <name> --direction <lower|higher> \
  --verify <command> [--metric-key <key>] --target <number> \
  [--guard <command>] [--max-iterations <n>]
```

If initialization returns `complete`, report the measured result without creating a Goal. Otherwise reuse the matching unfinished Goal or call `create_goal`. Its objective identifies codex-autoresearch, the run id, metric, target, and any iteration limit, and requires the experiment workflow while run status is active.

Use Codex's native Goal controls for pause, resume, and clear. Follow the available Goal tool contract; do not create a replacement for a paused or blocked Goal.

## Run Experiments

Launch approval covers subsequent experiments within the agreed scope, evaluation, stopping conditions, and permissions. For an approved foreground run, continue while status is `active`, including after partial improvements or discarded hypotheses. Answer side questions without abandoning the run unless the user pauses it or changes direction. Ask again only when a new decision falls outside the agreement.

Use the validated status at entry or resume. Within an uninterrupted loop, the latest `finish` result supplies the current status and metric; consult earlier events as needed.

1. Choose one coherent hypothesis from code, results, and relevant research. Pursue promising directions, learn from failed attempts, and change approach when the evidence warrants it.
2. Modify only the approved scope. Keep the experiment independently measurable and reversible.
3. Finalize with a description of the hypothesis:

   ```bash
   python3 <control> finish --repo <repo> --description <hypothesis>
   ```

`finish` validates scope and Git provenance, commits the trial, measures it, runs the guard on an improvement, keeps or reverts the trial, and appends the result. Use those measurements for progress and completion; additional checks should answer an unresolved question. Interpret that evidence before choosing the next experiment. Use the returned `status` to decide whether more experiments may run; `outcome` describes only the trial's keep/discard decision.

| Status | Next action |
|---|---|
| `active` | Continue from the retained result with another hypothesis. |
| `complete` | Mark the matching foreground Goal complete and report the result. |
| `stopped` | End experiments and report the stopping reason and best retained result. If the foreground Goal is still active, direct the user to its native pause controls; do not mark it complete or blocked merely because a limit was reached. |
| `blocked` | Report the external dependency and what must change to resume. |
| `error` | Inspect diagnostics and the validated repository state before recovery. |

Normal failed hypotheses and failing guards are discarded. Block only when meaningful progress requires unavailable information, credentials, data, hardware, or another external change. For foreground, satisfy the Goal tool's blocking conditions before calling `block --repo <repo> --reason <reason>` and marking the Goal blocked.

Keep progress updates brief and substantive. When stopping, report baseline, best retained metric, experiment count, and useful findings. The event log contains the detailed history.

## Resume Or Change A Run

Run `status` to validate the saved configuration and history.

- An active foreground run continues with its matching Goal after any native pause is lifted.
- An active background run with a running controller needs no relaunch.
- A user-stopped run can resume with `resume --repo <repo>`. Add `--note <direction>` when the user supplies a new direction.
- For `blocked` or `error`, first resolve the cause. Resume requires consistent Git state and no unreverted trial; record what changed with `--note`.
- A completed run or a run at its iteration limit needs archiving before a new experiment.

For a new goal, stop a live background run first; clear a conflicting foreground Goal through Codex controls. `archive --repo <repo>` preserves prior artifacts. Include archiving in the new-run confirmation, and carry it out without an extra question when already authorized.

## Errors

A failed command is not a completed experiment. Inspect its error, logs, and `status`; correct an invalid invocation when possible within the approved task. Do not continue experiments while status is terminal or Git ownership is uncertain.

`run.json` is immutable configuration and `events.jsonl` is the append-only state history. Unknown schemas, invalid or partial events, malformed metrics, Git drift, and rollback failures must remain visible errors. Never repair these files by guessing from logs or summaries.

A failed initialization can leave `init-error.json` and logs without `run.json`. Inspect the cause and archive that attempt before retrying. If a trial was not reverted, recover Git explicitly and archive it before a new run. Background process recovery is covered in [Background](background.md).
