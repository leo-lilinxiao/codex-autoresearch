---
name: codex-autoresearch
description: "Autonomous goal-directed iteration. Loops autonomously -- modify, verify, keep/discard, repeat -- toward any measurable or verifiable outcome. Use when: (1) iteratively improving code with a measurable target (tests, coverage, bundle size, latency), (2) planning a loop config from a vague goal, (3) hunting bugs with evidence and hypotheses, (4) fixing errors (tests, types, lint, build) to zero, (5) running a structured security audit, or (6) gating and executing a ship workflow. Do not use for one-shot questions, subjective writing, or pure conversation without an actionable goal."
---

# codex-autoresearch

Autonomous goal-directed iteration. Modify -> Verify -> Keep/Discard -> Repeat.

## When Activated

1. Classify the request as `loop`, `plan`, `debug`, `fix`, `security`, or `ship`.
2. Load `references/core-principles.md` and `references/structured-output-spec.md`.
3. Load `references/results-logging.md` when a results log is needed.
4. Load `references/interaction-wizard.md` only if required fields are missing.
5. Load the mode-specific workflow reference.
6. Parse inline config from the user prompt or skill mention.
7. Execute the selected workflow exactly as written.
8. Produce the required structured output and artifacts.

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
| `loop` | Run the autonomous improvement loop | `references/autonomous-loop-protocol.md` |
| `plan` | Convert a vague goal into a launch-ready config | `references/plan-workflow.md` |
| `debug` | Hunt bugs with evidence and hypotheses | `references/debug-workflow.md` |
| `fix` | Iteratively reduce errors to zero | `references/fix-workflow.md` |
| `security` | Run a structured security audit | `references/security-workflow.md` |
| `ship` | Gate and execute a ship workflow | `references/ship-workflow.md` |

Use `Mode: <name>` in the prompt to force a specific subworkflow.

## Load Order

1. `references/core-principles.md`
2. `references/structured-output-spec.md`
3. `references/results-logging.md` when a results log is needed
4. `references/interaction-wizard.md` when required fields are missing
5. `references/autonomous-loop-protocol.md` (always -- shared loop mechanics for all iterating modes)
6. the mode-specific workflow (if different from the loop protocol)

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

If required fields are missing, use the wizard contract in `references/interaction-wizard.md`.

## Hard Rules

1. **Ask before act.** ALWAYS scan the repo and ask at least one round of clarifying questions before starting any loop. Never silently infer all fields and start iterating.
2. **Never ask after launch.** Once the user says "go" (or equivalent: "start", "launch", or any clear approval), the loop is fully autonomous. NEVER pause to ask the user anything -- not for clarification, not for confirmation, not for permission. If you encounter ambiguity during the loop, apply best practices and keep going. The user may be asleep.
3. Read all in-scope files before the first write.
4. One focused change per iteration.
5. Mechanical verification only.
6. Commit before verification only when `git status --porcelain` shows no changes outside the experiment scope.
7. Never stage or revert unrelated user changes.
8. Keep results logs uncommitted.
9. Prefer `git reset --hard HEAD~1` for rollback; fall back to `git revert` only when reset fails.
10. Discard gains under 1% that add disproportionate complexity.
11. Unlimited runs by default unless the user explicitly asks for `Iterations: N`.
12. External ship actions (deploy, publish, release) must be confirmed during the pre-launch wizard phase. If not confirmed before launch, skip them and log as blocker.
13. NEVER STOP. NEVER ASK "should I continue?". Keep iterating until interrupted or a hard blocker appears. A hard blocker is: verify command no longer runnable, scope files deleted externally, git repo corrupted, disk full, or the same crash 5+ times in a row.

## Structured Output

Every mode should follow `references/structured-output-spec.md`.

Minimum requirement:

- print a setup summary before the loop starts,
- print progress updates during the loop,
- print a completion summary at the end,
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

Codex scans the repo, asks targeted questions to clarify your intent, then starts the loop. You never need to write key-value config.

## References

- `references/core-principles.md`
- `references/autonomous-loop-protocol.md`
- `references/interaction-wizard.md`
- `references/structured-output-spec.md`
- `references/modes.md`
- `references/plan-workflow.md`
- `references/debug-workflow.md`
- `references/fix-workflow.md`
- `references/security-workflow.md`
- `references/ship-workflow.md`
- `references/results-logging.md`
