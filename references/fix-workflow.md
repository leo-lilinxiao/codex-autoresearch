# Fix Workflow

Iterative repair loop for reducing tests, type errors, lint failures, build failures, or bug findings to zero.

**Two-phase boundary:** All clarifying questions happen before launch. Once the user says "go", this workflow is fully autonomous -- never pause to ask the user anything. If you encounter ambiguity, apply best practices and keep going.

## Purpose

Use this mode when the user wants the system repaired, not just diagnosed.

## Trigger

- `$codex-autoresearch Mode: fix`
- "fix all errors"
- "make tests pass"
- "fix the build"
- "clean up the failures"

## Flags

| Flag | Purpose |
|------|---------|
| `--target "<command>"` | Explicit verify command |
| `--guard "<command>"` | Safety command that must always pass |
| `--scope "<glob>"` | Limit editable files |
| `--category test|type|lint|build|bug` | Only fix one category |
| `--skip-lint` | Ignore lint-only issues |
| `--from-debug` | Import findings from latest debug session |
| `--iterations N` | Bound the repair loop |

## Wizard

If `Target` or `Scope` is missing, collect:

- what to fix,
- scope,
- guard command (optional),
- launch choice.

## Phases

### Phase 1: Detect

Auto-detect failure categories:

- build
- test
- type
- lint
- bug findings from debug mode

### Phase 2: Prioritize

Priority order:

1. build
2. critical and high bugs
3. type errors
4. test failures
5. medium and low bugs
6. lint

### Phase 3: Fix One Thing

Rules:

- one atomic fix per iteration,
- fix the implementation rather than muting the signal,
- do not hide issues with ignore directives unless the user explicitly authorizes that strategy.

### Phase 4: Commit

Commit before verification when the workspace is isolated.

### Phase 5: Verify

Re-run the target command and compare the error count.

### Phase 6: Guard

Run the guard if configured.

### Phase 7: Decide

- improved + guard passed -> keep
- improved + guard failed -> rework (up to 2 attempts), then discard. Rollback follows the generic loop: prefer `git reset --hard HEAD~1`, fall back to `git revert --no-edit HEAD`.
- unchanged -> discard
- worse -> discard immediately
- crash -> recover or discard

### Phase 8: Log

Append to:

```tsv
iteration	category	target	delta	guard	status	description
```

## Output Directory

```text
fix/{YYMMDD}-{HHMM}-{slug}/
  fix-results.tsv
  blocked.md
  summary.md
```

`blocked.md` must list items that could not be fixed safely within the configured attempts.

## Web Search for Unfamiliar Errors

When an error during repair is caused by an unfamiliar framework behavior or external library issue that cannot be resolved from the codebase alone, web search may be triggered per `references/web-search-protocol.md`. Search results are treated as repair hypotheses and verified mechanically.

## Completion

Stop when:

- error count reaches zero,
- iteration limit is reached,
- or only blocked items remain.
