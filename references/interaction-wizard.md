# Interaction Wizard Contract

This file defines how Codex should collect missing information for `codex-autoresearch`.

## Goal

The user says one sentence. Codex figures out the rest through guided conversation. The user should never need to know field names, write key-value pairs, or understand the internal configuration format.

When this file mentions `<skill-root>`, it means the directory containing the loaded `SKILL.md`.

**Clarify First.** For new interactive launches, scan the repo and ask at least one repo-grounded confirmation round before starting the loop. This confirmation round is mandatory. The user should stay in control without learning the internal config shape.

## Global Rules

1. Accept natural language input. The user's first message may be as short as "improve my test coverage" or "make training faster".
2. Scan the repo before asking anything -- read directory structure, key config files, scripts, and code relevant to the user's goal.
3. Ask at least one round of clarifying questions before launch. Show what you found and what you plan to do, then let the user confirm or correct it.
4. Guide the user through conversation. Ask one question at a time (or batch tightly related ones). Each question must be specific and grounded in what you found in the repo.
5. Propose concrete defaults with every question. Let the user confirm or correct.
6. Aim to finish clarification in 1 to 3 rounds. Ask more only when a real blocker remains; avoid turning setup into a questionnaire.
7. Present a structured confirmation summary before launching (see Confirmation Format below).
8. Do not collapse confirmation into a bare "foreground/background + go" prompt. Even when run mode is the only remaining choice, first show a short repo-grounded summary of the goal, metric, verify path, and next step.
9. The user should never see raw field names (Goal, Scope, Metric, Direction, Verify, Guard). Translate everything into natural conversation.
10. After the user approves the summary, follow the chosen run mode directly from the same skill entrypoint. Foreground stays in the current session; background persists the confirmed launch manifest and starts the runtime controller. Do not tell the user to switch to a different wrapper command.
11. End the confirmation summary with a short runtime checklist that reinforces execution order: baseline first, then initialize artifacts, and always log a completed experiment before starting the next one.
12. After the launch gate allows a fresh or confirmed interactive launch, check `python3 <skill-root>/scripts/autoresearch_hooks_ctl.py status`. If setup is missing, stale, disabled, or untrusted, run `python3 <skill-root>/scripts/autoresearch_hooks_ctl.py install` before clarification continues. Treat this as internal preparation; keep setup details out of the user-facing summary unless a setup failure blocks launch. Use model-visible goal tools when they are actually available.
13. Capture the first status response's `startup_tip_needed` value before any install/update. If true, show one product-facing startup tip in the confirmation summary: "For the smoothest long-running runs, start Codex with `codex --enable goals --enable hooks --dangerously-bypass-approvals-and-sandbox`." Do not expose status field names or claim to have detected the exact shell command.

## Clarification Protocol

### Step 1: Scan

Read the repo to understand what exists -- source files, training scripts, config files, test suites, build systems, CI configs, etc. Check manifest files (`package.json`, `requirements.txt`, `pyproject.toml`, `go.mod`, etc.) to understand the stack before asking about it.

After the primary repo is known, run `python3 <skill-root>/scripts/autoresearch_launch_gate.py --repo <primary_repo>` and follow `session-resume-protocol.md`: resume when it is safe, use the mini-wizard when confirmation is needed, or continue the normal wizard only for a fresh launch.

When the flow continues into a fresh or confirmed interactive launch, run the setup check from the global rules. If setup work is needed, do it silently before asking the next clarification question. Do not infer current-session goal-tool availability from saved setup state; use model-visible goal tools when they are actually available. Keep the first startup-tip decision from the initial status check, mention the tip once in the confirmation summary when needed, then continue the normal wizard.

When model-visible goal tools are available, call `get_goal` before the confirmation summary. If an existing official goal cannot be reused for the proposed autoresearch objective, include that conflict in the summary before the user chooses foreground.

### Step 2: Guided Questions (required)

Ask at least one round of questions, even when the goal seems obvious. Use the optional question appendix below only when you need help choosing the shortest useful question set for the situation.

