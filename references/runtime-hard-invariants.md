# Runtime Hard Invariants

Use this file as the primary execution checklist during active runs. Keep it short in memory. Treat the other protocol files as detailed reference material unless a specific situation requires them.

## Shared Runtime Checklist

1. Measure the baseline before initializing run artifacts.
2. Initialize artifacts immediately after the baseline is known.
3. Treat every completed experiment as unfinished until it is logged.
4. Record each completed experiment before starting the next one.
5. Use the bundled helper scripts for authoritative TSV/JSON updates.
6. Let helper logic own keep/stop gating and row/state semantics.
7. All normal run artifacts are workspace-owned under `autoresearch-results/`: `results.tsv`, `state.json`, `context.json`, and `lessons.md`; background also uses `launch.json`, `runtime.json`, and `runtime.log`.
8. Lessons are secondary helper-derived output, not a primary runtime invariant.
9. Stop only on goal reached, manual stop, configured iteration cap, a true blocker, or the documented soft-blocker handoff after strategy exhaustion.
10. After any context compaction event, re-read `core-principles.md`, this file, and the selected mode workflow before the next iteration.
11. Every 10 iterations, run the Protocol Fingerprint Check. If any item fails, re-read the loaded runtime docs before continuing.

## Protocol Fingerprint Check

Verify you can still recall:

- baseline before init,
- log every completed experiment before the next one starts,
- helper scripts own authoritative TSV/JSON updates and keep/stop gating,
- artifact paths come from `workspace_root` + `autoresearch-results/` and the git-local pointer, never from repo-root artifact guessing,
- the current stop conditions for this run,
- the current rollback strategy in use,
- the active pivot/refine escalation thresholds when they matter,
- the selected mode workflow's key deviation from the default loop.

## Closeout Order

For normal loop execution, the closeout order is:

1. finish the experiment,
2. run verify and guard,
3. record the result through the helper,
4. only then choose the next idea.

Do not treat logging as optional bookkeeping.
