# Web Search Protocol

Controlled integration of web search into the autonomous loop. Search results are treated as hypothesis inputs, never as verified solutions.

## When to Search

### Automatic Triggers

1. **PIVOT Escalation:** After 2 PIVOTs without improvement (see `references/pivot-protocol.md` Level 3).
2. **Unfamiliar Error:** During debug or fix mode, when an error message is not found anywhere in the codebase and the agent cannot form a hypothesis from code context alone.
3. **Framework/API Uncertainty:** When the hypothesis requires knowledge of an external library's behavior that cannot be determined from the installed source or type definitions.

### User Opt-In

During the wizard phase, the user may explicitly enable or disable web search:

- "You can search the web if you get stuck" -> enable
- "Stay offline" / "No web search" -> disable
- Default: enabled for PIVOT escalation, disabled otherwise

## Constraints

### Timing

- **Never in the first 3 iterations.** The agent must attempt local reasoning first.
- **Maximum 3 searches per 10 iterations.** Sliding window: count searches in the last 10 iterations.
- **Cooldown:** At least 2 iterations between consecutive searches. If a search triggers a PIVOT which would trigger another search, the cooldown still applies -- wait 2 iterations.
- **Trigger stacking:** If multiple triggers fire simultaneously (PIVOT escalation + unfamiliar error), execute only one search. The cooldown prevents the second.

### Query Formulation

Formulate queries that are:
- Specific to the technical problem (not the project)
- Include the language, framework, and error signature
- Exclude project-specific names

Good queries:
- `python asyncio connection pool exhaustion under concurrent requests`
- `typescript strict mode generic inference failure readonly array`
- `webpack 5 circular dependency warning resolution`

Bad queries:
- `how to fix my code`
- `codex-autoresearch stuck`
- `MyProjectName search endpoint slow`

### Result Handling

Search results are **hypotheses**, not solutions:

1. Extract 1-3 candidate approaches from search results.
2. For each candidate, formulate a testable hypothesis.
3. Enter the normal iteration cycle: modify -> verify -> keep/discard.
4. Do not copy-paste solutions. Adapt the approach to the current codebase.
5. If a search yields no useful results, log it and continue with local reasoning.

## Logging

### Results TSV

Search iterations use status `search`:

```tsv
iteration	commit	metric	delta	guard	status	description
12	-	-	-	-	search	[SEARCH] "asyncio pool exhaustion concurrent" -> found connection limit pattern
13	d4e5f6g	38	-3	pass	keep	applied pool limit increase from search insight
```

### Search Log

Optionally append to a search log section in the results TSV comments:

```tsv
# search_log:
# iteration=12 query="asyncio pool exhaustion concurrent" results=3 useful=1
```

## Integration Points

- **pivot-protocol.md:** Level 3 escalation triggers web search.
- **debug-workflow.md:** Unfamiliar error pattern triggers search.
- **fix-workflow.md:** Unfamiliar error during repair triggers search.
- **interaction-wizard.md:** Wizard can ask about web search preference.
- **results-logging.md:** New `search` status value.

## Disabling Web Search

If the environment does not support web search (no internet, restricted sandbox), or the user opts out:

1. Skip Level 3 escalation in the pivot protocol.
2. Proceed directly from Level 2 (PIVOT) to Level 4 (soft blocker warning) after 3 PIVOTs.
3. Log: `[SEARCH SKIPPED] web search unavailable or disabled`.
