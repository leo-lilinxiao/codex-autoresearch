# Operator's Manual

How to get results from codex-autoresearch. Covers installation, the two-phase interaction model, every mode, and practical tips.

---

## Installation

Clone and copy into your project:

```bash
git clone https://github.com/leo-lilinxiao/codex-autoresearch.git
cp -r codex-autoresearch your-project/.agents/skills/codex-autoresearch
```

Or use the skill installer in Codex:

```text
$skill-installer install https://github.com/leo-lilinxiao/codex-autoresearch
```

Verify: open Codex in the target repo, type `$`, confirm `codex-autoresearch` appears.

See [INSTALL.md](INSTALL.md) for symlink, admin scope, and live-development options.

---

## How Interaction Works

Every invocation follows a two-phase model. Understanding these two phases is the single most important thing in this manual.

### Phase 1: Setup (interactive)

You say one sentence. Codex scans the repo, fills in what it can, and asks you to confirm or clarify the rest. This is a conversation -- you can steer it, add constraints, or just say "go."

```
You:   $codex-autoresearch
       I want to get rid of all the `any` types in my TypeScript code

Codex: I found 47 `any` occurrences across src/**/*.ts.

       Confirmed:
       - Target: eliminate `any` types in src/**/*.ts
       - Metric: `any` count (current: 47), direction: lower
       - Verify: grep count, Guard: tsc --noEmit

       Need to confirm:
       - Run mode: foreground or background?
       - Run until all gone, or cap at N iterations?
       - Any other safety checks beyond tsc?

       Choose a run mode, then reply "go" to start, or tell me what to change.
```

The wizard runs for at most 5 rounds. It always asks at least one confirming question, even when it could infer everything.

For unattended runs, the wizard may also ask one safety question about rollback or workspace isolation before launch. After you say "go," it stays silent.

### Phase 2: Execution (fully autonomous)

Once you say "go" (or "start", "launch", or any clear approval), the chosen run mode takes over. From this point on, Codex will never pause to ask you anything. If it hits ambiguity, it applies best practices and keeps going. In foreground it continues in the current session; in background it hands off so you can walk away, go to sleep, or work on something else.
For that to hold in practice, launch Codex CLI with approvals / sandbox settings that will not interrupt git commit or revert commands. In a disposable or otherwise trusted repo, giving Codex fuller permissions is the simplest option.

The only things that stop the loop:

- You interrupt Codex
- The iteration cap is reached (if you set one)
- A hard blocker appears (verify command broken, repo corrupted, disk full, same crash 5+ times)

This boundary is absolute at the skill level. Everything before "go" can ask. Everything after "go" is silent.

---

## The Iteration Cycle

Every iterating mode (loop, debug, fix, security, ship) shares the same cycle:

```
  Pick hypothesis  -->  Edit files  -->  git commit  -->  Run verify + guard
  (consult lessons,                                            |
   apply perspectives,                                     improved?
   filter by environment)                                 /         \
                                                        yes          no
                                                        /              \
                                                     KEEP           REVERT
                                                  (+lesson)            |
                                                      \              /
                                                       +-- Log -----+
                                                            |
                                                      Health check
                                                            |
                                                    3+ discards? --yes--> REFINE/PIVOT
                                                            |
                                                          repeat
```

1. **Hypothesis** -- one focused idea based on what worked, what failed, what is untried
2. **Edit** -- change files within the declared scope only
3. **Commit** -- `git commit` before verification (so revert is always safe)
4. **Verify** -- run the verify command, extract the metric value
5. **Guard** -- if set, run the guard command to check for regressions
6. **Decide** -- metric improved and guard passed = keep; otherwise revert
7. **Log** -- append result to `research-results.tsv`

Revert uses the rollback strategy approved during setup. In a dedicated experiment branch/worktree with pre-launch approval, it may use `git reset --hard HEAD~1`; otherwise it uses `git revert --no-edit HEAD`.

Run artifacts should be updated by the helper scripts rather than hand-editing TSV or JSON. Use the skill-bundle path, not the target repo's own `scripts/` directory. Here `<skill-root>` means the directory containing the loaded `SKILL.md`; in the common repo-local install this is `.agents/skills/codex-autoresearch`.

