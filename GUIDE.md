# Operator's Manual

This document covers everything you need to run codex-autoresearch effectively -- from installation through advanced multi-mode workflows.

---

## Getting Started

### Install

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

### Your first run

Just tell Codex what you want:

```text
$codex-autoresearch
Eliminate all Go vet violations in this repo
```

Codex scans the repo, proposes a metric and verify command, and asks you to confirm before starting. You can also provide structured config if you prefer:

```text
$codex-autoresearch
Goal: Eliminate all Go vet violations
Scope: **/*.go
Metric: go vet violation count
Direction: lower
Verify: go vet ./... 2>&1 | wc -l
Guard: go test ./...
```

If you are unsure about your goal, use plan mode:

```text
$codex-autoresearch
I want to make our API faster but I don't know where to start
```

### Bounded vs unbounded

By default, the loop runs until interrupted. Add `Iterations: N` to cap it:

```text
$codex-autoresearch
Goal: Cut Webpack build warnings to zero
Scope: src/**/*.ts, src/**/*.tsx, webpack.config.*
Metric: warning count
Direction: lower
Verify: npm run build 2>&1 | grep -c "WARNING"
Guard: npm test
Iterations: 20
```

| Scenario | Recommendation |
|----------|---------------|
| Overnight improvement session | Unlimited (default) |
| Quick experiment | `Iterations: 10` |
| Targeted fix with known scope | `Iterations: 5` |
| CI/CD pipeline | Set N based on time budget |

---

## Understanding the Protocol

### Lifecycle of one iteration

```
  Hypothesis  -->  Modify  -->  Commit  -->  Verify  -->  Guard
                                                |            |
                                             improved?    passed?
                                              |    |      |    |
                                             yes   no    yes   no
                                              |    |      |    |
                                            KEEP  REVERT  ok  rework (2x)
                                              |               |
                                              +--- Log -------+
```

1. **Hypothesis** -- pick one focused change based on git history and past results
2. **Modify** -- edit files within the declared scope
3. **Commit** -- `git commit` before running verification
4. **Verify** -- run the verify command, extract the metric
5. **Guard** -- if a guard command is set, run it to check for regressions
6. **Decide** -- keep (metric improved + guard passed) or revert
7. **Log** -- append result to TSV log

### The two gates: Verify and Guard

| Gate | Question it answers | Fails means |
|------|---------------------|-------------|
| Verify | Did the target metric improve? | Revert the change |
| Guard | Did anything else break? | Rework the change (up to 2 attempts), then revert |

Use guard when optimizing a metric that could introduce regressions:

```text
Verify: pytest --cov=src --cov-report=term 2>&1 | grep TOTAL | awk '{print $NF}'   # track coverage
Guard: npx tsc --noEmit                                                              # don't break types
```

### Required vs optional fields

**Required** (for `loop` mode):

| Field | What it is |
|-------|------------|
| `Goal` | Plain-language description of the target |
| `Scope` | File globs that Codex may modify |
| `Metric` | The number being tracked |
| `Direction` | `higher` or `lower` |
| `Verify` | Shell command that outputs the metric |

**Optional:**

| Field | Default | What it does |
|-------|---------|--------------|
| `Guard` | none | Regression-prevention command |
| `Iterations` | unlimited | Stop after N iterations |
| `Run tag` | auto-generated | Label for this run |
| `Stop condition` | none | Custom early-stop rule |

If required fields are missing, an interactive wizard scans the repo and always confirms with you before starting (up to 5 rounds). You never need to know the field names.

### Workspace safety

The loop commits and reverts repeatedly. This requires a clean workspace.

If unrelated uncommitted changes exist:
- The loop will not start
- Use `plan` mode instead (read-only)
- Or isolate the work in a clean branch / worktree

### Output artifacts

| Mode | Artifact |
|------|----------|
| `loop` | `research-results.tsv` |
| `plan` | Config block printed inline |
| `debug` | `debug/{YYMMDD}-{HHMM}-{slug}/` |
| `fix` | `fix/{YYMMDD}-{HHMM}-{slug}/` |
| `security` | `security/{YYMMDD}-{HHMM}-{slug}/` |
| `ship` | `ship/{YYMMDD}-{HHMM}-{slug}/` |

---

## Mode Deep Dives

### loop

The default mode. Iterates toward any measurable target.

```text
$codex-autoresearch
Goal: Cut CI pipeline time from 14 minutes to under 6 minutes
Scope: .github/workflows/*.yml, jest.config.*, src/**/*.test.ts
Metric: CI duration in seconds
Direction: lower
Verify: time npm test 2>&1 | grep "real"
Guard: npm test
Iterations: 15
```

