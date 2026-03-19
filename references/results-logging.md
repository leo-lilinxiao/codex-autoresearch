# Results Logging

Use a plain TSV log so the agent can learn from prior iterations.

## Generic Log File

Default filename:

```text
research-results.tsv
```

Add a direction comment at the top:

```text
# metric_direction: higher
```

or

```text
# metric_direction: lower
```

## Header Comments

The first comment line declares the metric direction. Additional comment lines may include:

```text
# environment: cpu=8 ram=16384MB gpu=A100(40GB) python=3.11 container=docker
# metric_direction: lower
# run_tag: any-types-v2
# parallel: serial
# web_search: enabled
```

## Generic Schema

```tsv
iteration	commit	metric	delta	guard	status	description
```

## Columns

| Column | Meaning |
|--------|---------|
| `iteration` | Sequential counter, starting at `0` for the baseline. Parallel batches use suffix notation (`5a`, `5b`, `5c`) |
| `commit` | Short hash for kept or attempted commit, `-` if reverted or not committed |
| `metric` | Parsed metric value |
| `delta` | Change versus current best |
| `guard` | `pass`, `fail`, or `-` |
| `status` | See Status Values below |
| `description` | One-sentence explanation of the iteration |

## Status Values

| Status | Meaning |
|--------|---------|
| `baseline` | Initial measurement before any changes |
| `keep` | Change improved the metric and passed guard |
| `discard` | Change did not improve or failed guard |
| `crash` | Verification crashed or produced an error |
| `no-op` | No actual diff was produced |
| `blocked` | Hard blocker encountered, loop stopped |
| `refine` | Strategy adjustment within current approach (see `pivot-protocol.md`) |
| `pivot` | Strategy abandoned, fundamentally new approach (see `pivot-protocol.md`) |
| `search` | Web search performed for external knowledge (see `web-search-protocol.md`) |
| `drift` | Metric drifted from expected value during session resume |

## Example

```tsv
# metric_direction: lower
iteration	commit	metric	delta	guard	status	description
0	a1b2c3d	14	0	-	baseline	current pytest failure count
1	b2c3d4e	9	-5	pass	keep	reduce fixture startup overhead
2	-	11	+2	-	discard	expand retries in API client
3	-	0	0	-	crash	refactor parser with bad import
4	-	9	0	fail	discard	inline auth cache but break regression guard
```

## Parallel Batch Notation

When parallel experiments are active (see `references/parallel-experiments-protocol.md`), use suffix notation for worker iterations:

```tsv
5a	abc1234	38	-3	pass	keep	[PARALLEL worker-a] narrowed auth types (SELECTED)
5b	-	42	+1	pass	discard	[PARALLEL worker-b] wrapper approach
5c	-	40	-1	fail	discard	[PARALLEL worker-c] union types (guard fail)
```

Only the selected result increments the main iteration counter.

## Rules

- Create the log at setup time.
- Append after every iteration, including crashes, no-ops, refines, pivots, and searches.
- Never commit the log.
- Re-read the latest entries before choosing the next idea.
- Health check warnings are logged in the description column with a `[HEALTH]` prefix.
