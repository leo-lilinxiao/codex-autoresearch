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
  <a href="#modes">Modes</a> ·
  <a href="#configuration">Configuration</a> ·
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

You:   Go, run overnight.

Codex: Starting -- baseline: 47. Iterating until interrupted.
```

Each improvement stacks. Each failure reverts. Everything is logged.

See [INSTALL.md](docs/INSTALL.md) for more install options. See [GUIDE.md](docs/GUIDE.md) for full operator's manual.

---

## What It Does

A Codex skill that runs a modify-verify-decide loop on your codebase. Each iteration makes one atomic change, verifies it against a mechanical metric, and keeps or discards the result. Progress accumulates in git; failures auto-revert. Works with any language, any framework, any measurable target.

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
  6. Improved -> keep (extract lesson). Worse -> git reset. Crashed -> fix or skip.
  7. Log the result
  8. Health check (disk, git, verify health)
  9. If 3+ discards -> REFINE; 5+ -> PIVOT; 2 PIVOTs -> web search
  10. Repeat. Never stop. Never ask.
```

---

## Modes

Seven modes, one invocation pattern: `$codex-autoresearch` followed by a sentence describing what you want. Codex auto-detects the mode and guides you through a short conversation to fill in the details.

| Mode | When to use | Stops when |
|------|-------------|------------|
| `loop` | You have a measurable target to optimize | Interrupted or N iterations |
| `plan` | You have a goal but not the config | Config block is generated |
| `debug` | You need root-cause analysis with evidence | All hypotheses tested or N iterations |
| `fix` | Something is broken and needs repair | Error count reaches zero |
| `security` | You need a structured vulnerability audit | All attack surfaces covered or N iterations |
| `ship` | You need gated release verification | All checklist items pass |
| `exec` | CI/CD pipeline, no human available | N iterations (always bounded), JSON output |

**Mode selection shortcut:**

```
"I want to improve X"           -->  loop  (or plan if unsure about metric)
"Something is broken"           -->  fix   (or debug if cause is unknown)
"Is this code secure?"          -->  security
"Ship it"                       -->  ship
codex exec --skill ...          -->  exec  (CI/CD, no wizard)
```

---

## Configuration

### Required fields (for `loop` mode)

| Field | Type | Example |
|-------|------|---------|
| `Goal` | What to achieve | `Reduce type errors to zero` |
| `Scope` | File globs to modify | `src/**/*.ts` |
| `Metric` | What number to track | `type error count` |
| `Direction` | `higher` or `lower` | `lower` |
| `Verify` | Shell command producing the metric | `tsc --noEmit 2>&1 \| wc -l` |

### Optional fields

| Field | Default | Purpose |
|-------|---------|---------|
| `Guard` | none | Safety command that must always pass (regression prevention) |
| `Iterations` | unlimited | Cap at N iterations |
| `Run tag` | auto | Label for this run |
| `Stop condition` | none | Custom early-stop rule |

Missing required fields trigger an interactive wizard that scans your repo and always confirms with you before starting (up to 5 rounds). You never need to know the field names.

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

## Quick Decision Guide

| You want to... | Mode | Key config |
|----------------|------|------------|
| Push a number in one direction overnight | `loop` | Goal + Metric + Verify |
| Figure out which metric to track | `plan` | Just a Goal |
| Find why something is broken | `debug` | Scope + Symptom |
| Make failing tests/types/lint pass | `fix` | Target command |
| Audit code for vulnerabilities | `security` | Scope + Focus |
| Release with confidence | `ship` | Say "ship it" or "dry run first" |
| Run in CI/CD without interaction | `exec` | All fields upfront + Iterations |

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

Every run extracts structured lessons -- what worked, what failed, and why. Lessons are persisted in `autoresearch-lessons.md` (uncommitted, like the results log) and consulted at the start of future runs to bias hypothesis generation toward proven strategies and away from known dead ends.

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

If Codex detects a prior interrupted run (results log, lessons file, experiment commits), it can resume from the last consistent state instead of starting over:

- **Consistent state:** resume immediately, skip wizard
- **Partially consistent:** mini-wizard (1 round) to re-confirm
- **Inconsistent or different goal:** fresh start (old log renamed)

See `references/session-resume-protocol.md`.

---

## CI/CD Mode (exec)

Non-interactive mode for automation pipelines. All config is provided upfront -- no wizard, always bounded, JSON output.

```yaml
# GitHub Actions example
- name: Autoresearch optimization
  run: codex exec --skill codex-autoresearch
         --goal "Reduce type errors" --scope "src/**/*.ts"
         --metric "type error count" --direction lower
         --verify "tsc --noEmit 2>&1 | grep -c error"
         --iterations 20
```

Exit codes: 0 = improved, 1 = no improvement, 2 = hard blocker.

See `references/exec-workflow.md`.

---

## Results Log

Every iteration is recorded in TSV format (`research-results.tsv`):

```
iteration  commit   metric  delta   status    description
0          a1b2c3d  47      0       baseline  initial any count
1          b2c3d4e  41      -6      keep      replace any in auth module with strict types
2          -        49      +8      discard   generic wrapper introduced new anys
3          c3d4e5f  38      -3      keep      type-narrow API response handlers
```

Progress summaries print every 5 iterations. Bounded runs print a final baseline-to-best summary.

---

## Safety Model

| Concern | How it is handled |
|---------|-------------------|
| Dirty worktree | Loop refuses to start; suggests `plan` mode or clean branch |
| Failed change | `git reset --hard HEAD~1` keeps history clean; results log is the audit trail |
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

**How do I stop it?** Interrupt Codex, or set `Iterations: N`. Git state is always consistent because commits happen before verification.

**Does security mode touch my code?** No. Read-only analysis. Tell Codex to "also fix critical findings" during setup to opt into remediation.

**How many iterations?** Depends on the task. 5 for targeted fixes, 10-20 for exploration, unlimited for overnight runs.

**Does it learn across runs?** Yes. Lessons are extracted after each run and consulted at the start of the next one. The lessons file persists across sessions.

**Can it resume after an interruption?** Yes. On the next invocation, it detects the prior run and resumes from the last consistent state.

**Can it search the web?** Yes, when stuck after multiple strategy pivots. Web search results are treated as hypotheses and verified mechanically.

**How do I use it in CI?** Use `Mode: exec` or `codex exec`. All config is provided upfront, output is JSON, and exit codes indicate success/failure.

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
