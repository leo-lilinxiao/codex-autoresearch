# Runtime Hard Invariants

Use this file as the primary execution checklist during active runs. Keep it short in memory. Treat the other protocol files as detailed reference material unless a specific situation requires them.

## Shared Runtime Checklist

1. Measure the baseline before initializing run artifacts.
2. Initialize artifacts immediately after the baseline is known.
3. Treat every completed experiment as unfinished until it is logged.
4. Record each completed experiment before starting the next one.
5. Use the bundled helper scripts for authoritative TSV/JSON updates.
6. Let helper logic own keep/stop gating and row/state semantics.
7. Foreground's core persistent artifacts are `research-results.tsv` and `autoresearch-state.json`. Background adds launch/runtime control artifacts.
8. Lessons are secondary helper-derived output, not a primary runtime invariant.
9. Stop only on goal reached, manual stop, configured iteration cap, or a true blocker.
10. After any context compaction event, re-read `core-principles.md`, this file, and the selected mode workflow before the next iteration.
11. Every 10 iterations, run the Protocol Fingerprint Check. If any item fails, re-read the loaded runtime docs before continuing.

## Protocol Fingerprint Check

Verify you can still recall:

- baseline before init,
- log every completed experiment before the next one starts,
- helper scripts own authoritative TSV/JSON updates and keep/stop gating,
- the current stop conditions and rollback strategy,
- the selected mode workflow plus any active pivot/refine escalation.

## Closeout Order

For normal loop execution, the closeout order is:

1. finish the experiment,
2. run verify and guard,
3. record the result through the helper,
4. only then choose the next idea.

Do not treat logging as optional bookkeeping.
