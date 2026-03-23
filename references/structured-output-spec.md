# Structured Output Specification

Every `codex-autoresearch` mode must produce predictable output and, where defined, predictable artifact files. Interactive and user-facing modes use human-readable sections; `exec` uses JSON-only machine-readable output.

## Status Values

All modes share these status values (see `references/results-logging.md` for full schema):

| Status | Meaning |
|--------|---------|
| `baseline` | Initial measurement before any changes |
| `keep` | Change improved the metric and passed guard |
| `discard` | Change did not improve or failed guard |
| `crash` | Verification crashed or produced an error |
| `no-op` | No actual diff was produced |
| `blocked` | Hard blocker encountered, loop stopped |
| `refine` | Strategy adjustment within current approach |
| `pivot` | Strategy abandoned, fundamentally new approach |
| `search` | Web search performed for external knowledge |
| `drift` | Metric drifted from expected value during session resume |

## Common Response Sections

These sections apply to interactive and other user-facing modes. `exec` mode is the exception and follows the JSON contract below.

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

Extended statuses for stuck recovery and search:

```text
[iteration N] [REFINE] adjusted strategy -> metric result -> refine
[iteration N] [PIVOT] abandoned strategy X, trying Y -> metric result -> pivot
[iteration N] [SEARCH] "query" -> found approach -> metric result -> search
```

Parallel batch notation:

```text
[iteration Na] [PARALLEL worker-a] hypothesis -> metric result -> keep (SELECTED)
[iteration Nb] [PARALLEL worker-b] hypothesis -> metric result -> discard
```

## Mode Output Templates

### loop

Required completion summary:

- goal
- baseline metric
- best metric
- keep/discard/crash/refine/pivot counts
- lessons extracted (count)
- environment summary (one line)
- artifact path

Artifact:

- `research-results.tsv`
- `autoresearch-lessons.md` (if lessons were extracted)
- `autoresearch-state.json` (session state snapshot, not committed to git; see `references/session-resume-protocol.md`)

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

Ship mode also persists the generic iterating-run artifacts:

- `research-results.tsv`
- `autoresearch-lessons.md` (if lessons were extracted)
- `autoresearch-state.json`

Output directory:

```text
ship/{YYMMDD}-{HHMM}-{slug}/
  checklist.md
  ship-log.tsv
  summary.md
```

### exec

JSON output mode for CI/CD. No human-readable text.

Per-iteration line (stdout):

```json
{"iteration": 1, "commit": "abc1234", "metric": 41, "delta": -6, "guard": "pass", "status": "keep", "description": "narrowed auth types"}
```

Completion summary (stdout, last line):

```json
{"status": "completed", "baseline": 47, "best": 38, "best_iteration": 5, "total_iterations": 10, "keeps": 4, "discards": 5, "crashes": 1, "improved": true, "exit_code": 0}
```

Error output (stderr):

```json
{"error": "missing required field: Verify", "exit_code": 2}
```

Exit codes: 0 = improved, 1 = no improvement, 2 = hard blocker.

## Logging Rules

- TSV headers must be written exactly once.
- When helper-managed artifacts include timestamps (for example lessons entries or runtime/state metadata), they should use UTC.
- File paths should be repo-relative inside artifacts.
- Final summaries should reference every artifact created.
- Parallel workers use `[PARALLEL worker-{id}]` prefix.
