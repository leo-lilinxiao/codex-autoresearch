<div align="center">

# Codex Autoresearch

Autonomous iteration protocol for [Codex](https://openai.com/codex). Define a goal, a metric, and a verify command -- Codex handles the rest.

[![Codex Skill](https://img.shields.io/badge/Codex-Skill-blue?logo=openai&logoColor=white)](https://developers.openai.com/codex/skills)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

[Architecture](#architecture) . [30-Second Start](#30-second-start) . [Modes](#modes) . [Configuration](#configuration) . [Guide](GUIDE.md) . [Recipes](EXAMPLES.md)

</div>

---

## What It Does

A Codex skill that runs a modify-verify-decide loop on your codebase. Each iteration makes one atomic change, verifies it against a mechanical metric, and keeps or discards the result. Progress accumulates in git; failures auto-revert. Works with any language, any framework, any measurable target.

Inspired by [Karpathy's autoresearch](https://github.com/karpathy/autoresearch) principles, generalized beyond ML.

### Why This Exists

Karpathy's autoresearch proved that a simple loop -- modify, verify, keep or discard, repeat -- can push ML training from baseline to new highs overnight. codex-autoresearch generalizes that loop to everything in software engineering that has a number. Test coverage, type errors, performance latency, lint warnings -- if there is a metric, it can iterate autonomously.

---

## Architecture

```
                    +------------------+
                    |   Read Context   |
                    +--------+---------+
                             |
                    +--------v---------+
                    | Establish Baseline|  <-- iteration #0
                    +--------+---------+
                             |
              +--------------v--------------+
              |                             |
              |    +-------------------+    |
              |    | Choose Hypothesis |    |
              |    +--------+----------+    |
              |             |               |
              |    +--------v----------+    |
              |    | Make ONE Change   |    |
              |    +--------+----------+    |
              |             |               |
              |    +--------v----------+    |
              |    | git commit        |    |
              |    +--------+----------+    |
              |             |               |
              |    +--------v----------+    |
              |    | Run Verify        |    |
              |    +--------+----------+    |
              |             |               |
              |         improved?           |
              |        /         \          |
              |      yes          no        |
              |      /              \        |
              | +---v----+    +-----v----+  |
              | |  KEEP  |    | REVERT   |  |
              | +---+----+    +-----+----+  |
              |      \            /          |
              |    +--v----------v--+       |
              |    |   Log Result   |       |
              |    +-------+--------+       |
              |            |                |
              +------------+ (repeat)       |
              |                             |
              +-----------------------------+
```

The loop runs until interrupted (unbounded) or for exactly N iterations (bounded via `Iterations: N`).

**In pseudocode:**

```
LOOP (forever or N times):
  1. Review current state + git history + results log
  2. Pick ONE hypothesis (based on what worked, what failed, what's untried)
  3. Make ONE atomic change
  4. git commit (before verification)
  5. Run mechanical verification
  6. Improved -> keep. Worse -> git reset. Crashed -> fix or skip.
  7. Log the result
  8. Repeat. Never stop. Never ask.
```

---

## 30-Second Start

**1. Install:**

Clone and copy into your project:
```bash
git clone https://github.com/leo-lilinxiao/codex-autoresearch.git
cp -r codex-autoresearch your-project/.agents/skills/codex-autoresearch
```

Or use the skill installer in Codex:
```text
$skill-installer install https://github.com/leo-lilinxiao/codex-autoresearch
```

**2. Open Codex in your project and run:**

Just tell Codex what you want:

```text
$codex-autoresearch
I want to get rid of all the `any` types in my TypeScript code
```

Codex scans your repo, then **always** asks to confirm before starting -- even if the goal seems clear:

```
Codex: I found 47 `any` occurrences across src/**/*.ts.

       Confirmed:
       - Target: eliminate `any` types in src/**/*.ts
       - Metric: `any` count (current: 47), direction: lower
       - Verify: grep + tsc --noEmit as guard

       Need to confirm:
       - Run until all gone, or cap at N iterations?
       - Any other safety checks beyond tsc?

       Next step: reply "go" to start, or tell me what to change.

You:   Go, run overnight.

Codex: Starting -- baseline: 47. I'll keep going until you stop me.
```

Each improvement stacks. Each failure reverts. Everything is logged.

For power users, structured key-value configuration is also supported -- see [GUIDE.md](GUIDE.md).

See [INSTALL.md](INSTALL.md) for symlink and development install options.

---

## Modes

Six modes, one invocation pattern: `$codex-autoresearch` followed by a sentence describing what you want. Codex auto-detects the mode and guides you through a short conversation to fill in the details.

| Mode | When to use | Stops when |
|------|-------------|------------|
| `loop` | You have a measurable target to optimize | Interrupted or N iterations |
| `plan` | You have a goal but not the config | Config block is generated |
| `debug` | You need root-cause analysis with evidence | All hypotheses tested or N iterations |
| `fix` | Something is broken and needs repair | Error count reaches zero |
| `security` | You need a structured vulnerability audit | All attack surfaces covered or N iterations |
| `ship` | You need gated release verification | All checklist items pass |

**Mode selection shortcut:**

```
"I want to improve X"           -->  loop  (or plan if unsure about metric)
"Something is broken"           -->  fix   (or debug if cause is unknown)
"Is this code secure?"          -->  security
"Ship it"                       -->  ship
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
| Release with confidence | `ship` | `--auto` or `--dry-run` |

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

8-phase gated release process. Auto-detects ship type (PR, deployment, release).

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

See [GUIDE.md](GUIDE.md) for flags and advanced options for each mode.

---

## Mode Chaining

Modes can be composed sequentially:

```
plan  -->  loop              # figure out config, then execute
debug -->  fix --from-debug  # find bugs, then repair them
security --fix               # audit and remediate in one pass
```

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
| Stuck (5+ discards) | Re-read all context, review patterns, try bolder changes |
| Ambiguity mid-loop | Apply best practices autonomously; never pause to ask the user |
| External side effects | `ship` mode requires explicit confirmation |

---

## Project Structure

```
codex-autoresearch/
  SKILL.md                          # skill entrypoint (loaded by Codex)
  README.md                         # this file
  README_ZH.md                      # Chinese documentation
  INSTALL.md                        # installation guide
  GUIDE.md                          # operator's manual
  EXAMPLES.md                       # recipes by domain
  CONTRIBUTING.md                   # contributor guide
  LICENSE                           # MIT
  agents/
    openai.yaml                     # Codex UI metadata
  scripts/
    validate_skill_structure.sh     # structure validator
  references/
    autonomous-loop-protocol.md     # loop protocol specification
    core-principles.md              # universal principles
    plan-workflow.md                # plan mode spec
    debug-workflow.md               # debug mode spec
    fix-workflow.md                 # fix mode spec
    security-workflow.md            # security mode spec
    ship-workflow.md                # ship mode spec
    interaction-wizard.md           # interactive setup contract
    structured-output-spec.md       # output format spec
    modes.md                        # mode index
    results-logging.md              # TSV format spec
```

---

## FAQ

**How do I pick a metric?** Use `Mode: plan`. It analyzes your codebase and suggests one.

**Works with any language?** Yes. The protocol is language-agnostic. Only the verify command is domain-specific.

**How do I stop it?** Interrupt Codex, or set `Iterations: N`. Git state is always consistent because commits happen before verification.

**Does security mode touch my code?** No. Read-only analysis. Use `--fix` to opt into remediation.

**How many iterations?** Depends on the task. 5 for targeted fixes, 10-20 for exploration, unlimited for overnight runs.

---

## Acknowledgments

This project builds on ideas from [Karpathy's autoresearch](https://github.com/karpathy/autoresearch). The Codex skills platform is by [OpenAI](https://openai.com).

---

## License

MIT -- see [LICENSE](LICENSE).
