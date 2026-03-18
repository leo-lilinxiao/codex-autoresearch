# Structured Output Specification

Every `codex-autoresearch` mode must produce predictable human-readable output and, where defined, predictable artifact files.

## Common Response Sections

Before work starts:

1. `Setup`
2. `Config`
3. `Baseline`

During work:

1. `Iteration`
2. `Metric`
3. `Decision`

At completion:

1. `Summary`
2. `Artifacts`
3. `Next Actions`

## Common Iteration Line

Use this shape during loops:

```text
[iteration N] hypothesis -> metric result -> keep/discard/crash
```

## Mode Output Templates

### loop

Required completion summary:

- goal
- baseline metric
- best metric
- keep/discard/crash counts
- artifact path

Artifact:

- `research-results.tsv`

### plan

Required reply sections:

- Goal
- Scope
- Metric
- Direction
- Verify
- Guard
- Launch Options

No output directory required unless the user asks to save artifacts.

### debug

Output directory:

```text
debug/{YYMMDD}-{HHMM}-{slug}/
  findings.md
  eliminated.md
  debug-results.tsv
  summary.md
```

`summary.md` must include:

- issue statement
- scope
- findings by severity
- disproven hypotheses count
- recommended next action

### fix

Output directory:

```text
fix/{YYMMDD}-{HHMM}-{slug}/
  fix-results.tsv
  blocked.md
  summary.md
```

`summary.md` must include:

- baseline error count
- final error count
- categories fixed
- blocked items
- guard status

### security

Output directory:

```text
security/{YYMMDD}-{HHMM}-{slug}/
  overview.md
  threat-model.md
  attack-surface-map.md
  findings.md
  coverage.md
  dependency-audit.md
  recommendations.md
  security-audit-results.tsv
```

### ship

Output directory:

```text
ship/{YYMMDD}-{HHMM}-{slug}/
  checklist.md
  ship-log.tsv
  summary.md
```

## Logging Rules

- TSV headers must be written exactly once.
- Timestamps should use UTC.
- File paths should be repo-relative inside artifacts.
- Final summaries should reference every artifact created.
