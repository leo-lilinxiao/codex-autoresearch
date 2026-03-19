# Lessons Protocol

Cross-run learning system. Extracts structured insights from completed iterations and persists them so future runs start smarter.

## Lessons File

Default filename:

```text
autoresearch-lessons.md
```

This file lives alongside the results log. It is never committed to git.

## Lesson Structure

Each lesson is a structured entry:

```markdown
### L-{N}: {title}
- **Strategy:** what was attempted
- **Outcome:** keep / discard / crash / pivot
- **Insight:** what to do differently next time
- **Context:** goal, scope, metric at the time
- **Iteration:** {run-tag}#{iteration-number}
- **Timestamp:** {ISO-8601 UTC}
```

## When to Extract Lessons

### Timing Precision

Lesson extraction happens at specific points in the iteration cycle:

- **After a KEEP decision (Phase 7) and before Log (Phase 8):** Extract a positive lesson.
- **After a PIVOT decision (Phase 7) and before Log (Phase 8):** Extract a strategic lesson.
- **At run completion (when Phase 9 exits):** Extract a summary lesson if none was extracted in the last 5 iterations.

### After Every Kept Iteration

Extract a positive lesson:
- What strategy worked?
- Why did it work? (correlation with prior successes, unique approach, etc.)
- Is this generalizable or specific to current scope?

### After Every PIVOT Decision

Extract a strategic lesson:
- What strategy family was abandoned?
- How many iterations were spent before pivoting?
- What signal triggered the pivot?

### At Run Completion

Extract a summary lesson:
- Best overall strategy family for this goal type
- Most common failure patterns
- Effective verify/guard combinations observed

## Reading Lessons

### At Run Start (Phase 1: Read)

1. Check if `autoresearch-lessons.md` exists.
2. If it exists, read all entries.
3. During hypothesis generation (Phase 3: Ideate), consult lessons to:
   - Prefer strategies that succeeded in similar contexts.
   - Avoid strategies that consistently failed.
   - Adapt successful strategies from related goals.

### During Ideation (Phase 3)

Before committing to a hypothesis:
1. Scan lessons for entries matching the current goal type or scope.
2. If a matching positive lesson exists, bias toward that strategy family.
3. If a matching negative lesson exists, skip unless the context is materially different.

## Capacity Management

### Cap: 50 Entries

When the lessons file exceeds 50 entries:

1. Group entries by strategy family.
2. For each family, compute a success ratio: `kept / (kept + discarded + crashed)`.
3. Summarize families with 5+ entries into a single consolidated entry.
4. Remove individual entries older than 30 days that have been summarized.
5. Keep all entries from the current run regardless of age.

### Time Decay

Lessons older than 14 days receive reduced weight during hypothesis selection. Lessons older than 30 days are candidates for summarization. Lessons from the current run always have full weight.

## Writing Rules

- Create the lessons file at the end of the first iteration that produces a keep or pivot.
- Append after each qualifying event (keep, pivot, run completion).
- Never commit the lessons file.
- Use the same run tag as the results log for cross-referencing.
- If the lessons file is corrupted or unparseable, rename it with a `.bak` suffix and start fresh.

## Integration Points

- **Phase 1 (Read):** load lessons file if present.
- **Phase 3 (Ideate):** consult lessons before choosing hypothesis.
- **Phase 7 (Decide):** after keep -> extract positive lesson.
- **Phase 9 (Repeat):** after pivot -> extract strategic lesson.
- **Completion:** extract summary lesson.
- **Session Resume:** lessons file is a primary signal for detecting prior runs.
