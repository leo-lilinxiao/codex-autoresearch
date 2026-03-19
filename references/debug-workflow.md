# Debug Workflow

Evidence-driven bug hunting based on hypotheses, experiments, and classification.

**Two-phase boundary:** All clarifying questions happen before launch. Once the user says "go", this workflow is fully autonomous -- never pause to ask the user anything. If you encounter ambiguity, apply best practices and keep going.

## Purpose

Use this mode when the user needs root-cause analysis rather than immediate blind fixes.

## Trigger

- `$codex-autoresearch Mode: debug`
- "find all bugs"
- "debug this"
- "why is this failing"
- "investigate this issue"

## Flags

| Flag | Purpose |
|------|---------|
| `--scope "<glob>"` | Limit investigation scope |
| `--symptom "<text>"` | Pre-fill the issue statement |
| `--fix` | Chain into fix mode after findings |
| `--severity critical|high|medium|low` | Minimum severity to report |
| `--technique <name>` | Force a specific investigation technique |
| `--iterations N` | Bound the investigation |

## Wizard

If `Scope` or `Symptom` is missing, collect:

- Symptom
- Scope
- Investigation depth
- After-action preference

## Investigation Techniques

- direct inspection
- trace execution
- minimal reproduction
- binary search
- differential debugging
- pattern search
- working backwards
- image analysis (screenshots, flame graphs, UI captures -- see Image Input below)

## Image Input

Debug mode accepts image input during the wizard phase:

- **Error screenshots:** extract error messages, stack traces, and UI state from images.
- **Flame graphs:** identify hot paths and performance bottlenecks visually.
- **UI bugs:** compare expected vs actual rendering from screenshot evidence.

When an image is provided:
1. Analyze the image to extract relevant diagnostic information.
2. Use extracted information to inform hypotheses during Phase 3.
3. Reference the image findings in the `evidence` field of confirmed findings.

## Web Search for Unfamiliar Errors

When an error message is not found anywhere in the codebase and the agent cannot form a hypothesis from code context alone, web search may be triggered per `references/web-search-protocol.md`. Search results are treated as hypotheses and verified mechanically.

## Phases

### Phase 1: Gather

Collect:

- expected behavior,
- actual behavior,
- reproduction steps,
- error messages,
- affected environment.

If the user did not provide symptoms, scan tests, typecheck, lint, and build output for leads.

### Phase 2: Reconnaissance

Map:

- relevant files,
- call chains,
- integration points,
- recent commits in the affected area.

### Phase 3: Hypothesize

Create one falsifiable hypothesis at a time.

### Phase 4: Test

Run one targeted experiment.

Rules:

- one experiment per iteration,
- record the exact command or inspection step,
- keep the experiment minimal.

### Phase 5: Classify

Result types:

- confirmed bug
- disproven hypothesis
- inconclusive
- new lead

Severity:

- critical
- high
- medium
- low

### Phase 6: Log

Append to:

```tsv
iteration	type	hypothesis	result	severity	location	description
```

### Phase 7: Repeat

Priority order:

1. new leads,
2. untested high-confidence hypotheses,
3. new files in the error surface,
4. bug-pattern expansion.

## Output Directory

```text
debug/{YYMMDD}-{HHMM}-{slug}/
  findings.md
  eliminated.md
  debug-results.tsv
  summary.md
```

## Structured Findings

Each finding in `findings.md` must include:

- title
- severity
- location
- hypothesis
- evidence
- reproduction
- impact
- root cause
- suggested fix

## Completion

Stop when:

- iteration limit is reached,
- the user interrupts,
- or the workflow has gone several iterations without producing new leads and reports diminishing returns.
