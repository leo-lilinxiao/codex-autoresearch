<p align="center">
  <img src="image/banner.png" width="700" alt="Codex Autoresearch">
</p>

<h2 align="center"><b>Aim. Iterate. Arrive.</b></h2>

<p align="center">
  <i>Autonomous goal-driven experimentation for Codex.</i>
</p>

<p align="center">
  <a href="https://developers.openai.com/codex/skills"><img src="https://img.shields.io/badge/Codex-Skill-blue?logo=openai&logoColor=white" alt="Codex Skill"></a>
  <a href="https://github.com/leo-lilinxiao/codex-autoresearch"><img src="https://img.shields.io/github/stars/leo-lilinxiao/codex-autoresearch?style=social" alt="GitHub Stars"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="MIT License"></a>
</p>

<p align="center">
  <b>English</b> ·
  <a href="docs/i18n/README_ZH.md">🇨🇳 中文</a> ·
  <a href="docs/i18n/README_JA.md">🇯🇵 日本語</a> ·
  <a href="docs/i18n/README_KO.md">🇰🇷 한국어</a> ·
  <a href="docs/i18n/README_FR.md">🇫🇷 Français</a> ·
  <a href="docs/i18n/README_DE.md">🇩🇪 Deutsch</a> ·
  <a href="docs/i18n/README_ES.md">🇪🇸 Español</a> ·
  <a href="docs/i18n/README_PT.md">🇧🇷 Português</a> ·
  <a href="docs/i18n/README_RU.md">🇷🇺 Русский</a>
</p>

---

The idea: tell Codex what you want to improve, then walk away. It modifies your code, verifies the result, keeps or discards, and repeats. You come back to a log of experiments and a better codebase.

