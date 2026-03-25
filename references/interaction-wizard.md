# Interaction Wizard Contract

This file defines how Codex should collect missing information for `codex-autoresearch`.

## Goal

The user says one sentence. Codex figures out the rest through guided conversation. The user should never need to know field names, write key-value pairs, or understand the internal configuration format.

When this file mentions `<skill-root>`, it means the directory containing the loaded `SKILL.md`.

**Clarify First: The Ask-Before-Act Protocol.** Codex ALWAYS scans the repo and asks at least one round of clarifying questions before starting any loop, even if all fields seem inferable. No exceptions. A 30-second confirmation is always cheaper than 50 wasted iterations in the wrong direction.

## Global Rules

1. Accept natural language input. The user's first message may be as short as "improve my test coverage" or "make training faster".
2. Scan the repo before asking anything -- read directory structure, key config files, scripts, and code relevant to the user's goal.
3. ALWAYS ask at least one round of clarifying questions, even when you think you can infer everything. Show the user what you found and what you plan to do. Let them confirm or correct.
4. Guide the user through conversation. Ask one question at a time (or batch tightly related ones). Each question must be specific and grounded in what you found in the repo.
5. Propose concrete defaults with every question. Let the user confirm or correct.
6. Up to 5 clarification rounds are allowed before launching. But never zero rounds.
7. Present a structured confirmation summary before launching (see Confirmation Format below).
8. The mandatory confirmation round must never collapse into a bare "foreground/background + go" prompt. Even if the only unresolved choice is run mode, first show a short repo-grounded summary of the confirmed goal, metric, verify path, and next step.
9. The user should never see raw field names (Goal, Scope, Metric, Direction, Verify, Guard). Translate everything into natural conversation.
10. After the user approves the summary, follow the chosen run mode directly from the same skill entrypoint. Foreground stays in the current session; background persists the confirmed launch manifest and starts the runtime controller. Do not tell the user to switch to a different wrapper command.

## Clarification Protocol

### Step 1: Scan

Read the repo to understand what exists -- source files, training scripts, config files, test suites, build systems, CI configs, etc. Check manifest files (`package.json`, `requirements.txt`, `pyproject.toml`, `go.mod`, etc.) to understand the stack before asking about it.

### Step 2: Guided Questions (MANDATORY -- at least 1 round)

ALWAYS ask at least one round of questions, even when the goal seems obvious. Use the Question Reference below to pick the right questions for the situation.

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
- If after 5 rounds the goal is still unclear, propose the most reasonable interpretation and let the user approve or edit.
- If the user says the experiment spans multiple repos, identify one **primary repo** for run-control artifacts and list any additional **companion repos** separately, each with its own scope.
- Do not replace the structured summary with a single-line "foreground or background?" prompt. The user should see what you inferred from the repo before they are asked to approve launch.

### Step 3: Confirm (Structured Format)

Before launching, present a structured confirmation summary. The user should be able to scan it in seconds and reply with one word.

#### English Format

```
**Confirmed**
- Target: eliminate `any` types in src/**/*.ts
- Metric: `any` occurrence count (current: 47), direction: lower
- Verify: `grep -r ":\s*any" src/ --include="*.ts" | wc -l`
- Guard: `tsc --noEmit` must still pass
- Required stop labels: `production-path`, `real-backend` (when structural success criteria matter)

**Need to confirm**
- Run until all gone, or cap at N iterations?
- Any other safety checks beyond tsc?

**Next step**
- Choose foreground or background, then reply "go" to start, or tell me what to change.
```

#### Chinese Format

```
**已确认**
- 目标：消除 src/**/*.ts 中所有 any 类型
- 指标：any 出现次数（当前 47），方向：降低
- 验证：`grep -r ":\s*any" src/ --include="*.ts" | wc -l`
- 守护：`tsc --noEmit` 必须继续通过
- 必需停止标签：`production-path`、`real-backend`（仅在存在结构性成功条件时展示）

**还需确认**
- 跑到全部消除，还是限制在 N 次迭代？
- 除了 tsc 还有其他安全检查吗？

**下一步**
- 先选择 foreground 或 background，再回复 "go" 启动，或告诉我要改什么。
```

#### Format Rules

1. Always use the user's language -- Chinese prompt gets Chinese headings, English gets English.
2. Keep the confirmation scannable -- aim for under 15 lines.
3. Show concrete numbers (current metric value, file count, etc.) so the user can sanity-check.
4. The "Need to confirm" section should only contain genuine blockers, not padding.
5. End with a clear call to action.
6. If run mode is still undecided, list it under "Need to confirm" and then ask the user to choose foreground or background. Do not omit the summary just because run mode is the only remaining blocker.
7. Only show "Required stop labels" when the goal truly has a structural success requirement in addition to the numeric target.

The user replies "go", "start", "launch", or corrects something. No field names, no YAML, no structured input required.

## Launch Handoff

When the user replies with launch approval (`go`, `start`, `launch`, or an equivalent clear confirmation):

