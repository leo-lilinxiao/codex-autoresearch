# Ship Workflow

Universal shipment workflow for code, releases, deployments, content, campaigns, research artifacts, and similar outputs.

**Two-phase boundary:** All clarifying questions and ship confirmations happen before launch. External ship actions (deploy, publish, release) must be explicitly approved during the pre-launch wizard. If not approved before launch, skip the Ship phase and log as blocker.

## Purpose

Convert "ready enough" into a gated ship process:

1. identify,
2. inventory,
3. checklist,
4. prepare,
5. dry-run,
6. ship,
7. verify,
8. log.

## Trigger

- `$codex-autoresearch Mode: ship`
- "ship it"
- "deploy this"
- "publish this"
- "release this"

## Flags

| Flag | Purpose |
|------|---------|
| `--type <type>` | Override auto-detected shipment type |
| `--target "<path or destination>"` | Specify target artifact or destination |
| `--dry-run` | Stop after simulation |
| `--auto` | Auto-approve the dry-run when no blockers remain |
| `--force` | Ignore non-critical checklist items |
| `--rollback` | Undo the last reversible ship action |
| `--monitor N` | Monitor for N minutes after ship |
| `--checklist-only` | Generate and evaluate the checklist only |

## Wizard

If type or target is missing, collect:

- shipment type,
- target artifact or destination,
- run mode,
- monitoring duration.

## Generic Launch Contract

Ship mode follows the same interactive launch contract as the other iterating modes. Before `go`, confirm these generic fields plus the run-mode choice (`foreground` or `background`). Background still hands off through a launch manifest and detached runtime; foreground stays in the current Codex session.

- `Goal` -- ship the selected target safely,
- `Scope` -- files, configs, scripts, and artifacts that may be edited to satisfy the checklist,
- `Metric` -- checklist readiness score (or another mechanical pass-count score),
- `Direction` -- `higher`,
- `Verify` -- command or scripted evaluation that emits the current readiness score and fails non-zero when the check crashes,
- `Guard` (optional) -- smoke check that must always stay green while preparing the shipment.

The user should not see those raw field names, but the runtime still depends on them being confirmed before launch.

## Shipment Types

- code-pr
- code-release
- deployment
- content
- marketing-email
- marketing-campaign
- sales
- research
- design

## Phases

### Phase 1: Identify

Infer shipment type from repo state and user request.

### Phase 2: Inventory

Assess current readiness and missing pieces.

### Phase 3: Checklist

Generate mechanically verifiable gates.

Convert the checklist into a numeric readiness score so the generic loop can compare iterations. Preferred forms:

- percentage of required gates currently passing, or
- count of required gates currently passing.

Examples:

- tests passing,
- lint clean,
- links checked,
- metadata present,
- changelog updated,
- rollback plan present.

### Phase 4: Prepare

If checklist items fail, iterate on the highest-value failing item first.

This phase uses the generic improve-verify-decide loop:

- edit only within the shipment scope,
- re-run the ship verify command,
- keep or discard based on whether the readiness score improved,
- extract lessons and log the result like any other interactive iterating mode.

### Phase 5: Dry-Run

Simulate the ship action without external side effects.

### Phase 6: Ship

Execute the actual delivery.

Rule:

- never perform this phase unless the user explicitly confirmed ship actions during the pre-launch wizard phase. If ship actions were not confirmed before launch, skip this phase and log as blocker. This is consistent with the two-phase boundary: all confirmations happen before launch.

### Phase 7: Verify

Confirm the ship landed and the target is healthy.

### Phase 8: Log

Append a shipment record.

In addition to the ship-specific output directory, ship mode still writes the generic iterating-run artifacts:

- `autoresearch-results/results.tsv`
- `autoresearch-results/lessons.md`
- `autoresearch-results/state.json`

## Output Directory

```text
ship/{YYMMDD}-{HHMM}-{slug}/
  checklist.md
  ship-log.tsv
  summary.md
```

## Ship Log Schema

```tsv
timestamp	type	target	checklist_score	dry_run	shipped	verified	duration	notes
```

## Rollback

If `--rollback` is requested or verification fails:

- choose the domain-appropriate rollback,
- log whether the rollback succeeded,
- flag non-reversible ship types clearly before execution.
