# Background Runs

Launch with the configuration approved in [Workflow](workflow.md), using `launch` instead of `init` and adding `--execution-policy <danger-full-access|workspace-write>`.

`danger-full-access` is the default because experiments create Git commits and reverts. Use `workspace-write` when the user chooses it; restricted Git writes cause a visible error.

After launch, return the run id, baseline, results path, and controller status. Wait or monitor when the user requests it.

## Controller And Workers

```text
Codex task -> detached controller -> worker 1 -> worker 2 -> ... -> terminal state
```

The controller starts one `codex exec` worker at a time with the confirmed goal, metric, stopping conditions, scopes, and control-script path. Each worker uses the supplied contract to complete one experiment through `finish`, or record an actionable external blocker through `block`, then exits. Launch approval already covers these experiments.

Workers do not create Goals, start controllers, ask launch questions, manually commit or revert, or edit run artifacts. The controller validates the resulting events and starts another worker only if the preceding worker succeeded and the run remains active.

## Controls

- `status --repo <repo>`: validated experiment status and controller/worker PIDs.
- `stop --repo <repo>`: request a stop; the controller terminates the worker process tree before checking the repository boundary.
- `resume --repo <repo> [--note <direction>]`: continue the confirmed experiment, optionally with new guidance.

A simple request to continue does not require a new strategy. For an error or blocker, resolve its cause before resuming.

If the controller is gone but its worker is alive, report the worker PID and log path. Do not resume or archive until that worker exits or is explicitly terminated. Once no worker remains, `stop` can close an orphaned active run before resume.

Missing worker events, unexpected exits, invalid state, or controller failures stop continuation with diagnostics. Full worker output is in `autoresearch-results/logs/`; controller events are in `runtime.log`. Use these to explain failures rather than inferring success from process exit alone.
