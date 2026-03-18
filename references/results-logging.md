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

## Generic Schema

```tsv
iteration	commit	metric	delta	guard	status	description
```

## Columns

| Column | Meaning |
|--------|---------|
| `iteration` | Sequential counter, starting at `0` for the baseline |
| `commit` | Short hash for kept or attempted commit, `-` if reverted or not committed |
| `metric` | Parsed metric value |
| `delta` | Change versus current best |
| `guard` | `pass`, `fail`, or `-` |
| `status` | `baseline`, `keep`, `discard`, `crash`, `no-op`, or `blocked` |
| `description` | One-sentence explanation of the iteration |

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

## Rules

- Create the log at setup time.
- Append after every iteration, including crashes and no-ops.
- Never commit the log.
- Re-read the latest entries before choosing the next idea.
