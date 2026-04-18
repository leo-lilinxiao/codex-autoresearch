---
name: codex-autoresearch
description: "Autonomous long-running iteration for Codex CLI. Use when the user wants Codex to plan or run an unattended improve-verify loop toward a measurable or verifiable outcome, especially for overnight runs; it also covers repeated debugging, fixing, security auditing, and ship-readiness workflows. Do not use for ordinary one-shot coding help or casual Q&A."
metadata:
  short-description: "Run an unattended improve-verify loop"
---

# codex-autoresearch

Autonomous goal-directed iteration. Modify -> Verify -> Keep/Discard -> Repeat.

## When Activated

1. Classify the request as `loop`, `plan`, `debug`, `fix`, `security`, `ship`, or `exec`, and parse any inline config from the prompt.
2. Load `references/core-principles.md` and `references/structured-output-spec.md`. For active execution modes (`loop`, `debug`, `fix`, `security`, `ship`, `exec`), also load `references/runtime-hard-invariants.md`.
3. Load only the additional references the current situation needs:
   - `references/session-resume-protocol.md` when resuming or controlling an existing run
   - `references/environment-awareness.md` before choosing hardware-sensitive work
   - `references/interaction-wizard.md` for every new interactive launch (`loop`, `debug`, `fix`, `security`, `ship`) before execution begins
   - `references/results-logging.md` only when debugging TSV/state semantics or helper behavior directly
4. Load the selected mode workflow reference plus only the detailed cross-cutting protocols that actually apply (`lessons`, `pivot`, `health-check`, `parallel`, `web-search`, `hypothesis-perspectives`).
5. Use the bundled helper scripts when stateful artifacts or runtime control are involved. Resolve them relative to the loaded skill bundle root (`<skill-root>/scripts/...`), not the target repo root. In the common repo-local install this means commands such as `python3 .agents/skills/codex-autoresearch/scripts/autoresearch_init_run.py --repo <primary_repo> --workspace-root <workspace_root> ...`. New-run helpers (`autoresearch_init_run.py` and `autoresearch_runtime_ctl.py launch/create-launch`) require both `--repo <primary_repo>` and `--workspace-root <workspace_root>`. Existing-run control-plane helpers (`autoresearch_resume_check.py`, `autoresearch_launch_gate.py`, `autoresearch_resume_prompt.py`, `autoresearch_supervisor_status.py`, `autoresearch_health_check.py`, `autoresearch_runtime_ctl.py status/stop/start`) require `--repo <primary_repo>` and resolve the workspace-owned Results directory from the repo's git-local pointer plus canonical context.
6. Execute the selected workflow exactly as written and produce the required structured output and artifacts.

## Core Loop

1. Read the relevant context.
2. Define a mechanical success metric.
3. Establish a baseline.
4. Make one focused change.
5. Verify with a command.
6. Keep or discard the change.
7. Log the result.
8. Repeat.

## Modes

| Mode | Purpose | Primary Reference |
|------|---------|-------------------|
| `loop` | Run the autonomous improvement loop | `references/loop-workflow.md` |
| `plan` | Convert a vague goal into a launch-ready config | `references/plan-workflow.md` |
| `debug` | Hunt bugs with evidence and hypotheses | `references/debug-workflow.md` |
| `fix` | Iteratively reduce errors to zero | `references/fix-workflow.md` |
| `security` | Run a structured security audit | `references/security-workflow.md` |
| `ship` | Gate and execute a ship workflow | `references/ship-workflow.md` |
| `exec` | Non-interactive CI/CD mode with JSON output | `references/exec-workflow.md` |

Use `Mode: <name>` in the prompt to force a specific subworkflow.

## Required Config

For the generic loop, the following fields are needed internally. Codex infers them from the user's natural language input and repo context, then fills gaps through guided conversation:

- `Goal`
- `Scope`
- `Metric`
- `Direction`
- `Verify`

Optional but recommended:

- `Guard`
- `Iterations`
- `Run tag`
- `Stop condition`

For every new interactive run, use the wizard contract in `references/interaction-wizard.md`.

## Explicit Run Modes

