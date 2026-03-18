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
- run mode,
- monitoring duration.

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

Examples:

- tests passing,
- lint clean,
- links checked,
- metadata present,
- changelog updated,
- rollback plan present.

### Phase 4: Prepare

If checklist items fail, iterate on the highest-value failing item first.

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
