<p align="center">
  <img src="image/banner.png" width="700" alt="Codex Autoresearch">
</p>

<h2 align="center"><b>Aim. Iterate. Arrive.</b></h2>

<p align="center">
  <i>Autonomous goal-driven experimentation for Codex.</i>
</p>

<p align="center">
  <a href="https://developers.openai.com/codex/skills"><img src="https://img.shields.io/badge/Codex-Skill-blue?logo=openai&logoColor=white" alt="Codex Skill"></a>
  <a href="https://github.com/leo-lilinxiao/codex-autoresearch"><img src="https://img.shields.io/github/stars/leo-lilinxiao/codex-autoresearch?style=social" alt="GitHub Stars"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="MIT License"></a>
</p>

<p align="center">
  <b>English</b> ·
  <a href="docs/i18n/README_ZH.md">🇨🇳 中文</a> ·
  <a href="docs/i18n/README_JA.md">🇯🇵 日本語</a> ·
  <a href="docs/i18n/README_KO.md">🇰🇷 한국어</a> ·
  <a href="docs/i18n/README_FR.md">🇫🇷 Français</a> ·
  <a href="docs/i18n/README_DE.md">🇩🇪 Deutsch</a> ·
  <a href="docs/i18n/README_ES.md">🇪🇸 Español</a> ·
  <a href="docs/i18n/README_PT.md">🇧🇷 Português</a> ·
  <a href="docs/i18n/README_RU.md">🇷🇺 Русский</a>
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> ·
  <a href="#what-it-does">What It Does</a> ·
  <a href="#architecture">Architecture</a> ·
  <a href="#how-it-works">How It Works</a> ·
  <a href="#what-codex-figures-out">What Codex Figures Out</a> ·
  <a href="#cross-run-learning">Learning</a> ·
  <a href="#parallel-experiments">Parallel</a> ·
  <a href="docs/GUIDE.md">Guide</a> ·
  <a href="docs/EXAMPLES.md">Recipes</a>
</p>

---

## Quick Start

**1. Install:**

```bash
git clone https://github.com/leo-lilinxiao/codex-autoresearch.git
cp -r codex-autoresearch your-project/.agents/skills/codex-autoresearch
```

Or use the skill installer in Codex:
```text
$skill-installer install https://github.com/leo-lilinxiao/codex-autoresearch
```

**2. Open Codex in your project and say what you want:**

```text
$codex-autoresearch
I want to get rid of all the `any` types in my TypeScript code
```

**3. Codex scans, confirms, then iterates autonomously:**

```
Codex: I found 47 `any` occurrences across src/**/*.ts.

       Confirmed:
       - Target: eliminate `any` types in src/**/*.ts
       - Metric: `any` count (current: 47), direction: lower
       - Verify: grep + tsc --noEmit as guard

       Need to confirm:
       - Run until all gone, or cap at N iterations?

       Reply "go" to start, or tell me what to change.

       For truly unattended runs, launch Codex with approvals / sandbox settings
       that will not interrupt git commit or revert commands.

You:   Go, run overnight.

Codex: Starting -- baseline: 47. Iterating until interrupted.
```

Each improvement stacks. Each failure reverts. Everything is logged.

See [INSTALL.md](docs/INSTALL.md) for more install options. See [GUIDE.md](docs/GUIDE.md) for full operator's manual.

---

## What It Does

A Codex skill that runs a modify-verify-decide loop on your codebase. Each iteration makes one atomic change, verifies it against a mechanical metric, and keeps or discards the result. Progress accumulates in git; failures auto-revert. Best for unattended runs where you want Codex to keep pushing toward a measurable result for minutes, hours, or overnight.

