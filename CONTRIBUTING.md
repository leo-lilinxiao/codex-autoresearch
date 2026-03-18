# Contributing

codex-autoresearch is a Markdown-first skill package. Everything is `.md` files -- no build step, no compilation.

---

## Setup for Development

```bash
# clone
git clone https://github.com/leo-lilinxiao/codex-autoresearch.git
cd codex-autoresearch

# symlink into a test project for live editing
ln -s $(pwd) your-project/.agents/skills/codex-autoresearch

# verify: open Codex in the test project, type $, confirm the skill appears
```

When done, replace the symlink with a copy if needed:
```bash
rm your-project/.agents/skills/codex-autoresearch
cp -r codex-autoresearch your-project/.agents/skills/codex-autoresearch
```

---

## Codebase Map

```
SKILL.md                         <- skill entrypoint, mode routing, hard rules
references/
  autonomous-loop-protocol.md    <- how the loop works (8 phases)
  core-principles.md             <- universal principles
  {mode}-workflow.md             <- per-mode specification
  interaction-wizard.md          <- interactive field collection
  structured-output-spec.md      <- output format contract
  modes.md                       <- mode index
  results-logging.md             <- TSV log format
agents/openai.yaml               <- Codex UI metadata (optional)
scripts/validate_skill_structure.sh  <- structure checker
```

### Ownership

| File | Owns | Touch when |
|------|------|------------|
| `SKILL.md` | Mode routing, activation triggers, hard rules | Adding/changing modes, changing defaults |
| `references/*-workflow.md` | Full behavior spec for one mode | Changing how a mode works |
| `references/autonomous-loop-protocol.md` | The 8-phase loop | Changing loop mechanics |
| `references/interaction-wizard.md` | Field collection UX | Changing setup flow |
| `references/structured-output-spec.md` | Output shapes | Changing what gets produced |
| `agents/openai.yaml` | UI display metadata | Changing how skill appears in Codex UI |
| `README.md` / `README_ZH.md` | Public-facing overview | Any user-visible change |
| `GUIDE.md` | Operator's manual | Any behavioral or config change |
| `EXAMPLES.md` | Copy-paste recipes | New domains, new patterns |

---

## How to Add a New Mode

1. **Write the spec**: create `references/yourmode-workflow.md` with full protocol, phases, rules, flags, error handling, and output format.

2. **Register in SKILL.md**: add to the modes table and the "When Activated" classification list.

3. **Update the index**: add to `references/modes.md`.

4. **Update wizard**: add mode-specific fields to `references/interaction-wizard.md` if needed.

5. **Update output spec**: add output template to `references/structured-output-spec.md`.

6. **Update docs**: add to README.md, README_ZH.md, GUIDE.md, EXAMPLES.md.

---

## Commit Conventions

[Conventional commits](https://www.conventionalcommits.org/):

| Prefix | Use for |
|--------|---------|
| `feat:` | New mode, new feature |
| `fix:` | Bug fix |
| `docs:` | Documentation only |
| `refactor:` | Restructuring without behavior change |
| `chore:` | Tooling, config, maintenance |

---

## Pull Requests

- One PR per logical change
- Branch from `main`, target `main`
- Use conventional commit format for the title
- Explain what changed, why, and how to test
- Update all affected docs (see ownership table above)
- Do not bump versions -- maintainers handle that

### PR body template

```
## What changed
- ...

## Files touched
| File | Change |
|------|--------|
| ... | ... |

## How to test
1. Symlink skill into a test project
2. Invoke: $codex-autoresearch Mode: ...
3. Verify: ...
```

---

## Testing

No automated tests -- this is Markdown instructions. Testing means using the skill:

1. Symlink your working tree into a test project
2. Open Codex
3. Invoke the skill with different configs
4. Verify behavior matches your changes
5. Try edge cases: empty scope, missing fields, failing guard

Run the structure validator:

```bash
bash scripts/validate_skill_structure.sh
```

---

## What to Contribute

**Valuable:**
- New domain recipes (EXAMPLES.md)
- Bug fixes in loop edge cases
- New modes with full specs
- OWASP/STRIDE additions for security mode
- Protocol improvements (stuck-detection, smarter ideation)

**Please don't:**
- Formatting-only changes
- Style/naming convention changes
- Whitespace edits
- Comments explaining obvious things

---

## Notes

- `SKILL.md` is the only entrypoint. Codex reads it first; references load on demand.
- Everything is MIT licensed. Your contributions will be too.
- Questions or ideas? Open an issue.
