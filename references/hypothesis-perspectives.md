# Hypothesis Perspectives

Structured multi-lens reasoning applied before committing to a hypothesis. Not multi-agent -- this is a thinking framework within a single agent.

## When to Apply

**Mandatory:**
- On every hypothesis during the first 5 iterations (exploring the problem space).
- Immediately after every REFINE or PIVOT decision (perspectives are part of the re-ideation).

**Optional:**
- When the last 3 iterations were all discards but REFINE has not yet triggered.
- When entering a new strategy family for the first time.

**Skip:**
- For obvious, mechanical fixes (e.g., fixing an import path, renaming a variable).
- When the hypothesis is a direct continuation of a successful strategy (same approach, next target).
- When running in exec mode (minimize overhead in CI).

## The Four Lenses

### 1. Optimist

Ask: "What is the single most impactful change I could make right now?"

- Focus on the biggest potential gain.
- Consider changes that address the root cause rather than symptoms.
- Look for multiplier effects (one change that improves multiple areas).

### 2. Skeptic

Ask: "Why might this hypothesis fail?"

- Cross-check with the results log: has a similar approach already been tried and discarded?
- Identify assumptions that could be wrong.
- Consider side effects that could trigger guard failure.
- Check if the hypothesis depends on conditions that may not hold.

### 3. Historian

Ask: "What do past results and lessons tell me?"

- Consult `autoresearch-results/lessons.md` for relevant entries.
- Review the results log for patterns:
  - Which strategy families have the best keep rate?
  - Which files or areas have been most responsive to changes?
  - What is the typical delta for successful iterations?
- If this is the first run with no history, note "no prior data" and move on.

### 4. Minimalist

Ask: "Is there a simpler version of this hypothesis?"

- Can the same effect be achieved with fewer file changes?
- Can the change be smaller in scope while still testing the core idea?
- Is there a way to achieve 80% of the benefit with 20% of the complexity?
- Would a simpler version be easier to revert if it fails?

## Decision Process

After applying all four lenses:

1. If all lenses agree on the hypothesis, proceed.
2. If the Skeptic raises a concrete concern backed by evidence (prior failure in results log, known side effect from lessons), address the concern before proceeding. Evidence-backed skepticism overrides optimism.
3. If the Historian suggests a better-tested alternative, prefer it unless the Optimist's case is compelling and untried.
4. If the Minimalist offers a simpler version that tests the same core idea, prefer the simpler version.
5. **Tie-breaking:** A tie is when 2 lenses favor and 2 oppose (or equivalent ambiguity). In a true tie, the Minimalist wins -- smaller experiments are cheaper to discard. If no Minimalist alternative exists, prefer the untried approach over the retried one.

## Output Format

When perspectives are applied, record the reasoning briefly in the commit message or log description:

```
experiment: [hypothesis] (perspectives: optimist=high-impact, skeptic=no prior failures, historian=new approach, minimalist=single-file change)
```

Do not add perspectives reasoning to the TSV log -- keep it in commit messages only to avoid log bloat.

## Integration Points

- **autonomous-loop-protocol.md (Phase 3: Ideate):** Apply perspectives before selecting the hypothesis.
- **lessons-protocol.md:** Historian lens reads from the lessons file.
- **pivot-protocol.md:** Always apply perspectives after a REFINE or PIVOT.
- **parallel-experiments-protocol.md:** When generating multiple hypotheses for parallel execution, apply perspectives to each independently.
