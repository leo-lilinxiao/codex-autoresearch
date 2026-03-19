# Recipes

Working examples organized by what you want to accomplish. Each recipe shows what you say to Codex, what Codex does, and the configuration it generates internally. You only need the one-liner -- Codex figures out the rest.

---

## Table of Contents

- [Iterating Toward a Target](#iterating-toward-a-target)
- [Fixing Broken Things](#fixing-broken-things)
- [Hunting Bugs](#hunting-bugs)
- [Auditing for Vulnerabilities](#auditing-for-vulnerabilities)
- [Planning When You Are Unsure](#planning-when-you-are-unsure)
- [Releasing with Confidence](#releasing-with-confidence)
- [Chaining Modes](#chaining-modes)
- [CI/CD Mode (exec)](#cicd-mode-exec)
- [MCP Integration](#mcp-integration)
- [Choosing Verify and Guard Commands](#choosing-verify-and-guard-commands)

---

## Iterating Toward a Target

These all use loop mode. You state a goal, Codex proposes metrics and verification, you say "go."

### Eliminate `any` types in TypeScript

```
You:   $codex-autoresearch
       Get rid of all the `any` types in my TypeScript code

Codex: I found 47 `any` occurrences across src/**/*.ts.

       Confirmed:
       - Target: eliminate `any` types in src/**/*.ts
       - Metric: `any` count (current: 47), direction: lower
       - Verify: grep count + tsc --noEmit as guard

       Need to confirm:
       - Run until all gone, or cap at N iterations?

You:   Go, run overnight.
```

What Codex does each iteration: picks one `any` usage, replaces it with a proper type annotation, verifies the count dropped and tsc still compiles, keeps or reverts.

### Raise Python test coverage

```
You:   $codex-autoresearch
       Raise my test coverage from 58% to at least 85%

Codex: Found 58% coverage across src/.

       Confirmed:
       - Target: 85%+ test coverage
       - Metric: coverage percentage, direction: higher
       - Verify: pytest coverage report
       - Guard: ruff linter

       Need to confirm:
       - Should I write new test files or only add to existing ones?
       - Any modules to prioritize?

You:   Either is fine. Start with src/auth/ and src/api/. Go.
```

What Codex does each iteration: identifies an uncovered function or branch, writes a test for it, verifies coverage increased and lint still passes, keeps or reverts.

### Reduce API response time

```
You:   $codex-autoresearch
       The /search endpoint p95 is 800ms, get it under 200ms

Codex: Found the search handler in src/api/search.ts. It queries
       PostgreSQL with 3 JOINs and no index hints.

       Confirmed:
       - Target: p95 latency under 200ms for /search
       - Metric: p95 latency in ms, direction: lower
       - Verify: benchmark script, Guard: existing test suite

       Need to confirm:
       - Can I add database indexes, or code-only changes?
       - Is there a load testing script I should use?

You:   You can add indexes. Use `npm run bench:search` for benchmarks. Go.
```

Strategies Codex will try: adding database indexes, optimizing query structure, introducing caching, reducing middleware overhead, batching related queries.

### Shrink Webpack build warnings

```
You:   $codex-autoresearch
       Eliminate all the Webpack build warnings

Codex: Found 23 warnings in the last build output.

       Confirmed:
       - Target: zero build warnings
       - Metric: warning count, direction: lower
       - Verify: build output warning count
       - Guard: unit test suite

       Need to confirm:
       - Should I also address deprecation notices?

You:   Yes. Go, 15 iterations max.
```

### Speed up the CI pipeline

```
You:   $codex-autoresearch
       CI takes 14 minutes, I need it under 6

Codex: Analyzed .github/workflows/ci.yml. The test job runs sequentially
       and installs dependencies from scratch each time.

       Confirmed:
       - Target: CI duration under 6 minutes
       - Metric: total pipeline time, direction: lower
       - Verify: local test timing as proxy
       - Guard: all tests must still pass

       Need to confirm:
       - Can I modify the workflow YAML, or code-only?
       - Is the Docker build step required on every push?

You:   You can modify the workflow. Docker build only on main. Go.
```

Strategies Codex will try: parallelizing test shards, caching node_modules/pip packages, skipping redundant steps on feature branches, splitting slow integration tests into a separate job.

### Make clippy happy in Rust

```
You:   $codex-autoresearch
       Clean up all the clippy warnings in the Rust codebase

Codex: Found 31 clippy warnings across src/.

       Confirmed:
       - Target: zero clippy warnings
       - Metric: warning count, direction: lower
       - Verify: cargo clippy output
       - Guard: cargo test

       Need to confirm:
       - Should I also address `cargo clippy -- -W clippy::pedantic`?

You:   No, just the default warnings. Go.
```

---

## Fixing Broken Things

Fix mode iterates until the error count reaches zero. It auto-detects what is broken.

### Fix all pytest failures

```
You:   $codex-autoresearch
       pytest is failing, 12 tests broken after the refactor

Codex: I see 12 failures across tests/.

       Confirmed:
       - Target: make all pytest tests pass
       - Current: 12 failures

       Need to confirm:
       - Should I also guard with ruff to avoid introducing lint issues?
       - Fix all 12, or focus on a specific module first?

You:   Fix all, yes guard with ruff. Go.
```

Stops automatically when all tests pass.

### Fix TypeScript compilation errors

```
You:   $codex-autoresearch
       tsc is throwing 28 errors after the dependency upgrade

Codex: Found 28 type errors. Most are in src/api/ -- the new version
       of express changed several type signatures.

       Confirmed:
       - Target: zero tsc errors
       - Current: 28 errors

       Need to confirm:
       - Should I also run the test suite as a guard?

You:   Yes. Go.
```

### Fix ESLint errors after config change

```
You:   $codex-autoresearch
       Switched to stricter ESLint config and now there are 94 violations

Codex: Found 94 violations. Breakdown: 41 unused-vars, 23 no-explicit-any,
       18 prefer-const, 12 other.

       Confirmed:
       - Target: zero ESLint violations
       - Current: 94

       Need to confirm:
       - Should I also guard with tsc?
       - Some unused-vars might indicate dead code -- remove or suppress?

You:   Remove dead code. Guard with tsc. Go.
```

### Fix Go vet warnings

```
You:   $codex-autoresearch
       Clean up all go vet issues

Codex: Found 7 go vet warnings across cmd/ and internal/.

       Confirmed:
       - Target: zero go vet warnings
       - Current: 7

You:   Go.
```

---

## Hunting Bugs

Debug mode tests one hypothesis per iteration. Every finding needs evidence.

### Intermittent 503 under load

```
You:   $codex-autoresearch
       API returns 503 randomly under concurrent requests

Codex: I see connection pooling in src/db/pool.ts, rate limiting in
       src/middleware/, and 3 async handlers without error boundaries.

       Confirmed:
       - Symptom: intermittent 503 under concurrent load
       - Scope: src/api/, src/db/, src/middleware/

       Need to confirm:
       - When did this start? After a specific change, or always?
       - If I find the cause, should I also fix it?

You:   Started after the connection pool refactor last week. Find cause first.
```

Produces a findings directory with confirmed causes, disproven hypotheses, and recommended next steps.

### Search returning duplicate results

```
You:   $codex-autoresearch
       Paginated search results have duplicates when you go to page 2

Codex: Found the search handler in src/api/search.ts.
       It uses OFFSET/LIMIT pagination with a non-unique sort key.

       Confirmed:
       - Symptom: duplicate results on page 2+
       - Scope: src/api/search.ts, src/db/queries/

       Need to confirm:
       - Is this happening on all search endpoints or just /search?

You:   Just /search. Go.
```

### Silent cron job failures

```
You:   $codex-autoresearch
       The nightly data sync job keeps failing silently, no errors in logs

Codex: Found the job in src/jobs/sync.ts. The catch block swallows
       exceptions without logging.

       Confirmed:
       - Symptom: nightly job fails with no error output
       - Scope: src/jobs/, src/services/sync/

       Need to confirm:
       - Should I also fix the error handling, or just diagnose?

You:   Diagnose first, I'll fix separately.
```

---

## Auditing for Vulnerabilities

Security mode is read-only by default. Every finding requires file:line evidence.

### API injection audit

```
You:   $codex-autoresearch
       Check our API layer for injection vulnerabilities

Codex: Confirmed:
       - Scope: src/api/ and src/middleware/ (14 files)
       - Focus: SQL injection, XSS, input sanitization

       Need to confirm:
       - Report only, or also fix critical findings?
       - Should I also cover auth/access control?

You:   Report first, cover auth too.
```

Produces a report with ranked findings, each with file:line reference and exploitation scenario.

### Audit changed files only

```
You:   $codex-autoresearch
       Security check on just the files I changed this sprint

Codex: I see 8 modified files since the last tag. 3 are in src/api/,
       2 in src/auth/, 3 in tests/.

       Confirmed:
       - Scope: the 5 non-test modified files
       - Focus: input validation, auth changes

       Need to confirm:
       - Include the test files in scope?

You:   No, just the source files. Go.
```

### Audit and fix in one pass

```
You:   $codex-autoresearch
       Find vulnerabilities and fix anything critical

Codex: [runs security audit first]
       Found 2 Critical, 3 High, 5 Medium findings.

       Switching to fix mode for 2 Critical and 3 High findings.
       ...
```

---

## Planning When You Are Unsure

Plan mode helps you figure out what to measure and how. It never modifies code.

### Not sure what metric to use

```
You:   $codex-autoresearch
       I want to make our API faster but I don't know where to start

Codex: I scanned the repo. API layer is in src/api/ with Express + Prisma.

       Need to confirm:
       - What matters more: p95 latency, throughput, or cold start?
       - Should I benchmark the whole API or specific endpoints?

You:   p95 latency, the /search endpoint is the worst.

Codex: Proposed configuration:
       - Goal: Reduce /search p95 latency
       - Scope: src/api/search.ts, src/db/queries/, src/middleware/
       - Metric: p95 latency (ms), direction: lower
       - Verify: npm run bench:search 2>&1 | grep p95 | awk '{print $2}'
       - Guard: npm test

       Dry-run result: verify command outputs 847 (ms).
       Ready to paste into a loop invocation.
```

### Want to improve code quality

```
You:   $codex-autoresearch
       The codebase feels messy, what should I clean up first?

Codex: I scanned the repo. Here's what I found:
       - 47 `any` types in TypeScript
       - 6 files with cyclomatic complexity > 20
       - 12% of src/ has no test coverage
       - 23 Webpack build warnings

       Which of these matters most to you?

You:   Start with the `any` types.

Codex: [generates config for eliminating any types]
```

### Want to optimize database performance

```
You:   $codex-autoresearch
       Help me figure out how to make our database queries faster

Codex: Found 14 query files in src/db/. The /search endpoint runs
       3 JOINs with no EXPLAIN analysis. Two queries use SELECT *.

       Need to confirm:
       - Focus on query execution time, or total endpoint latency?
       - Can I add indexes to the schema?

You:   Total endpoint latency. Yes you can add indexes.

Codex: [generates config with endpoint latency as metric]
```

---

## Releasing with Confidence

Ship mode detects what you are releasing and generates a verification checklist.

### Ship a PR

```
You:   $codex-autoresearch
       Ship it

Codex: Detected: PR to main with 3 commits.

       Confirmed:
       - Type: code PR
       - Target: main branch

       Need to confirm:
       - Dry run first, or go live?
       - Post-ship monitoring? (5 min / 15 min / skip)

You:   Dry run first.
```

### Check readiness without shipping

```
You:   $codex-autoresearch
       Are we ready to deploy?

Codex: Running readiness checklist...
       - Tests: 142/142 passing
       - Types: clean
       - Lint: clean
       - Build: succeeds
       - No uncommitted changes
       - Branch is up to date with main

       All checks pass. Ready to ship when you are.
```

---

## Chaining Modes

Modes compose naturally through sequential invocations.

### Debug then fix

```
You:   $codex-autoresearch
       API returns 503 randomly under load
       [debug mode finds: pool exhaustion, missing error boundary]

You:   $codex-autoresearch
       Fix the bugs you just found
       [fix mode reads debug findings, repairs them one by one]
```

### Plan then loop

```
You:   $codex-autoresearch
       I want to reduce our API latency but not sure how
       [plan mode produces config]

You:   $codex-autoresearch
       Run the plan you made
       [loop mode executes with the generated config]
```

### Audit then fix

```
You:   $codex-autoresearch
       Audit the auth system, then fix anything critical
       [security mode audits, switches to fix mode for Critical/High]
```

---

## CI/CD Mode (exec)

Non-interactive mode for automation pipelines. All config upfront, JSON output, exit codes.

### Reduce type errors in GitHub Actions

```yaml
- name: Reduce type errors
  run: |
    codex exec --skill codex-autoresearch \
      --goal "Reduce type errors" \
      --scope "src/**/*.ts" \
      --metric "type error count" \
      --direction lower \
      --verify "tsc --noEmit 2>&1 | grep -c error" \
      --iterations 20
  continue-on-error: true
```

Exit codes: 0 = improved, 1 = no improvement, 2 = hard blocker.

### Raise coverage in GitLab CI

```yaml
optimize-coverage:
  script:
    - codex exec --skill codex-autoresearch
        --goal "Raise test coverage"
        --scope "src/"
        --metric "coverage percentage"
        --direction higher
        --verify "pytest --cov=src --cov-report=term 2>&1 | grep TOTAL | awk '{print $NF}'"
        --guard "ruff check ."
        --iterations 15
  allow_failure: true
```

### Nightly lint cleanup

```yaml
- name: Nightly lint cleanup
  run: |
    codex exec --skill codex-autoresearch \
      --goal "Eliminate ESLint violations" \
      --scope "src/" \
      --metric "violation count" \
      --direction lower \
      --verify "npx eslint src/ --format compact 2>&1 | tail -1 | grep -oP '\\d+ problem'" \
      --guard "npm run test:unit" \
      --iterations 30
  schedule:
    - cron: '0 3 * * *'
```

---

## MCP Integration

MCP (Model Context Protocol) servers extend Codex's capabilities. These recipes show how to combine autoresearch with MCP tools.

### Framework docs lookup during optimization

If you have an MCP docs server configured (e.g., for React, Django, or Express):

```
You:   $codex-autoresearch
       Optimize our React component rendering performance

Codex: [during ideation, queries MCP docs server for React.memo,
       useMemo, and useCallback best practices]
       [uses documentation insights to generate better hypotheses]
```

The agent consults MCP docs automatically when it encounters framework-specific patterns it needs to understand better. No special configuration needed beyond having the MCP server available.

### Database EXPLAIN queries during latency optimization

If you have an MCP database server configured:

```
You:   $codex-autoresearch
       Reduce /search endpoint p95 latency from 800ms to 200ms

Codex: [runs EXPLAIN via MCP database server to identify slow queries]
       [uses query plans to generate targeted index and query optimizations]
```

### API testing during security audits

If you have an MCP API testing server configured:

```
You:   $codex-autoresearch Mode: security
       Audit our REST API for injection vulnerabilities

Codex: [uses MCP API server to send test payloads during audit]
       [validates findings with actual API responses, not just code analysis]
```

---

## Choosing Verify and Guard Commands

The protocol is language-agnostic. Only the commands change.

### By language

| Language | Common verify | Common guard |
|----------|--------------|--------------|
| TypeScript | `npx tsc --noEmit 2>&1 \| grep -c error` | `npm run test:unit` |
| Python | `pytest -q 2>&1 \| tail -1` | `ruff check .` |
| Go | `go vet ./... 2>&1 \| wc -l` | `go test ./...` |
| Rust | `cargo clippy 2>&1 \| grep -c warning` | `cargo test` |
| Java | `mvn compile 2>&1 \| grep -c ERROR` | `mvn test` |

### By metric type

| What you track | Verify command pattern | Guard pattern |
|----------------|----------------------|---------------|
| Error count | Run the tool, count errors in output | Run test suite |
| Coverage % | Run coverage tool, extract percentage | Run linter |
| Latency (ms) | Run benchmark, extract p95/p99 | Run functional tests |
| Warning count | Run build/lint, count warnings | Run test suite |
| File size | Build output, measure artifact size | Run smoke test |

### Writing a good verify command

Requirements:
- Must output a single number (or a line containing a number Codex can extract)
- Must be deterministic (same input = same output)
- Must be fast (minutes, not hours -- fast verification = more experiments)
- Must not require user interaction

### Compound guards

Chain multiple safety checks with `&&`:

```
Guard: npx tsc --noEmit && npm run test:unit && npm run lint
```

All must pass for the guard to pass.
