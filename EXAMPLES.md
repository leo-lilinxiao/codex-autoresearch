# Recipes

Practical configurations organized by problem type. Each recipe shows what you say to Codex and the configuration it generates internally. You only need the one-liner -- Codex handles the rest through guided conversation.

---

## By Problem Type

- [Improving a Metric](#improving-a-metric)
- [Fixing Broken Things](#fixing-broken-things)
- [Finding Bugs](#finding-bugs)
- [Security Auditing](#security-auditing)
- [Shipping](#shipping)
- [Planning](#planning)
- [Advanced Patterns](#advanced-patterns)

---

## Improving a Metric

### Eliminate all `any` types in TypeScript

> "Get rid of all the `any` types in my TypeScript code"

```text
Goal: Remove all uses of `any` to achieve strict type safety
Scope: src/**/*.ts
Metric: count of `any` occurrences
Direction: lower
Verify: grep -r ":\s*any" src/ --include="*.ts" | wc -l
Guard: npx tsc --noEmit
```

Each iteration: pick one `any` usage -> replace with a proper type -> verify the count dropped -> confirm the build still passes.

### Increase Python test coverage

> "Raise my test coverage to at least 85%"

```text
Goal: Raise test coverage from 58% to 85%
Scope: src/**/*.py, tests/**/*.py
Metric: coverage %
Direction: higher
Verify: pytest --cov=src --cov-report=term 2>&1 | grep TOTAL | awk '{print $NF}'
Guard: ruff check .
Iterations: 25
```

### Reduce API p95 latency

> "Our API p95 is too high, get it under 200ms"

```text
Goal: Reduce API p95 latency below 200ms
Scope: src/api/**/*.ts, src/middleware/**/*.ts, src/db/**/*.ts
Metric: p95 latency ms
Direction: lower
Verify: npm run bench 2>&1 | grep p95 | awk '{print $NF}'
Guard: npm test
Iterations: 20
```

Strategies Codex will try: query optimization, connection pooling, caching hot paths, reducing middleware overhead, batching database calls.

### Fix flaky tests

> "Some tests pass sometimes and fail sometimes, make them reliable"

```text
Goal: Eliminate flaky test failures
Scope: src/**/*.test.ts, src/**/*.spec.ts
Metric: flaky test count
Direction: lower
Verify: for i in 1 2 3; do npm test 2>&1; done | grep -c "FAIL" || echo 0
Guard: npm test
Iterations: 15
```

Each iteration: identify one timing-dependent or order-dependent test -> make it deterministic -> verify flakiness is reduced -> confirm other tests still pass.

### Reduce CI pipeline duration

> "CI takes 14 minutes, I want it under 6"

```text
Goal: Cut CI pipeline time from 14 minutes to under 6 minutes
Scope: .github/workflows/*.yml, jest.config.*, src/**/*.test.ts
Metric: CI duration in seconds
Direction: lower
Verify: time npm test 2>&1 | grep "real"
Guard: npm test
Iterations: 15
```

Strategies Codex will try: parallelizing test suites, removing redundant setup steps, caching dependencies, splitting slow integration tests.

### Cut Webpack build warnings to zero

> "Eliminate all the build warnings"

```text
Goal: Eliminate all build warnings
Scope: src/**/*.ts, src/**/*.tsx, webpack.config.*
Metric: warning count
Direction: lower
Verify: npm run build 2>&1 | grep -c "WARNING"
Guard: npm test
```

---

## Fixing Broken Things

### Fix all pytest failures

> "pytest is failing, fix everything"

```text
Mode: fix
Target: pytest -q
Guard: ruff check .
Scope: tests/**/*.py, src/**/*.py
```

Stops automatically when all tests pass.

### Fix Go vet violations

> "Clean up all the go vet warnings"

```text
Mode: fix
Target: go vet ./...
Guard: go test ./...
Scope: **/*.go
```

### Fix ESLint errors after config upgrade

> "Upgraded ESLint config and now everything is red, fix it"

```text
Mode: fix
Target: npx eslint src/ --max-warnings 0
Guard: npm test
Scope: src/**/*.ts, src/**/*.tsx
Iterations: 30
```

### Fix Rust clippy warnings

> "Make clippy happy"

```text
Mode: fix
Target: cargo clippy -- -D warnings
Guard: cargo test
Scope: src/**/*.rs
```

### Fix from previous debug session

> "Fix the bugs you found in the last debug session"

```text
Mode: fix
--from-debug
Iterations: 30
```

Imports findings from the latest debug run and repairs them in priority order.

---

## Finding Bugs

### Intermittent 503 under concurrent requests

> "API returns 503 randomly under load, find out why"

```text
Mode: debug
Scope: src/api/**/*.ts, src/middleware/**/*.ts
Symptom: intermittent 503 errors under concurrent requests
Iterations: 15
```

### Search pagination returning duplicates

> "Search results have duplicates when you go to page 2"

```text
Mode: debug
Scope: src/search/**/*.ts, src/db/**/*.ts
Symptom: Search results contain duplicates when cursor crosses page boundaries
Iterations: 12
```

### Cron job silent failures

> "The Monday data sync job keeps failing silently, no errors in logs"

```text
Mode: debug
Scope: src/jobs/**/*.py, src/tasks/**/*.py
Symptom: Scheduled data sync job fails silently every Monday, no error in logs
Iterations: 10
--fix
```

The `--fix` flag auto-switches to fix mode after investigation completes.

---

## Security Auditing

### Full codebase audit

> "Do a security audit on the whole codebase"

```text
Mode: security
Iterations: 10
```

### Focused audit on input handling

> "Check the API layer for injection and XSS"

```text
Mode: security
Scope: src/api/**, src/middleware/**, src/validators/**
Focus: SQL injection, XSS, and input sanitization
Iterations: 10
```

### Delta audit (changed files only)

> "Audit just the files I changed recently"

```text
Mode: security
--diff
```

### Audit with auto-remediation

> "Find vulnerabilities and fix the critical ones"

```text
Mode: security
--fix
Iterations: 15
```

Auto-fixes confirmed Critical/High findings after the audit.

---

## Shipping

### Ship a PR

> "Ship the payment gateway PR"

```text
Mode: ship
Type: code-pr
Target: feature/payment-gateway
```

### Dry-run a deployment

> "Do a dry run of the deployment"

```text
Mode: ship
--type deployment
--dry-run
```

### Auto-approve ship

> "Ship it, auto-approve if checks pass"

```text
Mode: ship
--auto
```

### Readiness check only

> "Just check if we're ready to ship"

```text
Mode: ship
--checklist-only
```

---

## Planning

### When the goal is vague

> "I want to make our API faster but I don't know where to start"

```text
Mode: plan
Goal: reduce API p95 latency
```

Codex scans the repo, suggests metric/scope/verify, dry-runs the command, outputs a ready-to-use config.

### Performance-focused planning

> "Help me figure out how to optimize database queries"

```text
Mode: plan
Goal: optimize database query performance
```

### Quality-focused planning

> "I want to clean up Go compiler warnings but not sure which ones matter"

```text
Mode: plan
Goal: eliminate all compiler warnings in the Go codebase
```

---

## Advanced Patterns

### Guard as regression prevention

> "Simplify the utility module but don't break anything"

Optimize a metric without breaking existing behavior:

```text
Goal: Simplify utility module (reduce LOC)
Scope: src/utils/**/*.ts
Metric: total lines of code
Direction: lower
Verify: find src/utils -name "*.ts" | xargs wc -l | tail -1
Guard: npx tsc --noEmit && npm test
```

### Compound guard

Chain multiple safety checks:

```text
Guard: cargo clippy && cargo test && cargo doc --no-deps
```

### Debug -> Fix pipeline

> "Find what's causing 503s, then fix it"

First find bugs, then repair them:

```text
Mode: debug
Scope: src/api/**/*.ts
Symptom: intermittent 503 errors under concurrent requests
Iterations: 15
```

Then:

```text
Mode: fix
--from-debug
Iterations: 30
```

### Plan -> Execute pipeline

> "I'm not sure how to approach this, help me plan first"

Figure out the config, then run it:

```text
Mode: plan
Goal: reduce API p95 latency
```

Copy the generated config block and run it directly.

### Security audit -> Fix pipeline

> "Audit the code and fix anything critical"

Audit and remediate in one pass:

```text
Mode: security
--fix
Iterations: 15
```
