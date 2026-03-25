# Contributing to codex-autoresearch

This project is a Markdown-first Codex skill with a small set of helper scripts and stdlib tests. There is still no build step and no runtime dependency installation. Most changes are `.md` edits, but stateful behavior now also lives in `scripts/` and is validated by `tests/`.

## How the skill is structured

Codex loads `SKILL.md` first. That file contains mode routing, hard rules, and a load order that pulls in reference files on demand:

```
SKILL.md  (always loaded -- entrypoint)
  |
  +-- references/core-principles.md         (always loaded)
  +-- references/structured-output-spec.md  (always loaded)
  +-- references/session-resume-protocol.md (check for prior run)
  +-- references/environment-awareness.md   (probe hardware/toolchains)
  +-- references/autonomous-loop-protocol.md (loaded for iterating modes)
  +-- references/interaction-wizard.md       (loaded for every new interactive launch)
  +-- references/{mode}-workflow.md          (loaded per mode)
  +-- references/results-logging.md          (loaded when logging is needed)
  +-- references/lessons-protocol.md         (loaded for iterating modes)
  +-- references/pivot-protocol.md           (loaded for iterating modes)
  +-- references/health-check-protocol.md    (loaded for iterating modes)
  +-- references/hypothesis-perspectives.md  (loaded when beneficial)
  +-- references/parallel-experiments-protocol.md (loaded when parallel enabled)
  +-- references/web-search-protocol.md      (loaded when web search enabled)
  +-- references/modes.md                    (mode index)
```

This progressive disclosure means Codex only reads what it needs. A loop-mode invocation never loads the ship workflow. A plan-mode invocation never loads the results log spec.

The user-facing documentation lives in separate files:

```
README.md / docs/i18n/README_*.md    -- public overview
docs/GUIDE.md                        -- operator's manual
docs/EXAMPLES.md                     -- real-world recipes
docs/INSTALL.md                      -- installation options
```

## Development workflow

1. Fork and clone the repo.

2. Symlink into a test project so edits take effect immediately:

```bash
ln -s /path/to/your/fork your-project/.agents/skills/codex-autoresearch
```

3. Open Codex in the test project, type `$codex-autoresearch`, and verify the skill activates.

4. Make your changes. Test by invoking the skill in different scenarios. Do not treat the stdlib tests as the whole acceptance bar for behavior changes.

5. When satisfied, remove the symlink and submit a PR.

## Where to make changes

The project has two layers: the **skill layer** (what Codex reads) and the **documentation layer** (what humans read). Changes often touch both.

**Skill layer -- how Codex behaves:**

| If you want to change... | Edit this file |
|--------------------------|---------------|
| Which modes exist, how they route | `SKILL.md` |
| How the core loop works (phases, rollback, stuck recovery) | `references/autonomous-loop-protocol.md` |
| How Codex asks users for information before starting | `references/interaction-wizard.md` |
| How a specific mode behaves | `references/{mode}-workflow.md` |
| What output gets produced | `references/structured-output-spec.md` |
| Universal design principles | `references/core-principles.md` |
| TSV log format | `references/results-logging.md` |
| Cross-run learning | `references/lessons-protocol.md` |
| Stuck recovery escalation | `references/pivot-protocol.md` |
| Web search behavior | `references/web-search-protocol.md` |
| Environment detection | `references/environment-awareness.md` |
| Parallel experiments | `references/parallel-experiments-protocol.md` |
| Session resume | `references/session-resume-protocol.md` |
| Health monitoring | `references/health-check-protocol.md` |
| Hypothesis reasoning | `references/hypothesis-perspectives.md` |

**Documentation layer -- what humans see:**

| If you want to change... | Edit this file |
|--------------------------|---------------|
| The project overview and quick start | `README.md` + `docs/i18n/README_*.md` |
| Detailed usage instructions | `docs/GUIDE.md` |
| Copy-paste recipes and worked examples | `docs/EXAMPLES.md` |
| Installation methods | `docs/INSTALL.md` |

When a skill-layer change affects user-visible behavior, update the documentation layer too.

## Adding a new mode

1. Create `references/yourmode-workflow.md`. Include: purpose, trigger phrases, phases with rules, output format, and a two-phase boundary statement at the top.

2. Add the mode to the table in `SKILL.md` and to the classification list in "When Activated."

3. Add it to `references/modes.md` and update the Shared Expectations list if needed.

4. Add field mappings to `references/interaction-wizard.md` so the wizard knows how to guide users into this mode.

5. Add a section to `README.md`, update the maintained `docs/i18n/README_*.md` files, update `docs/GUIDE.md`, and add at least one recipe to `docs/EXAMPLES.md`.

6. Run `bash scripts/validate_skill_structure.sh` to verify the file structure.