- `python3 <skill-root>/scripts/autoresearch_init_run.py`
- `python3 <skill-root>/scripts/autoresearch_record_iteration.py`
- `python3 <skill-root>/scripts/autoresearch_resume_check.py`
- `python3 <skill-root>/scripts/autoresearch_select_parallel_batch.py`
- `python3 <skill-root>/scripts/autoresearch_supervisor_status.py`

### Verify and Guard: two gates, two questions

| Gate | Question | On failure |
|------|----------|------------|
| Verify | Did the metric improve? | Revert immediately |
| Guard | Did anything else break? | Rework (up to 2 attempts), then revert |

A good pairing answers two different questions:

```
Verify: pytest --cov=src --cov-report=term 2>&1 | grep TOTAL | awk '{print $NF}'
        ^ "Did coverage go up?"

Guard:  npx tsc --noEmit
        ^ "Do types still compile?"
```

Another example:

```
Verify: node scripts/count-lint-warnings.js
        ^ "Did warning count go down?"

Guard:  npm run test:unit
        ^ "Do unit tests still pass?"
```

Guard is optional. Use it when improving one metric could hurt something else.

---

## Configuration Fields

Codex infers these from your natural language input and repo context. You never need to write them -- the wizard handles translation. They are documented here for understanding.

### Required (loop mode)

| Field | What it is | Example |
|-------|------------|---------|
| `Goal` | Plain-language target | "Eliminate all type errors" |
| `Scope` | File globs Codex may modify | `src/**/*.ts` |
| `Metric` | The number being tracked | type error count |
| `Direction` | `higher` or `lower` | `lower` |
| `Verify` | Shell command that outputs the metric | `tsc --noEmit 2>&1 \| wc -l` |

### Optional

| Field | Default | What it does |
|-------|---------|--------------|
| `Guard` | none | Regression-prevention command that must always pass |
| `Iterations` | unlimited | Stop after N iterations |
| `Run tag` | auto-generated | Label for this run in the results log |
| `Stop condition` | none | Custom early-stop rule (e.g., "stop when metric reaches 1" or "stop when metric reaches 90") |

### Bounded vs unbounded runs

By default the loop runs until you interrupt it. Tell Codex to cap it:

```
You:   Go, but only 10 iterations.
```

or:

```
You:   Run overnight, no limit.
```

When to use each:

- **Overnight exploration** -- unlimited. Let Codex try dozens of approaches.
- **Focused fix** -- 5-10 iterations. The problem space is small.
- **Quick experiment** -- 3-5 iterations. You just want to see if the approach works.

Bounded runs print a final summary comparing baseline to best result.

---

## Modes

Seven modes, one invocation pattern: `$codex-autoresearch` followed by a sentence. Codex auto-detects which mode fits. You can also force a mode by saying it explicitly (e.g., "use debug mode").

### loop

The default. Iterates toward a measurable target.

```
You:   $codex-autoresearch
       Our TypeScript codebase has 47 `any` types, eliminate them all

Codex: [scans repo, confirms target, asks about iteration cap]

You:   Go, run overnight.

Codex: Starting -- baseline: 47. Iterating until interrupted.
       ...
       Iteration 1: replaced any in auth module -> 41 (-6) KEEP
       Iteration 2: generic wrapper attempt -> 49 (+8) DISCARD
       Iteration 3: narrowed API handlers -> 38 (-3) KEEP
       ...
```

Reference: `references/autonomous-loop-protocol.md`

### plan

Converts a vague goal into a concrete loop configuration. Use when you know what you want but not how to measure it.

```
You:   $codex-autoresearch
       I want to make our API faster but I don't know where to start

Codex: I scanned the repo. API layer is in src/api/ with Express + Prisma.

       Need to confirm:
       - What matters more: p95 latency, throughput, or cold start?
       - Should I benchmark the whole API or specific endpoints?

You:   p95 latency, the /search endpoint is the worst.

Codex: [proposes config, dry-runs the verify command, outputs ready-to-use block]
```

Plan mode is read-only -- it never modifies your code.

Reference: `references/plan-workflow.md`

### debug

Evidence-driven bug hunting. Each iteration tests one falsifiable hypothesis.