- `$codex-autoresearch` is the only primary human-facing entrypoint.
- For a new interactive run, scan the repo, ask the confirmation questions, and require an explicit run-mode choice: **foreground** or **background**.
- If the user chooses **foreground**, keep the loop in the current Codex session. Use the shared helper scripts (`autoresearch_init_run.py --repo <primary_repo> --workspace-root <workspace_root>`, `autoresearch_record_iteration.py`, `autoresearch_select_parallel_batch.py`, `autoresearch_supervisor_status.py --repo <primary_repo>`) and do not create launch/runtime control artifacts.
- If the user chooses **background**, call `autoresearch_runtime_ctl.py launch --repo <primary_repo> --workspace-root <workspace_root>` to persist the confirmed launch manifest and start the detached runtime controller in one step. The runtime itself should execute non-interactive `codex exec` sessions with the generated runtime prompt supplied on stdin. This skill now defaults those detached sessions to `danger_full_access` (`--dangerously-bypass-approvals-and-sandbox`) unless the user explicitly asks for the sandboxed `workspace_write` path. If the mini-wizard outcome is "fresh start", call `autoresearch_runtime_ctl.py launch --repo <primary_repo> --workspace-root <workspace_root> --fresh-start` so prior persistent run-control artifacts are archived as part of the same handoff.
- If the user resumes an existing interactive run in the other mode, synchronize `autoresearch-results/state.json` internally before continuing. Background `start` already performs that sync automatically before it relaunches nested Codex sessions; `autoresearch_set_session_mode.py` remains an internal/scripted recovery helper, not a normal user-facing step.
- Treat the repo where the run starts as the **primary repo**. Single-repo runs are the default. If the task truly spans multiple codebases, declare **companion repos** explicitly and give each repo its own scope instead of stuffing absolute paths into one mixed scope string.
- For a new interactive run, default the `workspace_root` from the launch context: if Codex started inside a git repo, use that repo root; otherwise use the current launch directory. Do not silently widen to a parent workspace just because sibling repos or old artifacts exist. Only widen when the user explicitly confirms a broader multi-repo workspace, and show the resulting `Results directory` in the confirmation summary.
- Foreground and background share the same experiment protocol, but they are mutually exclusive for a given workspace/run. Never try to keep both modes active against the same `autoresearch-results/` artifacts at the same time.
- For every new interactive foreground/background run, immediately after the initial repo scan check `python3 <skill-root>/scripts/autoresearch_hooks_ctl.py status` and then follow the hooks decision flow in `references/interaction-wizard.md`. If the status is not ready for future sessions, automatically install or repair the managed hooks before clarification continues. Keep the user-facing note short: `background` can use freshly installed hooks immediately, while the current `foreground` session would need a new Codex session / reopened thread to pick them up.
- For `status`, `stop`, or `resume` requests, stay on the same skill entry. `status` and `stop` apply to background runs only; foreground runs stay in the current session.
- `exec` remains the advanced / CI path. It is fully specified upfront and does not use the interactive handoff.

## Hard Rules