1. Require an explicit run-mode choice: **foreground** or **background**.
2. If the user chose **foreground**, keep the loop in the current Codex session:
   - initialize `research-results.tsv` and `autoresearch-state.json`
   - do not create `autoresearch-launch.json`, `autoresearch-runtime.json`, or `autoresearch-runtime.log`
   - report that the foreground run has started in the current session
3. If the user chose **background**, persist the confirmed config to `autoresearch-launch.json`, start the detached runtime controller, and report where the runtime/log artifacts live.
4. Do not ask the user to rerun a shell wrapper command just to continue overnight.

If the chosen path is **Fresh start** after recovery analysis, the handoff should be:

```bash
python3 <skill-root>/scripts/autoresearch_runtime_ctl.py launch --fresh-start ...
```

This archives prior persistent run-control artifacts to `.prev` before the new background run begins, including `research-results.tsv`, `autoresearch-state.json`, `autoresearch-launch.json`, `autoresearch-runtime.json`, and `autoresearch-runtime.log`.

## Question Reference

Categorized questions for common autoresearch scenarios. Pick 1-3 that are actually blocking. Prefer multiple-choice to reduce user effort.

### Scope & Boundaries

- "I see both `src/models/` and `src/api/` -- should I optimize the model layer only, or the full src?"
- "There are 3 training scripts here (`train_gpt2.py`, `train_llama.py`, `train_vit.py`) -- which one?"
- "Should I only modify test files, or can I also refactor the source code to make it more testable?"

### Metric & Target

- "Your test suite reports line coverage (currently 58%). Should I track that, or branch coverage?"
- "What's your target -- 80%? 90%? Or just push as high as I can?"
- "I see MFU is logged in the training output. Are we targeting a specific number, or just higher-is-better?"
- "The verify command currently measures response time. Should I track p50, p95, or p99?"
- "If I hit the target with the wrong mechanism or path, should I keep going? I can require structured stop labels so the run only stops when the retained keep matches the mechanism you care about, for example `production-path`, `root-cause`, or `real-backend`."

### Verification & Guard

- "I can run `pytest --cov=src` to measure coverage. Does that work, or do you use a different runner?"
- "Should I make sure `tsc --noEmit` still passes after each change, so we don't introduce type errors?"
- "The build takes 3 minutes. Should I use it as the guard, or is there a faster smoke test?"
- "I found `npm test` and `npm run lint` -- should I guard with both, or just tests?"

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
- "Should I remember lessons from this run for future sessions?"

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
- Guard (optional) -- Codex suggests if there's a regression risk
- Iterations (optional) -- asked only if user wants bounded run
- Required stop labels (optional) -- ask only when the run should stop on a specific mechanism, path, backend, or root-cause signal in addition to the metric target
- Rollback (optional) -- ask only if destructive rollback may be needed for unattended execution; otherwise default to non-destructive revert
- Parallel (optional) -- ask if environment supports it (CPU >= 4, RAM >= 8GB)
- Web search (optional) -- ask if user wants web search when stuck
- Lessons (optional) -- enabled by default, ask only if user wants to disable

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
- Guard (optional) -- suggested if appropriate

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
- Run mode -- ask: "Dry run first, or ship directly?"
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
- guard command is pass/fail only,
- iterations is a positive integer when provided.

If validation fails, tell the user in plain language what went wrong and suggest a fix. Do not show raw error formats.

## Launch Rules

- `plan` mode does not edit code unless the user explicitly says to launch.
- `ship` mode never performs side effects without explicit confirmation.
- After the user says "go" / "start" / "launch", begin immediately. Do not ask again.
- **Two-phase boundary:** ALL questions happen before launch. Once the loop starts, it is fully autonomous. NEVER pause to ask the user anything during execution -- not for clarification, not for confirmation, not for permission. If you encounter ambiguity mid-loop, apply best practices, log your reasoning, and keep iterating. The user may be asleep.

## Mini-Wizard (Session Resume)

When `session-resume-protocol.md` detects a prior run with a valid `autoresearch-state.json` but inconsistent TSV (Recovery Priority 2), the full wizard is replaced by a single-round mini-wizard:

1. Show what was detected:
   - Prior run tag, iteration count, best metric, and last status from the JSON state.
   - The specific inconsistency reported by `<skill-root>/scripts/autoresearch_resume_check.py` (for example retained-metric mismatch, missing main row, or stale counters).
2. Ask exactly one question with two choices:
   - **Resume:** use the JSON `config` as the authoritative source. Briefly confirm scope, metric, and verify command in a single confirmation block.
   - **Fresh start:** archive old artifacts with `.prev` suffixes and proceed with the full wizard.
3. If the user chooses to resume, present a condensed confirmation summary (same format as Step 3 above but sourced from JSON `config` instead of repo scanning).
4. The user replies "go" and the loop starts immediately in the chosen run mode:
   - foreground resume continues directly from `research-results.tsv` + `autoresearch-state.json`
   - background resume launches through `autoresearch_runtime_ctl.py launch ...`
   - fresh-start background handoff uses `autoresearch_runtime_ctl.py launch --fresh-start ...`
   No further rounds.

The mini-wizard respects the same two-phase boundary: all questions happen before launch.