```
You:   $codex-autoresearch
       API returns 503 randomly under load, no idea why

Codex: I see connection pooling in src/db/pool.ts, rate limiting in
       src/middleware/, and 3 async handlers without error boundaries.

       Need to confirm:
       - When did this start? After a specific change, or always?
       - If I find the cause, should I also fix it?

You:   Started after the pool refactor last week. Find cause first.

Codex: Starting investigation.
       ...
       Hypothesis 1: pool exhaustion under concurrent requests
         Evidence: pool.ts max=10, /search handler holds 3 connections
         Result: CONFIRMED -- pool saturates at 4 concurrent /search calls
       ...
```

Debug mode produces a findings directory with confirmed causes, disproven hypotheses, and recommended fixes.

To repair the findings afterward, start a new invocation:

```
You:   $codex-autoresearch
       Fix the bugs you found in the last debug session
```

Codex reads the debug output directory and enters fix mode automatically.

Reference: `references/debug-workflow.md`

### fix

Iteratively repairs errors until the count reaches zero. Auto-detects what is broken (tests, types, lint, build).

```
You:   $codex-autoresearch
       pytest is failing, 12 tests broken after the refactor

Codex: I see 12 failures across tests/.

       Confirmed:
       - Target: make all pytest tests pass
       - Current: 12 failures

       Need to confirm:
       - Should I also guard with ruff to avoid introducing lint issues?
       - Fix all 12, or focus on a specific module first?

You:   Fix all, yes guard with ruff. Go.

Codex: Starting -- baseline: 12 failures.
       ...
       Iteration 1: fixed import path in test_auth.py -> 10 (-2) KEEP
       ...
```

Fix mode stops automatically when the error count reaches zero.

Reference: `references/fix-workflow.md`

### security

Read-only structured audit using STRIDE threat modeling, OWASP Top 10, and red-team analysis. Every finding requires code evidence -- no theoretical vulnerabilities.

```
You:   $codex-autoresearch
       Check our API for injection vulnerabilities

Codex: Confirmed:
       - Scope: src/api/ and src/middleware/ (14 files)
       - Focus: SQL injection, XSS, input sanitization

       Need to confirm:
       - Report only, or also fix critical findings?
       - Should I also cover auth/access control?

You:   Report first, and yes cover auth too.

Codex: Starting audit.
       ...
       Finding S-1 [HIGH]: SQL injection in src/api/search.ts:42
         Raw user input passed to query builder without parameterization
         Exploitation: POST /search with payload `'; DROP TABLE users;--`
       ...
```

Security mode is read-only by default. To also repair findings, say so during setup:

```
You:   Find vulnerabilities and fix the critical ones.
```

Codex will audit first, then switch to fix mode for Critical/High findings.

Reference: `references/security-workflow.md`

### ship

Gated release verification. Auto-detects what you are shipping (PR, deployment, release) and generates a checklist.

Under the hood, ship mode still resolves a shipment scope, a readiness metric, and a mechanical verify command before the chosen interactive run mode begins.

```
You:   $codex-autoresearch
       Ship it

Codex: Detected: PR to main with 3 commits.

       Confirmed:
       - Type: code PR
       - Target: main branch

       Need to confirm:
       - Dry run first, or go live?
       - Post-ship monitoring? (5 min / 15 min / skip)

You:   Dry run first.
```

External actions (deploy, publish, merge) must be confirmed during this setup phase. If not confirmed before "go," they are skipped and logged as blockers.

Reference: `references/ship-workflow.md`

---

## Mode Chaining

Modes compose naturally through sequential invocations:

**Find then fix:**

```
You:   $codex-autoresearch
       API returns 503 randomly under load
       [debug mode runs, produces findings]

You:   $codex-autoresearch
       Fix the bugs you just found
       [fix mode runs, imports debug findings]
```

**Plan then execute:**

```
You:   $codex-autoresearch
       I want to reduce our API latency but not sure how to measure it
       [plan mode runs, produces config]

You:   $codex-autoresearch
       [paste the config plan generated, or just say "run the plan you made"]
```

**Audit then remediate:**

```
You:   $codex-autoresearch
       Audit the auth system for vulnerabilities, then fix anything critical
       [security mode audits, then automatically switches to fix mode]