**What happens:** Codex reads all in-scope files, measures the baseline (iteration #0), then begins the loop. Each iteration picks one hypothesis, makes one change, verifies, and keeps or reverts.

Reference: `references/autonomous-loop-protocol.md`

### plan

Converts a vague goal into a validated, launch-ready configuration.

```text
$codex-autoresearch
Mode: plan
Goal: optimize database query performance
```

**Steps:**

1. Scans the repo to understand structure and stack
2. Proposes a scope (which files to modify)
3. Proposes a metric and direction
4. Proposes a verify command
5. Dry-runs the verify command to confirm it works
6. Outputs a ready-to-paste config block

Every gate is mechanical -- scope must resolve to real files, verify must produce a number.

Reference: `references/plan-workflow.md`

### debug

Evidence-driven bug hunting using the scientific method.

```text
$codex-autoresearch
Mode: debug
Scope: src/api/**/*.ts, src/middleware/**/*.ts
Symptom: intermittent 503 errors under concurrent requests
Iterations: 12
```

**What it produces:**

- Confirmed findings with file:line evidence
- Disproven hypotheses (logged as equally valuable)
- Reproducible steps for each finding
- Recommended next actions

**Flags:**

| Flag | Purpose |
|------|---------|
| `--fix` | Auto-switch to fix mode after investigation |
| `--severity <level>` | Minimum severity to report |

Reference: `references/debug-workflow.md`

### fix

Iteratively repairs errors until the count reaches zero.

```text
$codex-autoresearch
Mode: fix
Target: pytest -q
Guard: ruff check .
Scope: tests/**/*.py, src/**/*.py
```

**What happens:** Auto-detects broken targets (tests, types, lint, build). Prioritizes blockers. Fixes one thing per iteration. Commits, verifies error count decreased, guard-checks, keeps or reverts. Stops automatically at zero errors.

**Flags:**

| Flag | Purpose |
|------|---------|
| `--target <cmd>` | Explicit verify command |
| `--guard <cmd>` | Safety command |
| `--category <type>` | Only fix one category (test, type, lint, build) |
| `--from-debug` | Import findings from latest debug session |

Reference: `references/fix-workflow.md`

### security

Read-only structured audit using STRIDE threat modeling, OWASP Top 10, and red-team analysis.

```text
$codex-autoresearch
Mode: security
Scope: src/api/**, src/middleware/**, src/validators/**
Focus: SQL injection, XSS, and input sanitization
Iterations: 10
```

Every finding requires code evidence (file:line + exploitation scenario). No theoretical findings accepted.

**Flags:**

| Flag | Purpose |
|------|---------|
| `--diff` | Only audit files changed since last audit |
| `--fix` | Auto-remediate confirmed Critical/High findings |
| `--fail-on <severity>` | Non-zero exit for CI/CD gating |

Reference: `references/security-workflow.md`

### ship

8-phase gated release process: Identify -> Inventory -> Checklist -> Prepare -> Dry-run -> Ship -> Verify -> Log.

```text
$codex-autoresearch
Mode: ship
--auto
```

Auto-detects what you are shipping (PR, deployment, release, content) and generates a domain-specific checklist. No external actions without explicit confirmation.

**Flags:**

| Flag | Purpose |
|------|---------|
| `--dry-run` | Validate without shipping |
| `--auto` | Auto-approve if checklist passes |
| `--force` | Skip non-critical items |
| `--rollback` | Undo last ship action |
| `--monitor N` | Post-ship monitoring for N minutes |
| `--type <type>` | Override auto-detection |
| `--checklist-only` | Just check readiness |

Reference: `references/ship-workflow.md`

---

## Cross-Domain Recipes

The protocol is domain-agnostic. Only the metric and verify command change.

| Domain | Metric | Verify | Guard |
|--------|--------|--------|-------|
| TypeScript | type error count | `tsc --noEmit 2>&1 \| tail -1` | `npm test` |
| Python | pytest failures | `pytest -q` | `ruff check .` |
| Go | test failures | `go test ./...` | `go vet ./...` |
| Rust | test failures | `cargo test` | `cargo clippy` |
| Coverage | coverage % | `pytest --cov=src --cov-report=term 2>&1 \| grep TOTAL \| awk '{print $NF}'` | `npx tsc --noEmit` |
| Frontend | Lighthouse score | `npx lighthouse --quiet` | `npm test` |
| Performance | p95 latency (ms) | `npm run bench \| grep p95` | `npm test` |
| ML training | val_loss | `python train.py` | -- |

---

## Multi-Mode Workflows

### Diagnose then repair

```
debug (Iterations: 15)  -->  fix --from-debug (Iterations: 30)
```

Debug mode finds all bugs with evidence. Fix mode imports those findings and repairs them one by one.

### Plan then execute

```
plan (Goal: "reduce API p95 latency")  -->  loop (paste generated config)
```

Plan mode outputs a complete config block. Copy it, run it.

### Audit then remediate

```
security --fix (Iterations: 15)
```

Single invocation: audit first, then auto-fix Critical/High findings.

---

## Operating Tips

### The skill does not appear

- Confirm the folder is at `.agents/skills/codex-autoresearch` or `~/.agents/skills/codex-autoresearch`
- Confirm `SKILL.md` exists at the root of that folder
- Restart Codex after installation changes

### The wrong skill triggers

- Use explicit invocation: `$codex-autoresearch`
- Avoid vague prompts without measurable targets

### The wizard asks too many questions

- Provide more fields inline to skip wizard steps
- Use `Mode: <name>` to skip mode classification
- For loop mode, provide all 5 required fields

### The loop refuses to commit

- Check for unrelated uncommitted changes
- Isolate work in a clean branch or worktree
- Use `plan` mode first if the workspace is not clean

### Can I use this without git?

Plan mode and security mode (read-only) work without git. The iterative loop requires git for its commit/revert safety model.