1. **Ask before act for new interactive launches.** For `loop`, `debug`, `fix`, `security`, and `ship`, ALWAYS scan the repo and ask at least one round of clarifying questions before the run starts. Load and follow `references/interaction-wizard.md` for every new interactive launch. The launch wizard must include an explicit run-mode choice: foreground or background. `exec` mode is the exception: it is fully configured upfront and must not stop for a launch question.
2. **Respect the chosen run mode after launch approval.** In interactive modes, once the user says "go" (or equivalent: "start", "launch", or any clear approval), follow the selected run mode exactly. Foreground stays in the current session and must not call `autoresearch_runtime_ctl.py launch`. Background calls `autoresearch_runtime_ctl.py launch --repo <primary_repo> --workspace-root <workspace_root>`, creating the confirmed launch manifest and detached runtime as a single script-level action. Detached sessions use the confirmed launch manifest's `execution_policy`; this skill defaults to `danger_full_access` unless the user explicitly asks for sandboxed `workspace_write`. If the chosen background path is a fresh start after recovery analysis, use `autoresearch_runtime_ctl.py launch --repo <primary_repo> --workspace-root <workspace_root> --fresh-start` so stale persistent run-control artifacts are archived automatically. `exec` mode has no launch question; once safety checks pass, it begins immediately.
3. **Never ask after the user approves the run.** Once the user has approved `go` in either foreground or background mode, do not pause mid-run to ask anything -- not for clarification, not for confirmation, not for permission. If you encounter ambiguity during the loop, apply best practices and keep going. The user may be asleep.
4. Read all in-scope files before the first write.
5. One focused change per iteration.
6. Mechanical verification only.
7. Commit before verification only when every managed repo's worktree stays within that repo's declared scope or autoresearch-owned artifacts. The background runtime enforces the same scope-aware gate before each relaunch boundary, but foreground runs must still honor it before creating a trial commit.
8. Never stage or revert unrelated user changes.
9. Keep run artifacts uncommitted and never stage them.
10. Use the rollback strategy approved during setup. In a dedicated experiment branch/worktree with pre-launch approval, `git reset --hard HEAD~1` is allowed; otherwise use `git revert --no-edit HEAD`.
11. Discard gains under 1% that add disproportionate complexity.
12. Unlimited runs by default unless the user explicitly asks for `Iterations: N`.
13. External ship actions (deploy, publish, release) must be confirmed during the pre-launch wizard phase. If not confirmed before launch, skip them and log as blocker.
14. Do not ask "should I continue?". Once launched, keep the chosen run mode active until interrupted or a hard blocker / configured terminal condition appears (see `references/autonomous-loop-protocol.md` Stop Conditions for the full definition).
15. During active execution, keep `references/runtime-hard-invariants.md` as the primary runtime checklist. Foreground's core persistent artifacts are `autoresearch-results/results.tsv`, `autoresearch-results/state.json`, `autoresearch-results/context.json`, and `autoresearch-results/lessons.md`; background also uses `autoresearch-results/launch.json`, `autoresearch-results/runtime.json`, and `autoresearch-results/runtime.log`.
16. When stuck (3+ consecutive discards), use the PIVOT/REFINE escalation ladder from `references/pivot-protocol.md` instead of brute-force retrying.
17. Prefer the bundled helper scripts over hand-editing `autoresearch-results/results.tsv`, `autoresearch-results/state.json`, `autoresearch-results/context.json`, or runtime-control files. Always call them via the skill-bundle path (`<skill-root>/scripts/...`); never call bare `scripts/autoresearch_*.py` from the target repo root unless the skill bundle itself is actually installed there.
18. In `exec` mode, never leave repo-root state artifacts behind. If helper scripts need state, use the exec scratch path and explicitly clean it up before exit. New schema artifacts still belong under the workspace-owned `autoresearch-results/` directory; legacy repo-root artifacts trigger the unsupported-layout error unless the user explicitly chooses a fresh start.
19. After any context compaction event (the CLI warns about thread length and compaction), re-read `references/runtime-hard-invariants.md`, `references/core-principles.md`, and the selected mode workflow from disk before the next iteration. Do not rely on memory of those documents after compaction.
20. Every 10 iterations, perform the Protocol Fingerprint Check defined in `references/runtime-hard-invariants.md`. Use Phase 8.7 of `references/autonomous-loop-protocol.md` only for the detailed re-anchoring procedure. If any item fails, re-read all loaded runtime docs from disk before continuing.

## Structured Output

Every mode should follow `references/structured-output-spec.md`.

Minimum requirement:

- for interactive and user-facing modes, print a setup summary before the loop starts,
- for interactive and user-facing modes, print progress updates during the loop,
- for interactive and user-facing modes, print a completion summary at the end,
- for `exec`, emit only the machine-readable JSON payloads defined in `references/exec-workflow.md`,
- write the mode-specific output files when the workflow defines an output directory.

## Quick Start

```text
$codex-autoresearch
I want to get rid of all the `any` types in my TypeScript code
```

```text
$codex-autoresearch
I want to make our API faster but I don't know where to start
```

```text
$codex-autoresearch
pytest is failing, 12 tests broken after the refactor
```

Codex scans the repo, asks targeted questions to clarify your intent, asks you to choose foreground or background for interactive runs, then starts the loop. You never need to write key-value config.

## References

- `references/core-principles.md`
- `references/runtime-hard-invariants.md`
- `references/loop-workflow.md`
- `references/autonomous-loop-protocol.md`
- `references/interaction-wizard.md`
- `references/structured-output-spec.md`
- `references/modes.md`
- `references/plan-workflow.md`
- `references/debug-workflow.md`
- `references/fix-workflow.md`
- `references/security-workflow.md`
- `references/ship-workflow.md`
- `references/exec-workflow.md`
- `references/results-logging.md`
- `references/lessons-protocol.md`
- `references/pivot-protocol.md`
- `references/web-search-protocol.md`
- `references/environment-awareness.md`
- `references/parallel-experiments-protocol.md`
- `references/session-resume-protocol.md`
- `references/health-check-protocol.md`
- `references/hypothesis-perspectives.md`
