# Specialized Modes

This file is the mode index. Each mode below has a full workflow reference.

Official Codex activation is `$codex-autoresearch` with `Mode: <name>`, or implicit skill matching.

| Mode | Invocation | Reference | Core Output |
|------|------------|-----------|-------------|
| `loop` | `Mode: loop` | `loop-workflow.md` | iterative metric-driven improvement |
| `plan` | `Mode: plan` | `plan-workflow.md` | launch-ready config |
| `debug` | `Mode: debug` | `debug-workflow.md` | findings, eliminated hypotheses, next actions |
| `fix` | `Mode: fix` | `fix-workflow.md` | reduced error count, blocked items, fix log |
| `security` | `Mode: security` | `security-workflow.md` | ranked findings, coverage, recommendations |
| `ship` | `Mode: ship` | `ship-workflow.md` | checklist, dry-run, ship verification |
| `exec` | `Mode: exec` | `exec-workflow.md` | JSON iteration lines, exit codes for CI/CD |

## Shared Expectations

All specialized modes must:

1. load `core-principles.md`,
2. follow `structured-output-spec.md`,
3. load `runtime-hard-invariants.md` for active execution,
4. use `interaction-wizard.md` for every new interactive launch (except `exec` mode),
5. load the selected mode workflow reference,
6. load detailed references such as `autonomous-loop-protocol.md`, `results-logging.md`, `lessons-protocol.md`, `pivot-protocol.md`, `health-check-protocol.md`, `parallel-experiments-protocol.md`, and `web-search-protocol.md` only when their behavior is actually needed,
7. keep all decisions mechanical where possible,
8. write their documented logs and output files (for foreground iterating modes this means `autoresearch-results/results.tsv` and `autoresearch-results/state.json` as the core persistent artifacts; lessons remain helper-derived secondary output, and exec persists the TSV plus inactive canonical context metadata while cleaning up scratch JSON state before exit),
9. preserve the official skill entrypoint in `SKILL.md`.
