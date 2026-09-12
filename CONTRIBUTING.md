# Contributing

Codex Autoresearch is intentionally small. Contributions should strengthen the single experiment loop rather than add another mode, recovery heuristic, or duplicate state layer.

Read the architecture and design rules below before changing code or protocol.

## Architecture

```text
SKILL.md
├── references/workflow.md
└── references/background.md

scripts/autoresearch.py         CLI and detached controller
scripts/autoresearch_core.py    strict schema, Git, commands, and events
scripts/autoresearch_report.py  read-only terminal, TSV, and HTML views
```

The user documentation is [README.md](README.md), [Installation](docs/INSTALL.md), [User Guide](docs/GUIDE.md), [Examples](docs/EXAMPLES.md), and synchronized translations under `docs/i18n/`.

## Sources Of Truth

- Product and runtime invariants: this document
- Model entry contract: `SKILL.md`
- Immutable run configuration: `autoresearch-results/run.json`
- Runtime state and audit: `autoresearch-results/events.jsonl`

Do not introduce a second state snapshot or reconstruct events from logs. Logs explain failures; they are not state. Generated history and reports are disposable projections of validated events.

## Design Rules

- Fail on malformed or contradictory input. Do not add fallback parsing.
- Fix the owning state transition, not one caller's symptom.
- Record full command/controller diagnostics before returning an error.
- Keep the initial `SKILL.md` below Codex's 8,000-byte selected-skill prompt limit.
- Keep references one level from `SKILL.md` and avoid duplicated rules.
- Load references when needed; keep each decision rule in one place. Preserve prior user authorization and let Codex choose hypotheses from evidence.
- Preserve one repository, one metric, one target, and one finalized experiment per iteration.
- Do not add custom Codex hooks. Foreground continuity belongs to official Goals; background continuity belongs to the controller.
- The background controller owns each worker process tree and must terminate it before stopping or failing.
- Do not add compatibility branches for unreleased schemas. A schema change must fail clearly and require an explicit fresh run.

## Validate

Documentation and structure:

```bash
bash scripts/run_contributor_gate.sh docs
```

Behavioral changes:

```bash
bash scripts/run_contributor_gate.sh skill
```

The skill gate runs strict unit tests plus deterministic foreground and background smoke tests. Real-model checks require local Codex authentication and are available separately through `scripts/run_skill_e2e.sh`.

## Pull Requests

Keep changes focused. Explain the user-visible behavior, the reason for the change, and the relevant validation.

Keep protocol and user documentation aligned with behavioral changes. Test meaningful runtime contracts and evaluate model behavior with representative requests; avoid tests that freeze prose or file counts. If architecture changes, update the Architecture, Sources Of Truth, and Design Rules sections here too.
