---
name: codex-autoresearch
description: "Run repeated, measured Git experiments toward a numeric target; keep improvements and revert failures. Use for autonomous optimization or managing an autoresearch run, not one-shot edits."
metadata:
  short-description: "Run measurable autonomous experiments"
---

# Codex Autoresearch

Improve a repository through repeated, reversible experiments:

`hypothesize -> change -> measure -> learn -> keep or revert -> repeat`

Codex chooses hypotheses and makes code changes. The control script owns measurement, commits, rollback, and the event history.

## Respond To The Request

Resolve `<control>` to this skill's own `scripts/autoresearch.py`; do not assume it is installed in the target repository.

For a status or results request, run the corresponding command directly:

| Request | Command |
|---|---|
| Status | `python3 <control> status --repo <repo>` |
| History | `python3 <control> history --repo <repo>` |
| TSV export | `python3 <control> history --repo <repo> --format tsv` |
| HTML report | `python3 <control> report --repo <repo>` |

Report the requested result without starting or resuming experiments. Return the generated path for an HTML report.

Before starting or resuming an experiment, read the applicable workflow unless it is already in context:

- [Workflow](references/workflow.md): starting, continuing, resuming, or changing an experiment.
- [Background](references/background.md): launching or controlling a detached run.

## Experiment Boundary

- One run owns one Git repository, one numeric metric, one confirmed target, and approved path scopes.
- For a new foreground run, initialize successfully before creating its Goal; the Goal identifies the returned run id. If initialization reports `complete`, no Goal is needed.
- Use `finish` to finalize each coherent experiment. Do not manually commit, revert, or edit run artifacts during an active run.
- Only a verified target can mean `complete`; an iteration limit, error, or external blocker has its own status.
- Validate state through the control script on entry or resume. Use recorded experiments rather than guessing from conversation.
- Surface command and state errors with their diagnostic paths. Never bypass validation, fabricate metrics, or reconstruct missing events.

Foreground continuation belongs to the official Codex Goal. Background continuation belongs to the detached controller. An already launched background worker follows its supplied experiment contract, without starting a new launch flow.