## Submitting a PR

Use [conventional commit](https://www.conventionalcommits.org/) format for titles:

- `feat:` -- new functionality (mode, feature, recipe)
- `fix:` -- corrects wrong behavior in skill instructions
- `docs:` -- documentation-only changes
- `refactor:` -- reorganizes content without changing behavior

In the PR body, explain what changed and how to test it. A good test is: symlink the branch into a project, invoke `$codex-autoresearch` with a relevant prompt, and observe whether Codex follows the updated instructions.

Keep PRs focused. One logical change per PR.

## What makes a good contribution

**High-value contributions:**

- Recipes for domains not yet covered in docs/EXAMPLES.md
- Improvements to the interaction wizard (better questions, better defaults)
- Protocol refinements backed by real-world testing (e.g., "the PIVOT threshold should account for near-miss iterations")
- Translations of documentation to new languages
- Bug reports with reproduction steps ("I said X, Codex did Y, expected Z")

**Please avoid:**

- Reformatting or restyling existing files without functional changes
- Adding verbose comments or explanations for self-evident content
- Bumping version numbers (maintainers handle releases)

## Contributor Gate

The automated tests are real and useful, but they do **not** all validate the same layer:

- `tests/autoresearch/` executes the helper scripts directly and checks TSV/JSON semantics.
- `tests/test_check_skill_invariants.py` validates the invariant checker itself.
- `bash scripts/run_skill_e2e.sh exec-smoke --clean` runs the real skill through `codex exec` in a disposable fixture repo.
- `bash scripts/run_skill_e2e.sh runtime-smoke --clean` automatically exercises the detached runtime launch/status/stop handoff with an installed skill copy and a fake Codex binary.

That means `python3 -m unittest ...` alone is not enough to prove the skill still works end to end.

Use this gate table:

| Change type | Minimum gate |
|-------------|--------------|
| Docs-only wording, examples, translations | `bash scripts/run_contributor_gate.sh docs` |
| Any `scripts/`, `SKILL.md`, `references/`, invariant, or artifact/state semantics change | `bash scripts/run_contributor_gate.sh skill` |
| Wizard / ask-before-act / `"go"` boundary / interactive loop behavior | `bash scripts/run_contributor_gate.sh skill` **plus** `bash scripts/run_skill_e2e.sh interactive-smoke` |

The `interactive-smoke` harness prints the exact manual verification steps. Keep it manual for conversational behavior that the automated gate cannot prove. The detached runtime handoff itself is now covered automatically by `runtime-smoke`.

## Validating your changes

```bash
bash scripts/run_contributor_gate.sh docs
bash scripts/run_contributor_gate.sh skill
```

`docs` is the lightweight structure check. `skill` is the real automated contributor gate: structure validation, helper/invariant unit tests, and a disposable `codex exec` smoke run.

For real skill-level validation against Codex CLI itself:

```bash
bash scripts/run_skill_e2e.sh exec-smoke
bash scripts/run_skill_e2e.sh runtime-smoke
bash scripts/run_skill_e2e.sh interactive-smoke
```

`exec-smoke` runs the real skill through `codex exec` in a disposable fixture repo and checks artifact invariants. `runtime-smoke` automatically exercises the installed-skill detached runtime handoff. `interactive-smoke` prepares a disposable repo and prints the exact manual wizard/`go` smoke-test steps for the still-human conversational layer.

For interactive behavioral validation, there is no fully automated suite. The skill is Markdown instructions plus helper scripts -- the only way to test wizard and autonomy boundaries is to use it. Symlink your branch, invoke the skill with various prompts, and verify Codex follows the updated instructions.

Edge cases worth trying:

- Invoke with no context ("$codex-autoresearch" and nothing else) -- does the wizard activate?
- Invoke with a complete goal -- does the wizard still ask at least one confirming question?
- Let the loop run for 5+ iterations -- does it behave correctly on keep, discard, and crash?

## Architecture decisions to be aware of

- **Progressive disclosure** is intentional. Do not move reference content into SKILL.md. The entrypoint should stay small.
- **The two-phase boundary** is a core design constraint. Everything before "go" can ask the user. Everything after "go" must be fully autonomous.
- **Natural language is the primary interface.** Users should never need to know field names or write structured config. The wizard handles translation.
- **Rollback must match the pre-launch approval.** In an isolated experiment branch/worktree, approved `git reset --hard HEAD~1` is allowed; otherwise use `git revert --no-edit HEAD`.
- **Lessons are additive.** Cross-run learning persists across sessions. Never delete lessons without user consent.
- **PIVOT/REFINE replaces brute-force retrying.** Stuck recovery should always escalate through the defined ladder.

## License

MIT. Contributions are made under the same license.