| What you need | Bad (skipping) | Good (confirming) |
|---------------|----------------|-------------------|
| Scope | Silently pick src/ | "I see `src/models/` and `src/api/` -- should I touch the model layer only, or the whole src?" |
| Metric | Silently pick line coverage | "Your test suite reports line coverage (currently 58%). Should I track that, or do you care more about branch coverage?" |
| Target | Assume "as high as possible" | "Coverage is at 58% now. What's your target -- 80%? 90%? Or just push as high as I can?" |
| Verify command | Silently pick pytest | "I can run `pytest --cov=src` to measure coverage. Does that work, or do you use a different runner?" |
| Guard | Skip it | "Should I make sure `tsc --noEmit` still passes after each change?" |
| Duration | Assume unlimited | "Want me to run 10 iterations as a test, or keep iterating until you interrupt me?" |

Rules:
- Each round must add new information. Never ask the same question twice.
- Prefer multiple-choice questions over open-ended ones to reduce user effort.
- If the user's answer introduces new ambiguity, ask about that specifically.
- If the goal is still unclear after 3 rounds, propose the most reasonable interpretation and let the user approve or edit.
- If the user says the experiment spans multiple repos, identify one **primary repo** for run-control artifacts and list any additional **companion repos** separately, each with its own scope.
- Default the `workspace_root` candidate from the launch context. If Codex was started inside a git repo, use that repo root as the default candidate. If Codex was started outside a git repo, use the current launch directory as the default candidate.
- Do not silently widen `workspace_root` to a parent directory just because nearby sibling repos, old `autoresearch-results/`, or a broader filesystem layout exist. Only widen to a broader shared workspace when the user explicitly confirms that intent.
- Do not replace the structured summary with a single-line "foreground or background?" prompt. The user should see what you inferred from the repo before they are asked to approve launch.
- If the chosen `workspace_root` is outside the launch context or outside the primary repo, call that out explicitly in the confirmation summary and show the resulting `Results directory`.
- If clarification changes the `workspace_root`, rerun the launch gate with the confirmed workspace root before the final summary.
- When the user explicitly describes multiple goals or says they cannot prioritize into a single metric, suggest `verify_format=metrics_json` with a primary metric for the TSV plus acceptance criteria on the others. If the repo scan reveals a verify script that outputs structured multi-metric data, mention it as an option but let the user decide whether they want multi-metric tracking or just a single primary metric. Do not proactively suggest multi-metric when the user's goal is clearly single-metric.

### Step 3: Confirm (Structured Format)

Before launching, present a structured confirmation summary. The user should be able to scan it in seconds and reply with one word.

#### English Format

```
**Confirmed**
- Target: eliminate `any` types in src/**/*.ts
- Results directory: `./autoresearch-results/`
- Metric: `any` occurrence count (current: 47), direction: lower
- Verify: `grep -r ":\s*any" src/ --include="*.ts" | wc -l`
- Guard: `tsc --noEmit` must still pass
- Also keeping: hard_conflicts == 0, oversized_rooms <= 100 *(only when multi-metric)*

**Need to confirm**
- Run until all gone, or cap at N iterations?
- Any other safety checks beyond tsc?

**Runtime checklist**
- Baseline first, then initialize results/state.
- Log every completed experiment before the next one starts.
- Use helper scripts for authoritative row/state updates.

**Next step**
- Choose foreground or background, then reply "go" to start, or tell me what to change.
```

#### Format Rules

1. Always use the user's language -- Chinese prompt gets Chinese headings, English gets English.
2. Keep the confirmation scannable -- aim for under 15 lines.
3. Show concrete numbers (current metric value, file count, etc.) so the user can sanity-check.
4. The "Need to confirm" section should only contain genuine blockers, not padding.
5. End with a clear call to action.
6. If run mode is still undecided, list it under "Need to confirm" and then ask the user to choose foreground or background. Do not omit the summary just because run mode is the only remaining blocker.
7. Keep the base template minimal. Add optional blocks only when they are genuinely needed.
8. Only show "Required keep labels" and/or "Required stop labels" when the goal truly has structural success requirements beyond the numeric target.
9. Keep the runtime checklist short. It exists to reinforce execution order, not to restate the whole protocol.
10. Do not include setup details in the normal confirmation summary. Mention them only when a setup failure blocks the selected run mode.
11. When the run tracks multiple metrics, show the additional thresholds in plain language (e.g., "Also keeping: hard_conflicts == 0") rather than exposing internal field names. Omit this line entirely for single-metric runs.
12. Always show the `Results directory`. If it is the default `./autoresearch-results/` under the launch context, the relative form is fine. If it lives outside the launch context or outside the primary repo, show the absolute path and make that widening explicit before launch.
13. If the startup tip is shown, keep it outside the confirmed run config so users do not confuse it with an internal requirement for this specific run.

