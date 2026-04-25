# Loop Workflow

Use this workflow for the default metric-driven improve/verify loop.

This is the thin execution guide for active runtime work. Load `autonomous-loop-protocol.md` for Phase 0 on every fresh launch, resume boundary, or recovery decision. Once the loop is running, keep `runtime-hard-invariants.md` in memory and reopen `autonomous-loop-protocol.md` only when you need detailed recovery, health-check, or escalation behavior.

## Purpose

Iterate toward a measurable outcome by making one focused change, verifying mechanically, deciding keep or discard, logging the result, and repeating.

## Before Launch

- Use `interaction-wizard.md` for every new interactive launch.
- Use `session-resume-protocol.md` before deciding whether the run is fresh or resumable.
- Use `environment-awareness.md` before choosing hardware-sensitive work.

## Runtime Cycle

1. Read the current in-scope context, recent results rows, and relevant retained state.
2. If no baseline exists yet, measure it and initialize `autoresearch-results/results.tsv` plus `autoresearch-results/state.json`.
3. Choose one focused hypothesis.
4. Make one focused change within scope.
5. Run the verify command and guard.
6. Record the result through `autoresearch_record_iteration.py` or `autoresearch_select_parallel_batch.py`.
7. Only after the result is recorded, choose the next experiment.

## Escalation And Recovery

- Use `pivot-protocol.md` when repeated discards show the current line of attack is stale.
- Use `results-logging.md` only when you need the detailed TSV/state contract or helper behavior.
- Use `lessons-protocol.md` only when you need to reason about lessons behavior directly.
- Use `health-check-protocol.md` when runtime integrity looks suspect.
- Use `parallel-experiments-protocol.md`, `web-search-protocol.md`, or `hypothesis-perspectives.md` only when those behaviors are actively in play.

## Stop Conditions

Keep iterating until one of these happens:

- the goal is reached,
- the user interrupts,
- the configured iteration cap is reached,
- or a true blocker appears.
