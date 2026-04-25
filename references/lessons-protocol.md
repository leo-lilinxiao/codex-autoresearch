# Lessons Protocol

Cross-run learning system. Extracts structured insights from completed iterations and persists them so future runs start smarter.

The executable companion is:

```bash
python3 <skill-root>/scripts/autoresearch_lessons.py
```

The protocol-aligned runtime wiring is:

- `autoresearch_record_iteration.py` appends lessons automatically after every `keep` and every `pivot` in interactive modes.
- `autoresearch_select_parallel_batch.py` appends the same interactive keep lesson when a parallel batch selects a winning worker and records a `keep` main row.
- `autoresearch_runtime_ctl.py` appends the completion summary lesson when the managed runtime reaches a terminal decision and no lesson has been written in the last 5 iterations of the same run. If no run tag is available, it only suppresses an exact duplicate summary for the current iteration.
- `exec` mode reads lessons for context but never writes or mutates the lessons file.

## Lessons File

Default filename:

```text
autoresearch-results/lessons.md
```

This file lives in the workspace-owned Results directory alongside `results.tsv`. It is never committed to git.

## Lesson Structure

Each lesson is a structured entry:

```markdown
### L-{N}: {title}
- **Strategy:** what was attempted
- **Outcome:** keep / discard / crash / pivot / summary
- **Insight:** what to do differently next time
- **Context:** goal, scope, metric at the time
- **Iteration:** {run-tag}#{iteration-number} when a run tag exists, otherwise plain {iteration-number}
- **Timestamp:** {ISO-8601 UTC}
```

## When to Extract Lessons

### Timing Precision

Lesson extraction happens at specific points in the iteration cycle:

- **After `autoresearch_record_iteration.py` persists a KEEP row and JSON state:** Extract a positive lesson.
- **After `autoresearch_record_iteration.py` persists a PIVOT row and JSON state:** Extract a strategic lesson.
- **At run completion (when the managed runtime reaches a terminal decision):** Extract a summary lesson if none was extracted in the last 5 iterations of the same run. If there is no run tag, suppress only an exact duplicate for the current iteration.

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

1. Check if `autoresearch-results/lessons.md` exists.
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

### Historical Archive Target: 50 Entries

When the lessons file grows beyond the target size:

1. Preserve every lesson from the current tagged run verbatim. If no run tag exists, preserve the trailing untagged current-run suffix verbatim.
2. Look at older non-current entries first.
3. Group 30+ day-old entries by normalized strategy family.
4. For each family with 5+ eligible entries, replace those individual entries with one consolidated `summary` lesson that records the keep/discard/crash ratio.
5. If the older archive is still above 50 entries after family compaction, roll up the oldest remaining historical entries into one generic historical summary.

### Time Decay

Lessons older than 14 days receive reduced weight during hypothesis selection. Lessons older than 30 days are the first candidates for summarization. Lessons from the current run always have full weight and are not summarized away mid-run.

## Writing Rules

- Create the lessons file at the end of the first iteration that produces a keep or pivot.
- Append after each qualifying event (keep, pivot, run completion).
- The file format on disk must exactly match the lesson structure above; `autoresearch_lessons.py list` is the canonical parser for that format.
- Never commit the lessons file.
- Use the same run tag as the results log for cross-referencing when one is available.
- If the lessons file is corrupted or unparseable, the canonical helper must rename it with a `.bak` suffix and start fresh.

## Integration Points

- **Phase 1 (Read):** load lessons file if present.
- **Phase 3 (Ideate):** consult lessons before choosing hypothesis.
- **Phase 7 (Decide):** after keep -> extract positive lesson.
- **Phase 9 (Repeat):** after pivot -> extract strategic lesson.
- **Completion:** extract summary lesson.
- **Session Resume:** lessons file is a moderate-weight detection signal for prior runs (see `session-resume-protocol.md`). Lessons persist across runs and are read at run start regardless of whether JSON state or TSV is used for recovery.
- **Exec Mode:** exec mode reads lessons for hypothesis filtering but never creates or modifies the lessons file.
