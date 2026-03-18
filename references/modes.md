# Specialized Modes

This file is the mode index. Each mode below has a full workflow reference.

Official Codex activation is `$codex-autoresearch` with `Mode: <name>`, or implicit skill matching.

| Mode | Invocation | Reference | Core Output |
|------|------------|-----------|-------------|
| `loop` | `Mode: loop` | `autonomous-loop-protocol.md` | iterative metric-driven improvement |
| `plan` | `Mode: plan` | `plan-workflow.md` | launch-ready config |
| `debug` | `Mode: debug` | `debug-workflow.md` | findings, eliminated hypotheses, next actions |
| `fix` | `Mode: fix` | `fix-workflow.md` | reduced error count, blocked items, fix log |
| `security` | `Mode: security` | `security-workflow.md` | ranked findings, coverage, recommendations |
| `ship` | `Mode: ship` | `ship-workflow.md` | checklist, dry-run, ship verification |

## Shared Expectations

All specialized modes must:

1. load `core-principles.md`,
2. follow `structured-output-spec.md`,
3. use `interaction-wizard.md` when required fields are missing,
4. keep all decisions mechanical where possible,
5. write their documented logs and output files,
6. preserve the official skill entrypoint in `SKILL.md`.