The user replies "go", "start", "launch", or corrects something. No field names, no YAML, no structured input required.

## Launch Handoff

When the user replies with launch approval (`go`, `start`, `launch`, or an equivalent clear confirmation):

1. Require an explicit run-mode choice: **foreground** or **background**.
2. By handoff time, the setup check should already be complete. Keep setup details out of the user-facing handoff unless a setup failure blocks the selected run mode.
3. If the user chose **foreground**, keep the loop in the current Codex session:
   - when model-visible goal tools are available, align the official Codex goal before initialization: call `get_goal`, reuse a matching non-complete current goal, or call `create_goal` with the confirmed objective when no goal exists
   - if an existing official goal cannot be reused, do not create another goal; surface that conflict in the confirmation summary before launch and let the user resolve it there
   - initialize `autoresearch-results/results.tsv`, `autoresearch-results/state.json`, and `autoresearch-results/context.json`
   - do not create `autoresearch-results/launch.json`, `autoresearch-results/runtime.json`, or `autoresearch-results/runtime.log`
   - keep the runtime checklist active: baseline first, then log every completed experiment before the next one starts
   - mark the official Codex goal complete only when the configured autoresearch success condition is actually met; hard blockers and user interruptions are not complete goals
   - report that the foreground run has started in the current session
4. If the user chose **background**, persist the confirmed config to `autoresearch-results/launch.json`, start the detached runtime controller, and report the Results directory. The wizard supplies the confirmed `--workspace-root <workspace_root>` internally; users should not have to type it.
   - the nested background session must receive the same runtime checklist, especially the "log before the next experiment" rule
   - do not create or update official Codex goals for background runs
5. Do not ask the user to rerun a shell wrapper command just to continue overnight.

If the chosen path is **Fresh start** after recovery analysis, the handoff should be:

```bash
python3 <skill-root>/scripts/autoresearch_runtime_ctl.py launch --repo <primary_repo> --workspace-root <workspace_root> --fresh-start ...
```

This archives prior persistent run-control artifacts inside `autoresearch-results/` to `.prev` before the new background run begins. Legacy repo-root artifacts are not recovered into the new schema; the user must choose fresh start or move/archive them.

## Optional Question Appendix

Use this appendix only when you need help choosing the shortest useful question set. Pick 1-3 questions that are actually blocking. Prefer multiple-choice to reduce user effort.

### Scope & Boundaries

- "I see both `src/models/` and `src/api/` -- should I optimize the model layer only, or the full src?"
- "There are 3 training scripts here (`train_gpt2.py`, `train_llama.py`, `train_vit.py`) -- which one?"
- "Should I only modify test files, or can I also refactor the source code to make it more testable?"
- "I can keep the Results directory in `./autoresearch-results/` for this current launch context, or widen to a shared parent workspace if this run truly spans multiple repos. Which do you want?"

### Metric & Target

- "Your test suite reports line coverage (currently 58%). Should I track that, or branch coverage?"
- "What's your target -- 80%? 90%? Or just push as high as I can?"
- "I see MFU is logged in the training output. Are we targeting a specific number, or just higher-is-better?"
- "The verify command currently measures response time. Should I track p50, p95, or p99?"
- "If I hit the target with the wrong mechanism or path, should I keep going? I can require structured keep labels so only the right mechanism can enter retained state, and structured stop labels so the run only stops when the retained keep matches the mechanism you care about."
- "You mentioned several goals. Should I pick one as the primary metric and set hard thresholds on the others, or would you prefer a single combined score?"