```

---

## Results Log

Every iteration is recorded in `research-results.tsv`:

```
iteration  commit   metric  delta   status    description
0          a1b2c3d  47      0       baseline  initial any count
1          b2c3d4e  41      -6      keep      replace any in auth module with strict types
2          c3d4e5f  49      +8      discard   generic wrapper introduced new anys
3          c3d4e5f  38      -3      keep      type-narrow API response handlers
```

Progress summaries print every 5 iterations. Bounded runs print a final baseline-to-best summary.

The TSV file is the real audit trail -- not the git history (failed experiments are reverted from git but preserved in the log).

`research-results.tsv`, `autoresearch-state.json`, and `autoresearch-lessons.md` are treated as autoresearch-owned artifacts: they stay uncommitted and are not staged as experiment changes.

---

## Workspace Requirements

The loop commits and reverts repeatedly. This requires a clean workspace.

If unrelated uncommitted changes exist:
- The loop will not start
- Use plan mode instead (read-only, no git requirements)
- Or isolate the work in a clean branch or worktree

---

## Output Artifacts

| Mode | What it produces |
|------|------------------|
| loop | `research-results.tsv`, `autoresearch-lessons.md`, `autoresearch-state.json` |
| plan | Config block printed inline (ready to paste) |
| debug | `research-results.tsv`, `autoresearch-lessons.md`, `autoresearch-state.json`, plus `debug/{YYMMDD}-{HHMM}-{slug}/` findings |
| fix | `research-results.tsv`, `autoresearch-lessons.md`, `autoresearch-state.json`, plus `fix/{YYMMDD}-{HHMM}-{slug}/` fix log |
| security | `research-results.tsv`, `autoresearch-lessons.md`, `autoresearch-state.json`, plus `security/{YYMMDD}-{HHMM}-{slug}/` audit report |
| ship | `research-results.tsv`, `autoresearch-lessons.md`, `autoresearch-state.json`, plus `ship/{YYMMDD}-{HHMM}-{slug}/` checklist and verification |
| exec | `research-results.tsv`, JSON lines to stdout, exit code |

---

## Safety Model

| Concern | How it is handled |
|---------|-------------------|
| Dirty worktree | Runtime preflight blocks launch or relaunch until out-of-scope changes are cleaned up or isolated |
| Failed change | Uses the rollback strategy approved before launch: approved hard reset in an isolated experiment branch/worktree, otherwise `git revert --no-edit HEAD`; results log is the audit trail |
| Guard failure | Up to 2 rework attempts before discarding |
| Syntax error | Auto-fix immediately, does not count as iteration |
| Runtime crash | Up to 3 fix attempts, then skip |
| Resource exhaustion | Revert, try smaller variant |
| Hanging process | Kill after timeout, revert |
| Stuck (3+ consecutive discards) | REFINE strategy; 5+ -> PIVOT; escalate to web search; then soft blocker |
| Ambiguity mid-loop | Apply best practices autonomously; never pause to ask the user |
| External side effects | Ship mode requires explicit confirmation during setup phase |
| Environment limits | Probed at startup; infeasible hypotheses filtered |
| Interrupted session | Resume from last consistent state |
| Context drift (long runs) | Protocol Fingerprint Check every 10 iterations; increase check frequency after compaction; re-read from disk on failure |

---

## Cross-Run Learning

Every iterating run except `exec` extracts structured lessons and persists them to `autoresearch-lessons.md` (alongside the results log, never committed). Future runs consult lessons to bias hypothesis generation. `exec` may read existing lessons, but it does not create or update them.

How it works:
- After every kept iteration: positive lesson (what worked and why)
- After every PIVOT: strategic lesson (what was abandoned and why)
- At run completion: summary lesson (best strategy family for this goal type)
- Cap: 50 entries. Older entries are summarized with time decay.

Lessons carry across runs and across goals. A lesson from optimizing test coverage can inform a later run optimizing build warnings if the strategy families overlap.

---

## Smart Stuck Recovery (PIVOT / REFINE)

The loop uses a graduated escalation system instead of blind retrying:

1. **REFINE** (3 consecutive discards): Adjust within current strategy -- different file, different technique, different granularity. Consult lessons for similar past failures.

2. **PIVOT** (5 consecutive discards): Abandon current strategy entirely. Re-read everything, choose a fundamentally different approach. Extract a strategic lesson.

3. **Web Search** (2 PIVOTs without improvement): Search the web for solutions if available. Results are treated as hypotheses and verified mechanically.

4. **Soft Blocker** (3 PIVOTs without improvement): Print a warning, continue with increasingly bold changes. The loop never stops unless a hard blocker appears.

A single successful keep resets all escalation counters to zero.

---

## Parallel Experiments

When enabled during the wizard, the loop can test multiple hypotheses per iteration using subagent workers in isolated git worktrees:

- The orchestrator generates N hypotheses (max 3).
- Each worker applies one hypothesis, runs verify, and reports results.
- The orchestrator picks the best result, merges it, and discards the rest.
- If no result improved, it counts as a single discard for PIVOT tracking.

Parallel mode is suggested during the wizard when the environment has enough resources (CPU >= 4, RAM >= 8GB, sufficient disk). Falls back to serial if worktrees are unsupported.

---

## Session Resume

If you interrupt a run and come back later, Codex can resume from where you left off:

- It first validates `autoresearch-state.json`, the primary recovery source, against the retained-state summary reconstructed from `research-results.tsv`.
- `autoresearch-lessons.md` is still read as context, but it is not the primary resume source.
- Foreground resume uses `research-results.tsv` plus `autoresearch-state.json`.
- Direct detached-runtime resume still requires an existing `autoresearch-launch.json`.
- If state is consistent: resumes immediately, no wizard needed. Background resume additionally requires the launch manifest.
- If state is partially consistent: runs a mini-wizard (1 round) to re-confirm.
- If state is inconsistent, the launch manifest is missing, or the goal has changed: starts fresh and archives the prior persistent run-control artifacts.

---

## Long Run Stability

Long-running sessions (20+ iterations) may experience context drift when the CLI compacts the conversation to stay within context limits. The skill includes three layers of defense:

### Automatic Re-Anchoring

Every 10 iterations (or more frequently after compaction), the agent runs a Protocol Fingerprint Check -- a zero-cost internal self-test that verifies it still remembers all critical rules and phase definitions. If any item fails, the agent re-reads the protocol files from disk before continuing. These events are marked with `[RE-ANCHOR]` in the results log.

You do not need to do anything to enable this. It runs automatically as part of Phase 8.7 in the iteration cycle.

### Interactive Run Modes

The public human workflow now stays on a single entrypoint: `$codex-autoresearch`.

1. Start the skill and describe the goal naturally.
2. Answer the confirmation questions.
3. Choose **foreground** or **background**.
4. Reply `go`.
5. In **foreground**, Codex keeps the loop in the current session. Only `research-results.tsv`, `autoresearch-state.json`, and lessons are created.
6. In **background**, Codex writes `autoresearch-launch.json` and starts the detached runtime controller automatically.
   The two modes share the same loop protocol and repo/scope semantics, but they are mutually exclusive for a given repo/run. Do not keep both modes active against the same primary repo artifacts at once.
7. If you resume an existing interactive run in the other mode, continue through the same `$codex-autoresearch` entrypoint. The shared state must be synchronized to the chosen mode before continuing; scripted background `start` performs that sync automatically before it relaunches.
8. Single-repo runs are still the default. In that case the declared scope applies only to the primary repo that owns the run-control artifacts.
9. If the experiment spans multiple repos, either mode can declare companion repos with their own scopes. `research-results.tsv` and `autoresearch-state.json` stay anchored in the primary repo; background mode also keeps launch/runtime control files there.
   Script-level entrypoints represent this with repeated `--companion-repo-scope PATH=SCOPE` flags.
   The TSV `commit` column remains the primary repo commit; companion-repo commit provenance lives in `autoresearch-state.json`.
10. Each background runtime cycle launches a non-interactive `codex exec` session with the runtime prompt supplied on stdin.
   Background launch manifests carry an `execution_policy`; this skill now defaults to `danger_full_access`, so detached sessions run with `--dangerously-bypass-approvals-and-sandbox` unless you explicitly opt back into the sandboxed `workspace_write` path.
11. Before each background detached session or relaunch, the runtime controller runs `autoresearch_health_check.py` and `autoresearch_commit_gate.py` so integrity and scope safety are enforced at the control-plane boundary across all managed repos.
12. If background `codex exec` itself cannot be launched, the runtime moves to `needs_human` instead of silently looking idle.
13. If an explicit stop request cannot actually terminate the detached runner, the runtime also moves to `needs_human` instead of pretending the run is fully stopped.

Foreground keeps iterating in the current session until a terminal condition, blocker, or interruption. Background continues through fresh Codex sessions in the background until a terminal condition, blocker, or explicit stop request.

Use the same skill entry for follow-up control:

- ask for status -> background mode only; the skill reads the runtime controller state
- ask to stop -> background mode only; the skill stops the runtime controller
- ask to resume -> the skill checks launch/runtime state and continues if safe

Advanced backend commands are still available for scripting or debugging:

```bash
python3 <skill-root>/scripts/autoresearch_resume_check.py --repo /path/to/repo
python3 <skill-root>/scripts/autoresearch_launch_gate.py --repo /path/to/repo
python3 <skill-root>/scripts/autoresearch_resume_prompt.py --repo /path/to/repo
python3 <skill-root>/scripts/autoresearch_supervisor_status.py --repo /path/to/repo
python3 <skill-root>/scripts/autoresearch_runtime_ctl.py status --repo /path/to/repo
python3 <skill-root>/scripts/autoresearch_runtime_ctl.py stop --repo /path/to/repo
```


---

## Environment Awareness

At the start of every run, Codex probes the environment:

- CPU cores, RAM, disk space
- GPU/NPU detection (NVIDIA, Ascend, ROCm, Apple Silicon)
- Installed toolchains (Python, Node.js, Go, Rust, Java)
- Container detection (Docker, Kubernetes)
- Network availability

This data filters infeasible hypotheses (e.g., no GPU optimization without a GPU) and informs resource-appropriate suggestions during plan mode.

---

## CI/CD Mode (exec)

Non-interactive mode for automation pipelines. Differences from interactive mode:

- No wizard -- all config provided upfront in the `codex exec` prompt or via environment variables
- Always bounded (Iterations field is mandatory)
- JSON output (one line per iteration, completion summary at end)
- No web search, no parallel, no session resume
- Reads lessons if available, but does not write them
- Exit codes: 0 = improved, 1 = no improvement, 2 = hard blocker

Before using `codex exec` in CI, configure Codex CLI authentication in advance. In controlled automation environments, prefer `codex exec --dangerously-bypass-approvals-and-sandbox ...` so the verify command has the same full-access behavior as the managed runtime. For programmatic runs, API key authentication is the preferred option.

When the bundled helper scripts drive `Mode: exec`, do not manually rename old repo-root artifacts first. `autoresearch_init_run.py --mode exec ...` already archives the default `research-results.tsv` and `autoresearch-state.json` files to `research-results.prev.tsv` and `autoresearch-state.prev.json` before it initializes the fresh run.

See `references/exec-workflow.md` for full details and CI integration examples.

---

## Troubleshooting

### The skill does not appear

- Confirm the folder is at `.agents/skills/codex-autoresearch` or `~/.agents/skills/codex-autoresearch`
- Confirm `SKILL.md` exists at the root of that folder
- Restart Codex after installation changes

### Codex starts without asking

This should not happen. Rule 1 requires at least one confirming question. If it does happen, the skill may not be loading correctly -- check the installation path.

### The loop stops and asks a question

This should not happen after you say "go." If it does, report it as a bug. The two-phase boundary is a hard rule.

### How do I see runtime status or stop a run?

Use the same `$codex-autoresearch` entry and ask for status or stop, but note that these are background-run controls. Foreground runs stay in the active session and therefore do not use `autoresearch_runtime_ctl.py` status/stop files.

### The verify command fails on the first run

Codex will attempt to fix it. If plan mode generated the config, it may dry-run the verify command when practical before outputting the block. If you wrote the verify command yourself, test it manually first.

### The loop refuses to commit

- Check for unrelated uncommitted changes (`git status`)
- Isolate work in a clean branch or worktree
- Use plan mode first if the workspace is not clean

### Can I use this without git?

Plan mode and security mode (read-only) work without git. The iterative loop requires git for its commit/revert safety model.

### Can I use this with any language?

Yes. The protocol is language-agnostic. Only the verify and guard commands are domain-specific.