Inspired by [Karpathy's autoresearch](https://github.com/karpathy/autoresearch) principles, generalized beyond ML.

### Why This Exists

Karpathy's autoresearch proved that a simple loop -- modify, verify, keep or discard, repeat -- can push ML training from baseline to new highs overnight. codex-autoresearch generalizes that loop to everything in software engineering that has a number. Test coverage, type errors, performance latency, lint warnings -- if there is a metric, it can iterate autonomously.

---

## Architecture

```
              +---------------------+
              |  Environment Probe  |  <-- Phase 0: detect CPU/GPU/RAM/toolchains
              +---------+-----------+
                        |
              +---------v-----------+
              |  Session Resume?    |  <-- check for prior run artifacts
              +---------+-----------+
                        |
              +---------v-----------+
              |   Read Context      |  <-- read scope + lessons file
              +---------+-----------+
                        |
              +---------v-----------+
              | Establish Baseline  |  <-- iteration #0
              +---------+-----------+
                        |
         +--------------v--------------+
         |                             |
         |  +----------------------+   |
         |  | Choose Hypothesis    |   |  <-- consult lessons + perspectives
         |  | (or N for parallel)  |   |      filter by environment
         |  +---------+------------+   |
         |            |                |
         |  +---------v------------+   |
         |  | Make ONE Change      |   |
         |  +---------+------------+   |
         |            |                |
         |  +---------v------------+   |
         |  | git commit           |   |
         |  +---------+------------+   |
         |            |                |
         |  +---------v------------+   |
         |  | Run Verify + Guard   |   |
         |  +---------+------------+   |
         |            |                |
         |        improved?            |
         |       /         \           |
         |     yes          no         |
         |     /              \        |
         |  +-v------+   +----v-----+ |
         |  |  KEEP  |   | REVERT   | |
         |  |+lesson |   +----+-----+ |
         |  +--+-----+        |       |
         |      \            /         |
         |   +--v----------v---+      |
         |   |   Log Result    |      |
         |   +--------+--------+      |
         |            |               |
         |   +--------v--------+      |
         |   |  Health Check   |      |  <-- disk, git, verify health
         |   +--------+--------+      |
         |            |               |
         |     3+ discards?           |
         |    /             \         |
         |  no              yes       |
         |  |          +----v-----+   |
         |  |          | REFINE / |   |  <-- pivot-protocol escalation
         |  |          | PIVOT    |   |
         |  |          +----+-----+   |
         |  |               |         |
         +--+------+--------+         |
         |         (repeat)           |
         +----------------------------+
```

The loop runs until interrupted (unbounded) or for exactly N iterations (bounded via `Iterations: N`).

**In pseudocode:**

```
PHASE 0: Probe environment, check for session resume
PHASE 1: Read context + lessons file

LOOP (forever or N times):
  1. Review current state + git history + results log + lessons
  2. Pick ONE hypothesis (apply perspectives, filter by environment)
     -- or N hypotheses if parallel mode is active
  3. Make ONE atomic change
  4. git commit (before verification)
  5. Run mechanical verification + guard
  6. Improved -> keep (extract lesson). Worse -> approved rollback strategy. Crashed -> fix or skip.
  7. Log the result
  8. Health check (disk, git, verify health)
  9. If 3+ discards -> REFINE; 5+ -> PIVOT; 2 PIVOTs -> web search
  10. Repeat. Never stop. Never ask.
```

---

## How It Works

You say what you want in one sentence. Codex does the rest.

It scans your repo, proposes a plan, confirms with you, then iterates autonomously:

| You say | What happens |
|---------|-------------|
| "Improve my test coverage" | Scans repo, proposes metric, iterates until target or interrupted |
| "Fix the 12 failing tests" | Detects failures, repairs one by one until zero remain |
| "Why is the API returning 503?" | Hunts root cause with falsifiable hypotheses and evidence |
| "Is this code secure?" | Runs STRIDE + OWASP audit, every finding backed by code evidence |
| "Ship it" | Verifies readiness, generates checklist, gates release |
| "I want to optimize but don't know what to measure" | Analyzes repo, suggests metrics, generates launch-ready config |

Behind the scenes, Codex maps your sentence to one of 7 specialized modes
(loop, plan, debug, fix, security, ship, exec). You never need to pick a mode --
just describe your goal.

---

## What Codex Figures Out

Codex infers everything from your sentence and your repo. You never write config.

| What it needs | How it gets it | Example |
|--------------|----------------|---------|
| Goal | Your sentence | "get rid of all any types" |
| Scope | Scans repo structure | auto-discovers src/**/*.ts |
| Metric | Proposes based on goal + tooling | any count (current: 47) |
| Direction | Infers from "improve" / "reduce" / "eliminate" | lower |
| Verify command | Matches to repo tooling | grep count + tsc --noEmit |
| Guard (optional) | Suggests if regression risk exists | npm test |

Before starting, Codex always shows you what it found and asks you to confirm.
One round of confirmation minimum, up to five if needed. Then you say "go" and walk away.
For truly unattended runs, start Codex CLI with approvals / sandbox settings that will not interrupt git commit or revert commands. In a disposable or otherwise trusted repo, giving Codex fuller permissions is the simplest option.

### Dual-gate verification

Two commands serve different purposes:

- **Verify** = "Did the target metric improve?" (measures progress)
- **Guard** = "Did anything else break?" (prevents regressions)

```text
Verify: pytest --cov=src --cov-report=term 2>&1 | grep TOTAL | awk '{print $NF}'   # did coverage go up?
Guard: npx tsc --noEmit                                                              # do types still pass?
```

If verify passes but guard fails, the change is reworked (up to 2 attempts). Guard files are never modified.

---

## Mode Details

### loop

The default mode. Iterates toward a measurable target.

```
You:   Get rid of all `any` types in my TypeScript code

Codex: Found 47 `any` in src/**/*.ts.

       Confirmed:
       - Target: eliminate all `any` types
       - Metric: count of `any` (current: 47), direction: lower
       - Verify: grep count, Guard: tsc --noEmit

       Need to confirm:
       - Run until zero, or cap at N iterations?

       Reply "go" to start.

You:   Go, overnight.
```

### plan

Converts a vague goal into a validated loop configuration.

```
You:   I want to make our API faster but I don't know where to start

Codex: I scanned the repo. API layer is in src/api/ with Express + Prisma.

       Need to confirm:
       - What matters more: p95 latency, throughput, or cold start?
       - Should I benchmark the whole API or specific endpoints?

       Reply with your priority.

You:   p95 latency, the /search endpoint is the worst.
```

### debug

Evidence-driven bug hunting. Each iteration tests one falsifiable hypothesis.

```
You:   Our API returns 503 randomly under load, no idea why

Codex: I see connection pooling in src/db/pool.ts, rate limiting in src/middleware/,
       and 3 async handlers without error boundaries.

       Confirmed:
       - Symptom: intermittent 503 under concurrent load
       - Scope: src/api/, src/db/, src/middleware/

       Need to confirm:
       - When did this start? After a specific change, or always?
       - If I find the cause, should I also fix it?

       Reply with context.

You:   Started after the connection pool refactor last week. Find cause first.
```

### fix

Iteratively repairs errors until the count reaches zero.

```
You:   pytest is failing, 12 tests broken after the refactor

Codex: I see 12 failures across tests/.

       Confirmed:
       - Target: make all pytest tests pass
       - Current: 12 failures

       Need to confirm:
       - Should I also guard with ruff to avoid introducing lint issues?
       - Fix all 12, or focus on a specific module first?

       Reply "go" to start.

You:   Fix all, yes guard with ruff. Go.
```

### security

Read-only STRIDE + OWASP + red-team audit. Every finding requires code evidence.

```
You:   Check our API for injection vulnerabilities

Codex: Confirmed:
       - Scope: src/api/ and src/middleware/ (14 files)
       - Focus: SQL injection, XSS, input sanitization

       Need to confirm:
       - Report only, or also fix critical findings?
       - Should I also cover auth/access control?

       Reply with preference.

You:   Report first, and yes cover auth too.
```

### ship

Gated release verification. Auto-detects what you are shipping (PR, deployment, release).

Internally, ship mode still derives a shipment scope, a readiness metric, and a mechanical verify command from the checklist before launch.

```
You:   Ship it

Codex: Detected: PR to main with 3 commits.

       Confirmed:
       - Type: code PR
       - Target: main branch

       Need to confirm:
       - Dry run first, or go live?
       - Post-ship monitoring? (5 min / 15 min / skip)

       Reply with preference.

You:   Dry run first.
```

See [GUIDE.md](docs/GUIDE.md) for detailed usage and advanced options for each mode.

---

## Mode Chaining

Modes can be composed sequentially:

```
plan  -->  loop              # figure out config, then execute
debug -->  fix               # find bugs, then repair them
security + fix               # audit and remediate in one pass
```

---

## Cross-Run Learning

Every iterating run except `exec` extracts structured lessons -- what worked, what failed, and why. Lessons are persisted in `autoresearch-lessons.md` (uncommitted, like the results log) and consulted at the start of future runs to bias hypothesis generation toward proven strategies and away from known dead ends. `exec` mode may read existing lessons, but it never creates or updates them.

- Positive lessons after every kept iteration
- Strategic lessons after every PIVOT decision
- Summary lessons at run completion
- Capacity: 50 entries max, older entries summarized with time decay

See `references/lessons-protocol.md` for details.

---

## Smart Stuck Recovery

Instead of blindly retrying after failures, the loop uses a graduated escalation system:

| Trigger | Action |
|---------|--------|
| 3 consecutive discards | **REFINE** -- adjust within current strategy |
| 5 consecutive discards | **PIVOT** -- abandon strategy, try fundamentally different approach |
| 2 PIVOTs without improvement | **Web search** -- look for external solutions |
| 3 PIVOTs without improvement | **Soft blocker** -- warn and continue with bolder changes |

A single successful keep resets all counters. See `references/pivot-protocol.md`.

---

## Parallel Experiments

Test multiple hypotheses simultaneously using subagent workers in isolated git worktrees:

```
Orchestrator (main agent)
  +-- Worker A (worktree-a) -> hypothesis 1
  +-- Worker B (worktree-b) -> hypothesis 2
  +-- Worker C (worktree-c) -> hypothesis 3
```

The orchestrator picks the best result, merges it, and discards the rest. Enable during the wizard by saying "yes" to parallel experiments. Falls back to serial if worktrees are unsupported.

See `references/parallel-experiments-protocol.md`.

---

## Session Resume

If Codex detects a prior interrupted managed run, it can resume from the last consistent state instead of starting over. The primary recovery source is `autoresearch-state.json`, a compact state snapshot atomically updated each iteration. The TSV results log serves as a cross-validation fallback. Direct detached-runtime resume requires an existing `autoresearch-launch.json`; if that confirmed launch state is missing, start a new run through the normal launch flow instead.

Recovery priority:

1. **JSON + TSV summary consistent, launch manifest present:** resume immediately, skip wizard
2. **JSON valid, helper reports mismatch:** mini-wizard (1 round) to re-confirm
3. **JSON missing or corrupt, TSV exists:** helper reconstructs retained state for confirmation, then continue with a fresh launch manifest
4. **Neither exists:** fresh start (prior persistent run-control artifacts archived)

See `references/session-resume-protocol.md`.

---

## CI/CD Mode (exec)

Non-interactive mode for automation pipelines. All config is provided upfront -- no wizard, always bounded, JSON output.

```yaml
# GitHub Actions example
- name: Autoresearch optimization
  run: |
    codex exec <<'PROMPT'
    $codex-autoresearch
    Mode: exec
    Goal: Reduce type errors
    Scope: src/**/*.ts
    Metric: type error count
    Direction: lower
    Verify: tsc --noEmit 2>&1 | grep -c error
    Iterations: 20
    PROMPT
```

Exit codes: 0 = improved, 1 = no improvement, 2 = hard blocker.

Before using `codex exec` in CI, configure Codex CLI authentication in advance. For programmatic runs, API key authentication is the preferred option.

See `references/exec-workflow.md`.

---

## Results Log

Every iteration is recorded in complementary artifacts:

- **`research-results.tsv`** -- full audit trail, with one main row per iteration plus optional parallel worker rows
- **`autoresearch-state.json`** -- compact state snapshot for fast session resume in interactive modes
- **`autoresearch-launch.json`** -- confirmed launch manifest written after the user says `go`
- **`autoresearch-runtime.json`** -- runtime control state (PID, status, last decision)
- **`autoresearch-runtime.log`** -- detached runtime log for long runs

In `exec` mode, the state snapshot is scratch-only under `/tmp/codex-autoresearch-exec/...`. The exec workflow is responsible for removing that scratch JSON before exit, typically via `autoresearch_exec_state.py --cleanup`.

```
iteration  commit   metric  delta   status    description
0          a1b2c3d  47      0       baseline  initial any count
1          b2c3d4e  41      -6      keep      replace any in auth module with strict types
2          c3d4e5f  49      +8      discard   generic wrapper introduced new anys
3          c3d4e5f  38      -3      keep      type-narrow API response handlers
```

These files stay uncommitted and are treated as autoresearch-owned artifacts, not normal experiment diffs. On session resume, the JSON state is cross-validated against a reconstructed TSV main-iteration summary instead of raw row counts. Progress summaries print every 5 iterations. Bounded runs print a final baseline-to-best summary.

Stateful artifact updates are backed by bundled helper scripts. Call them via the installed skill path, not the target repo's own `scripts/` directory. Here `<skill-root>` means the directory containing the loaded `SKILL.md`; in the common repo-local install this is `.agents/skills/codex-autoresearch`.

- `python3 <skill-root>/scripts/autoresearch_init_run.py`
- `python3 <skill-root>/scripts/autoresearch_record_iteration.py`
- `python3 <skill-root>/scripts/autoresearch_resume_check.py`
- `python3 <skill-root>/scripts/autoresearch_select_parallel_batch.py`
- `python3 <skill-root>/scripts/autoresearch_exec_state.py`
- `python3 <skill-root>/scripts/autoresearch_launch_gate.py`
- `python3 <skill-root>/scripts/autoresearch_resume_prompt.py`
- `python3 <skill-root>/scripts/autoresearch_runtime_ctl.py`
- `python3 <skill-root>/scripts/autoresearch_commit_gate.py`
- `python3 <skill-root>/scripts/autoresearch_health_check.py`
- `python3 <skill-root>/scripts/autoresearch_decision.py`
- `python3 <skill-root>/scripts/autoresearch_lessons.py`
- `python3 <skill-root>/scripts/autoresearch_supervisor_status.py`

Human-facing usage now has a single entrypoint: **`$codex-autoresearch`**.

- First interactive run: describe the goal naturally, answer the confirmation questions, then reply `go`.
- After `go`, Codex calls `autoresearch_runtime_ctl.py launch`, which atomically writes `autoresearch-launch.json` and starts the detached runtime controller.
- Before the detached runtime starts a session or relaunches one, it runs a script-level preflight: `autoresearch_health_check.py` for integrity checks and `autoresearch_commit_gate.py` for scope-aware git safety.
- Later `status`, `stop`, or `resume` requests should still go through `$codex-autoresearch`; the skill uses `autoresearch_runtime_ctl.py` internally.
- `Mode: exec` remains the advanced / CI path for fully specified non-interactive runs.

Advanced backend usage is available when you are scripting or debugging the runtime directly:

- `python3 <skill-root>/scripts/autoresearch_runtime_ctl.py status --repo <repo>`
- `python3 <skill-root>/scripts/autoresearch_runtime_ctl.py stop --repo <repo>`


---

## Safety Model

| Concern | How it is handled |
|---------|-------------------|
| Dirty worktree | Runtime preflight blocks launch or relaunch until out-of-scope changes are cleaned up or isolated |
| Health / state drift | Runtime preflight runs resume-helper-based integrity checks before every detached session and relaunch |
| Failed change | Uses the rollback strategy approved before launch: approved hard reset in an isolated experiment branch/worktree, otherwise `git revert --no-edit HEAD`; results log remains the audit trail |
| Guard failure | Up to 2 rework attempts before discarding |
| Syntax error | Auto-fix immediately, does not count as iteration |
| Runtime crash | Up to 3 fix attempts, then skip |
| Resource exhaustion | Revert, try smaller variant |
| Hanging process | Kill after timeout, revert |
| Stuck (3+ discards) | REFINE strategy; 5+ discards -> PIVOT to new approach; escalate to web search if needed |
| Ambiguity mid-loop | Apply best practices autonomously; never pause to ask the user |
| External side effects | `ship` mode requires explicit confirmation during the pre-launch wizard |
| Environment limits | Probed at startup; infeasible hypotheses filtered automatically |
| Interrupted session | Resume from last consistent state on next invocation |
| Context drift (long runs) | Protocol Fingerprint Check every 10 iterations; re-read from disk on failure; session split after 2 compactions |

---

## Project Structure

```
codex-autoresearch/
  SKILL.md                          # skill entrypoint (loaded by Codex)
  README.md                         # this file
  CONTRIBUTING.md                   # contributor guide
  LICENSE                           # MIT
  agents/
    openai.yaml                     # Codex UI metadata
  image/
    banner.png                      # project banner
  docs/
    INSTALL.md                      # installation guide
    GUIDE.md                        # operator's manual
    EXAMPLES.md                     # recipes by domain
    i18n/
      README_ZH.md                  # Chinese
      README_JA.md                  # Japanese
      README_KO.md                  # Korean
      README_FR.md                  # French
      README_DE.md                  # German
      README_ES.md                  # Spanish
      README_PT.md                  # Portuguese
      README_RU.md                  # Russian
  scripts/
    validate_skill_structure.sh     # structure validator
    run_contributor_gate.sh         # contributor acceptance gate
    autoresearch_helpers.py         # shared TSV/JSON helpers
    autoresearch_launch_gate.py     # decide fresh / resumable / needs_human before launch
    autoresearch_resume_prompt.py   # build the runtime-managed prompt from saved config
    autoresearch_runtime_ctl.py     # launch / create-launch / start / status / stop runtime controller
    autoresearch_commit_gate.py     # git/artifact/rollback gate
    autoresearch_decision.py        # structured keep/discard/crash policy helpers
    autoresearch_health_check.py    # executable health checks
    autoresearch_lessons.py         # structured lessons append/list helpers
    autoresearch_init_run.py        # initialize baseline log + state
    autoresearch_record_iteration.py # append one main iteration + update state
    autoresearch_resume_check.py    # decide full_resume / mini_wizard / fallback
    autoresearch_select_parallel_batch.py # log worker rows + batch winner
    autoresearch_exec_state.py      # resolve / cleanup exec scratch state
    autoresearch_supervisor_status.py # decide relaunch / stop / needs_human
    check_skill_invariants.py       # validate real skill-run artifacts
    run_skill_e2e.sh                # disposable Codex CLI smoke harness
  tests/
    autoresearch/                   # stdlib smoke tests for helper scripts
      base.py                       # shared script/runtime test helpers
      results/                      # results/state/exec/parallel coverage
  references/
    core-principles.md              # universal principles
    autonomous-loop-protocol.md     # loop protocol specification
    plan-workflow.md                # plan mode spec
    debug-workflow.md               # debug mode spec
    fix-workflow.md                 # fix mode spec
    security-workflow.md            # security mode spec
    ship-workflow.md                # ship mode spec
    exec-workflow.md                # CI/CD non-interactive mode spec
    interaction-wizard.md           # interactive setup contract
    structured-output-spec.md       # output format spec
    modes.md                        # mode index
    results-logging.md              # TSV format spec
    lessons-protocol.md             # cross-run learning
    pivot-protocol.md               # smart stuck recovery (PIVOT/REFINE)
    web-search-protocol.md          # web search when stuck
    environment-awareness.md        # hardware/resource detection
    parallel-experiments-protocol.md # subagent parallel testing
    session-resume-protocol.md      # resume interrupted runs
    health-check-protocol.md        # self-monitoring
    hypothesis-perspectives.md      # multi-lens hypothesis reasoning
```

---

## FAQ

**How do I pick a metric?** Use `Mode: plan`. It analyzes your codebase and suggests one.

**Works with any language?** Yes. The protocol is language-agnostic. Only the verify command is domain-specific.

**How do I stop it?** Ask `$codex-autoresearch` to stop the current run, or call `python3 <skill-root>/scripts/autoresearch_runtime_ctl.py stop --repo <repo>` if you are automating the backend directly. `Iterations: N` and stop conditions still work too.

**Does security mode touch my code?** No. Read-only analysis. Tell Codex to "also fix critical findings" during setup to opt into remediation.

**How many iterations?** Depends on the task. 5 for targeted fixes, 10-20 for exploration, unlimited for overnight runs.

**Does it learn across runs?** Yes. Lessons are extracted after each kept iteration, after each pivot, and at runtime completion when no recent lesson exists. The lessons file persists across sessions and is consulted at the start of the next run.

**Can it resume after an interruption?** Yes, for managed runs that already have `autoresearch-launch.json`, `research-results.tsv`, and `autoresearch-state.json`. If the confirmed launch state is missing, start a new run through the normal launch flow.

**Can it search the web?** Yes, when stuck after multiple strategy pivots. Web search results are treated as hypotheses and verified mechanically.

**How do I use it in CI?** Use `Mode: exec` or `codex exec`. Configure Codex CLI authentication first; API key auth is preferred for CI/programmatic use. All config is provided upfront, output is JSON, and exit codes indicate success/failure.

**Can it test multiple ideas at once?** Yes. Enable parallel experiments during setup. It uses git worktrees to test up to 3 hypotheses simultaneously.

---

## Acknowledgments

This project builds on ideas from [Karpathy's autoresearch](https://github.com/karpathy/autoresearch). The Codex skills platform is by [OpenAI](https://openai.com).

---

## Star History

<a href="https://www.star-history.com/?repos=leo-lilinxiao%2Fcodex-autoresearch&type=timeline&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/image?repos=leo-lilinxiao/codex-autoresearch&type=timeline&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/image?repos=leo-lilinxiao/codex-autoresearch&type=timeline&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/image?repos=leo-lilinxiao/codex-autoresearch&type=timeline&legend=top-left" />
 </picture>
</a>

---

## License

MIT -- see [LICENSE](LICENSE).