### Verification & Guard

- "I can run `pytest --cov=src` to measure coverage. Does that work, or do you use a different runner?"
- "Should I make sure `tsc --noEmit` still passes after each change, so we don't introduce type errors?"
- "The build takes 3 minutes. Should I use it as the guard, or is there a faster smoke test?"
- "I found `npm test` and `npm run lint` -- should I guard with both, or just tests?"
- If a command fails at baseline and is part of the user's repair target, present it as the verify/final acceptance check, not as guard. Guard is only for baseline-passing regression checks.

### Duration & Strategy

- "Should this run stay in the current foreground session, or hand off to the background runtime after `go`?"
- "Want me to run 10 iterations as a test, or let it go overnight?"
- "Should this be an unattended run that keeps going until you interrupt it, or a bounded trial run?"
- "Should I focus on quick wins first, or go straight for the biggest impact?"
- "If I get stuck after several attempts, should I try bolder architectural changes, or stop and report?"
- "If failed iterations need rollback, may I use destructive rollback inside a dedicated experiment branch/worktree so I do not have to stop and ask mid-run?"

### Parallel & Search

- "I can test multiple ideas at the same time using parallel experiments. Want me to try up to 3 hypotheses per round? (I detected {N} GPUs/NPUs -- each experiment would need how many?)"
- "If I get stuck, can I search the web for solutions? (results are always verified mechanically before applying)"

### Debug-Specific

- "Can you describe what happens? (A: error message, B: wrong output, C: intermittent failure, D: performance degradation)"
- "When did this start? (A: after a specific change, B: always been there, C: not sure)"
- "If I find the cause, should I also try to fix it, or just report?"
- "Do you have a screenshot, flame graph, or error image I can look at? (paste or drag an image if so)"

### Fix-Specific

- "I see 12 failing tests. Should I fix all of them, or focus on a specific module first?"
- "Some failures look related. Should I fix the root cause first, even if it's harder?"
- "Should I preserve backward compatibility, or is breaking the old API acceptable?"

### Security-Specific

- "Should I audit the whole codebase, or just the API layer?"
- "Focus on which threats? (A: injection/XSS, B: auth/access control, C: data exposure, D: all)"
- "Report only, or should I also fix critical findings?"
- "Do you have an architecture diagram or network topology image I can reference? (paste or drag an image if so)"

### Ship-Specific

- "Dry run first, or go live directly?"
- "Is this a PR, a deployment, or a release?"
- "How long should I monitor after shipping? (A: 5 min, B: 15 min, C: skip)"

## Internal Field Mapping

The wizard internally maps the conversation to these fields (the user never sees them):

### loop

- Goal -- extracted from user's description
- Scope -- inferred from repo + user's answers
- Metric -- proposed by Codex, confirmed by user
- Direction -- inferred from goal ("improve" = higher, "reduce/eliminate" = lower)
- Verify -- Codex proposes a command based on repo tooling
- Guard (optional) -- Codex suggests if there's a regression risk and the command already passes at baseline
- Iterations (optional) -- asked only if user wants bounded run
- Required keep labels (optional) -- ask only when only a specific mechanism, path, backend, or root-cause signal should be allowed into retained state
- Required stop labels (optional) -- ask only when the run should stop on a specific mechanism, path, backend, or root-cause signal in addition to the metric target
- Verify format (optional) -- default `scalar`; use `metrics_json` when the goal involves multiple metrics and the verify command outputs a JSON object as its final line
- Primary metric key (optional) -- which key in the metrics JSON to track in the TSV; defaults to the metric name
- Acceptance criteria (optional) -- list of `{metric_key, operator, target}` thresholds that the retained result must satisfy before the run can stop; only configure when the goal has multi-metric success requirements
- Required keep criteria (optional) -- list of `{metric_key, operator, target}` hard gates that every retained result must satisfy to enter `keep` state (e.g., `hard_conflicts == 0`); use when some metrics must never regress regardless of primary metric improvement
- Rollback (optional) -- ask only if destructive rollback may be needed for unattended execution; otherwise default to non-destructive revert
- Parallel (optional) -- ask if environment supports it (CPU >= 4, RAM >= 8GB)
- Web search (optional) -- ask if user wants web search when stuck