Inspired by [Karpathy's autoresearch](https://github.com/karpathy/autoresearch), generalized beyond ML to anything you can verify mechanically: test coverage, type errors, latency, lint warnings, security findings, release readiness — if a command can tell whether it improved, the loop can iterate on it.

## Quick Start

```text
# Install in Codex (recommended)
$skill-installer install https://github.com/leo-lilinxiao/codex-autoresearch
```

Restart Codex, open your project, and go:

```
You:   $codex-autoresearch
       I want to get rid of all the `any` types in my TypeScript code

Codex: I found 47 `any` occurrences across src/**/*.ts.
       Results directory: ./autoresearch-results/
       Metric: `any` count (current: 47), direction: lower
       Verify: grep count + tsc --noEmit as guard
       Run mode: foreground or background?

You:   Background, go. Run overnight.

Codex: Starting background run — baseline: 47. Iterating.
```

Each improvement stacks. Each failure reverts. Everything is logged.

See [INSTALL.md](docs/INSTALL.md) for manual copy, symlink, and user-scope options. See [GUIDE.md](docs/GUIDE.md) for the full manual.

## How It Works

```
You say one sentence  →  Codex scans & confirms  →  You say "go"
                                                        |
                                         +--------------+--------------+
                                         |                             |
                                    foreground                    background
                                  (current session)            (detached, overnight)
                                         |                             |
                                         +--------------+--------------+
                                                        |
                                                        v
                                              +-------------------+
                                              |    The Loop       |
                                              |                   |
                                              |  modify one thing |
                                              |  git commit       |
                                              |  run verify       |
                                              |  improved? keep   |
                                              |  worse? revert    |
                                              |  log the result   |
                                              |  repeat           |
                                              +-------------------+
```

That's it. You pick one: foreground keeps the loop in your current session, background hands it off to a detached process so you can sleep. Same loop either way, but they don't run at the same time.

## What You Say vs What Happens

| You say | What happens |
|---------|-------------|
| "Improve my test coverage" | Iterates until target or interrupted |
| "Fix the 12 failing tests" | Repairs one by one until zero remain |
| "Why is the API returning 503?" | Hunts root cause with falsifiable hypotheses |
| "Is this code secure?" | STRIDE + OWASP audit, every finding backed by code evidence |
| "Ship it" | Verifies readiness, generates checklist, gates release |
| "I want to optimize but don't know what" | Analyzes repo, suggests metrics, generates config |

Behind the scenes, Codex maps your sentence to one of 7 modes (loop, plan, debug, fix, security, ship, exec). You never need to pick one.

## What Codex Figures Out

You don't write config. Codex infers everything from your sentence and your repo:

| What it needs | How it gets it | Example |
|--------------|----------------|---------|
| Goal | Your sentence | "get rid of all any types" |
| Scope | Scans repo structure | `src/**/*.ts` |
| Metric | Proposes based on goal + tooling | any count (current: 47) |
| Direction | Infers from "improve" / "reduce" / "eliminate" | lower |
| Verify | Matches to repo tooling | `grep` count + `tsc --noEmit` |
| Guard | Suggests if regression risk exists | `npm test` |

Before starting, Codex always shows what it found and asks you to confirm. Then you choose foreground or background and say "go."
By default, the Results directory stays in the launch context: if you started Codex inside a git repo, that repo root is the default workspace root; if you started outside a git repo, the current launch directory is the default workspace root. Codex should not silently widen that to a parent directory unless you explicitly confirm a broader multi-repo workspace. The confirmation summary should always show the chosen Results directory before launch.

## When It Gets Stuck

Instead of blind retrying, the loop escalates:

| Trigger | Action |
|---------|--------|
| 3 consecutive failures | **REFINE** — adjust within current strategy |
| 5 consecutive failures | **PIVOT** — try a fundamentally different approach |
| 2 PIVOTs without progress | **Web search** — look for external solutions |
| 3 PIVOTs without progress | **Stop** — report that human input is needed |

One success resets all counters.

## Results Log

Every iteration is recorded in the workspace Results directory at `autoresearch-results/results.tsv`:

```
iteration  commit   metric  delta   status    description
0          a1b2c3d  47      0       baseline  initial any count
1          b2c3d4e  41      -6      keep      replace any in auth module
2          -        49      +8      discard   generic wrapper introduced new anys
3          d4e5f6g  38      -3      keep      type-narrow API response handlers
```

Failed experiments revert from git but stay in the log. The log is the real audit trail, while `autoresearch-results/state.json` is the resume snapshot.

## More Features

These are covered in detail in [GUIDE.md](docs/GUIDE.md):

- **Cross-run learning** — lessons from past runs bias future hypothesis generation
- **Parallel experiments** — test up to 3 hypotheses simultaneously via git worktrees
- **Session resume** — interrupted runs pick up from the last consistent state
- **CI/CD mode** (`exec`) — non-interactive, JSON output, for automation pipelines
- **Dual-gate verification** — separate verify (did it improve?) and guard (did anything break?)
- **Session hooks** — auto-installed; keep Codex on track across session boundaries

## FAQ

**It only makes small incremental changes. Can it try bigger ideas?**
By default the loop favors small, verifiable steps — that's by design. But it can go bigger: describe a larger hypothesis in your prompt (e.g., "try replacing the attention mechanism with linear attention and run the full eval"), and it will treat that as a single experiment to verify. The loop is best when the human sets the research direction and the agent does the heavy execution and analysis.

**Is this more for engineering optimization than research?**
It's strongest when the goal and metric are clear — push coverage up, push errors down, push latency lower. For open-ended research where the direction itself is uncertain, use `plan` mode first to explore, then switch to `loop` once you know what to measure. Think of it as a human-AI collaboration: you provide judgment, it provides iteration speed.

**How do I stop it?** Foreground: interrupt Codex. Background: `$codex-autoresearch` then ask to stop.

**Can it resume after interruption?** Yes. It resumes from `autoresearch-results/state.json` automatically.

**How do I use it in CI?** `Mode: exec` with `codex exec`. All config upfront, JSON output, exit codes 0/1/2.

## Documentation

| Doc | What it covers |
|-----|---------------|
| [INSTALL.md](docs/INSTALL.md) | All installation methods, skill discovery paths, hooks setup |
| [GUIDE.md](docs/GUIDE.md) | Full operator's manual: modes, config fields, safety model, advanced usage |
| [EXAMPLES.md](docs/EXAMPLES.md) | Recipes by domain: coverage, performance, types, security, etc. |

## Acknowledgments

Built on ideas from [Karpathy's autoresearch](https://github.com/karpathy/autoresearch). The Codex skills platform is by [OpenAI](https://openai.com).

## Star History

<a href="https://www.star-history.com/?repos=leo-lilinxiao%2Fcodex-autoresearch&type=timeline&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/image?repos=leo-lilinxiao/codex-autoresearch&type=timeline&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/image?repos=leo-lilinxiao/codex-autoresearch&type=timeline&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/image?repos=leo-lilinxiao/codex-autoresearch&type=timeline&legend=top-left" />
 </picture>
</a>

## License

MIT — see [LICENSE](LICENSE).
