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
| `exec` | `Mode: exec` | `exec-workflow.md` | JSON iteration lines, exit codes for CI/CD |

## Shared Expectations

All specialized modes must:

1. load `core-principles.md`,
2. follow `structured-output-spec.md`,
3. use `interaction-wizard.md` when required fields are missing (except `exec` mode),
4. load `autonomous-loop-protocol.md` for all iterating modes (loop, debug, fix, security, exec),
5. load `lessons-protocol.md` for cross-run learning (iterating modes),
6. load `pivot-protocol.md` for stuck recovery (iterating modes),
7. load `health-check-protocol.md` for self-monitoring (iterating modes),
8. keep all decisions mechanical where possible,
9. write their documented logs and output files,
10. preserve the official skill entrypoint in `SKILL.md`.