### plan

- Goal -- user's description
- Everything else is generated by plan mode

### debug

- Symptom -- user's description of the problem
- Scope -- inferred from symptom + repo structure
- After-action -- ask: "If I find the cause, should I also try to fix it?"

### fix

- Target -- inferred from user's description ("tests are failing" -> test runner)
- Scope -- inferred from repo structure
- Guard (optional) -- suggested only for baseline-passing regression checks; failing target commands are verify/final acceptance

### security

- Scope -- inferred or asked ("the whole API layer, or just authentication?")
- Focus -- extracted from user's concern or asked
- Action -- ask: "Report only, or should I also fix critical issues?"

### ship

- Shipment type -- auto-detected or asked
- Target -- inferred or asked
- Scope -- inferred from the target artifact, release files, deployment config, and any checklist-related files that may need edits
- Metric -- checklist readiness score (or another mechanical pass-count score)
- Direction -- `higher`
- Verify -- Codex proposes a command or script that evaluates the checklist and emits the readiness score
- Run mode -- foreground or background
- Ship action -- ask "Dry run first, or ship directly?" only when an external ship action is in scope
- Monitor -- ask how long to monitor after ship when relevant

### exec

Exec mode does NOT use the wizard. All fields must be provided at invocation time in the `codex exec` prompt or via environment variables. If any required field is missing, exec mode fails immediately with exit code 2. See `references/exec-workflow.md`.

### Execution Policy

- Background launch manifests record an `execution_policy`.
- This skill defaults that policy to `danger_full_access` so detached runtime sessions and controlled automation runs inherit full access by default.
- Only switch to `workspace_write` when the user explicitly asks for a sandboxed run or when you intentionally want to reproduce sandbox-related blockers.

## Validation Rules

Before launching, silently validate:

- scope resolves to real files,
- metric is mechanical (a command can produce a number),
- verify command is runnable,
- guard command is pass/fail only and already passes at baseline,
- iterations is a positive integer when provided.

If validation fails, tell the user in plain language what went wrong and suggest a fix. Do not show raw error formats.

## Launch Rules

- `plan` mode does not edit code unless the user explicitly says to launch.
- `ship` mode never performs side effects without explicit confirmation.
- After the user says "go" / "start" / "launch", begin immediately. Do not ask again.
- **Two-phase boundary:** all questions happen before launch. Once the loop starts, keep running without more user questions; if ambiguity appears mid-loop, apply best practices, log the reasoning, and continue until a stop condition or true blocker appears.

## Mini-Wizard (Session Resume)

When `session-resume-protocol.md` detects a prior run with a valid `autoresearch-results/state.json` but inconsistent TSV (Recovery Priority 2), the full wizard is replaced by a single-round mini-wizard:

1. Show what was detected:
   - Prior run tag, iteration count, best metric, and last status from the JSON state.
   - The specific inconsistency reported by `<skill-root>/scripts/autoresearch_resume_check.py` (for example retained-metric mismatch, missing main row, or stale counters).
2. Ask exactly one question with two choices:
   - **Resume:** use the JSON `config` as the authoritative source. Briefly confirm scope, metric, and verify command in a single confirmation block.
   - **Fresh start:** archive old artifacts with `.prev` suffixes and proceed with the full wizard.
3. If the user chooses to resume, present a condensed confirmation summary (same format as Step 3 above but sourced from JSON `config` instead of repo scanning).
4. The user replies "go" and the loop starts immediately in the chosen run mode:
   - foreground resume continues directly from `autoresearch-results/results.tsv` + `autoresearch-results/state.json`
   - background resume launches through `autoresearch_runtime_ctl.py launch --repo <primary_repo> --workspace-root <workspace_root> ...`
   - fresh-start background handoff uses `autoresearch_runtime_ctl.py launch --repo <primary_repo> --workspace-root <workspace_root> --fresh-start ...`
   No further rounds.

The mini-wizard respects the same two-phase boundary: all questions happen before launch.
