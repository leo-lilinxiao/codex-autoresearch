# Security Workflow

Structured security audit that combines code reconnaissance, STRIDE threat modeling, OWASP coverage, adversarial review lenses, attack-surface mapping, and evidence-backed findings.

**Two-phase boundary:** All clarifying questions happen before launch. Once the user says "go", this workflow is fully autonomous -- never pause to ask the user anything. If you encounter ambiguity, apply best practices and keep going.

## Purpose

Use this mode for a read-only audit first, then optional repair.

## Trigger

- `$codex-autoresearch Mode: security`
- "security audit"
- "find vulnerabilities"
- "threat model this"
- "red-team this app"

## Flags

| Flag | Purpose |
|------|---------|
| `--scope "<glob>"` | Restrict audit scope |
| `--focus "<text>"` | Bias toward a subsystem or risk theme |
| `--diff` | Audit only changes since the last audit artifact |
| `--fix` | After reporting, attempt to remediate confirmed critical or high findings |
| `--fail-on critical|high|medium` | Return failure if findings at or above threshold remain |
| `--iterations N` | Bound the audit loop |

## Wizard

If scope or audit intent is missing, collect:

- scope,
- depth,
- action after findings.

## Setup

### Step 1: Recon

Inspect:

- dependencies,
- config files,
- API routes,
- auth and middleware,
- storage layers,
- CI and deployment configs.

### Step 2: Assets

Catalog:

- user data,
- credentials and tokens,
- admin functions,
- external services,
- file and network entry points.

### Step 3: Trust Boundaries

Map boundaries such as:

- browser <-> server,
- public <-> authenticated,
- user <-> admin,
- app <-> database,
- app <-> third-party services,
- CI <-> production.

### Step 4: Threat Model

Build a threat model and attack surface map.

Recommended categories:

- spoofing
- tampering
- repudiation
- information disclosure
- denial of service
- elevation of privilege

### Image Input

Security mode accepts image input during the wizard phase:

- **Architecture diagrams:** identify trust boundaries, data flows, and attack surfaces from visual representations.
- **Network topology:** map external entry points and internal communication paths.

When an image is provided:
1. Analyze the image to extract architectural information.
2. Use extracted information to inform trust boundary mapping (Step 3) and threat modeling (Step 4).
3. Reference the image findings in the attack surface map.

### Step 5: Adversarial Lenses

Exercise the audit from these lenses:

- application attacker
- supply-chain attacker
- insider with partial access
- infrastructure attacker

Do not stay in a single mindset for the whole run. Rotate lenses as the attack surface changes.

## Loop

Per iteration:

1. select the next untested attack vector from the STRIDE map, OWASP set, or adversarial lens backlog,
2. analyze the relevant code path,
3. validate with code evidence,
4. classify severity, STRIDE category, and OWASP category where applicable,
5. log the result.

## Findings Rules

Every finding must include:

- location,
- attack scenario,
- impact,
- confidence,
- STRIDE category,
- OWASP category when applicable,
- mitigation.

Do not report purely theoretical issues without code evidence.

## Output Directory

```text
security/{YYMMDD}-{HHMM}-{slug}/
  overview.md
  threat-model.md
  attack-surface-map.md
  findings.md
  coverage.md
  dependency-audit.md
  recommendations.md
  security-audit-results.tsv
```

## Coverage

Track:

- STRIDE categories covered,
- OWASP Top 10 categories covered,
- adversarial lenses exercised,
- dependency audit completion,
- finding severity distribution,
- audit progress every 5 iterations.

## Bounded Audit Score

For bounded runs, summarize progress with a simple composite score:

```text
score = (stride_covered / 6) * 35
      + (owasp_covered / 10) * 35
      + min(findings_confirmed, 15) * 2
```

This score is only a progress indicator. It does not replace finding severity.

## Gating

If `--fail-on` is set:

- run the audit,
- evaluate the remaining findings,
- return failure when the threshold is met or exceeded.

## Auto-Fix

If `--fix` is set:

- switch to a repair loop for confirmed critical or high findings only,
- verify that existing tests and guards still pass,
- update `findings.md` with status markers.
