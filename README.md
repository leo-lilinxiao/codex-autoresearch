<p align="center">
  <img src="image/banner.png" width="700" alt="Codex Autoresearch">
</p>

<h2 align="center"><b>Aim. Iterate. Arrive.</b></h2>

<p align="center">
  <i>Autonomous, measurable experimentation for Codex.</i>
</p>

<p align="center">
  <a href="https://developers.openai.com/codex/skills"><img src="https://img.shields.io/badge/Codex-Skill-blue?logo=openai&logoColor=white" alt="Codex Skill"></a>
  <a href="https://github.com/leo-lilinxiao/codex-autoresearch"><img src="https://img.shields.io/github/stars/leo-lilinxiao/codex-autoresearch?style=social" alt="GitHub Stars"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="MIT License"></a>
</p>

<p align="center">
  <b>English</b> ·
  <a href="docs/i18n/README_ZH.md">中文</a> ·
  <a href="docs/i18n/README_JA.md">日本語</a> ·
  <a href="docs/i18n/README_KO.md">한국어</a> ·
  <a href="docs/i18n/README_FR.md">Français</a> ·
  <a href="docs/i18n/README_DE.md">Deutsch</a> ·
  <a href="docs/i18n/README_ES.md">Español</a> ·
  <a href="docs/i18n/README_PT.md">Português</a> ·
  <a href="docs/i18n/README_RU.md">Русский</a>
</p>

---

Tell Codex which number you want to move and where it should end up. Codex looks through your repository, confirms the plan with you, and then works one change at a time: measure it, keep it if it helps, roll it back if it doesn't, and repeat until the target is reached.

It works for anything a command can measure: failing tests, coverage, type errors, warnings, latency, binary size, reproducible security findings, and so on.

## Quick Start

Install from Codex:

```text
$skill-installer install https://github.com/leo-lilinxiao/codex-autoresearch
```

Open a clean Git repository with Full Access:

```bash
codex --dangerously-bypass-approvals-and-sandbox
```

Then invoke the skill:

```text
You:   $codex-autoresearch
       Reduce `python3 scripts/score.py` error_count to 0.

Codex: Baseline: 5
       Target: 0 (lower is better)
       Scope: src/
       Verify: python3 scripts/score.py, JSON key error_count
       Guard: none
       Run in foreground or background?

You:   Background. Go.
```

Codex starts the run you confirmed. You don't need to change any Codex settings or learn special syntax.

See [Installation](docs/INSTALL.md) for manual and development installs.

## The Loop

```text
look at the evidence
      |
change one thing
      |
commit and measure
      |
      +-- improved + guard passes --> keep
      |
      +-- otherwise ---------------> revert
      |
record the result
      |
repeat until target
```

Codex decides what to try and writes the code. A small control script does the bookkeeping: commits, measurement, rollback, and the record of every experiment.

## Foreground And Background

| | Foreground | Background |
|---|---|---|
| Runs in | Current Codex task | Detached controller |
| Continuation | Official Codex Goal | One `codex exec` worker per iteration |
| Best for | Watching and steering live | Long or overnight runs |
| Control | Codex Goal pause/resume | Ask `$codex-autoresearch` for status, stop, or resume |

Both modes follow the same rules. What differs is what keeps the loop going: in the foreground, a Codex Goal in your current task; in the background, a separate controller that starts a fresh worker for each experiment. A run uses one mode at a time.

## What Gets Confirmed

Before it changes anything, Codex shows you:

- the goal and numeric target;
- repository-relative paths it may change;
- the command that measures the metric, and how to read its output;
- an optional regression guard;
- foreground or background mode;
- an optional iteration limit.

You need a clean, named Git branch to start, and each run covers one repository.

Codex won't ask again about anything you've already decided. Once you confirm, it keeps going without asking you to approve each experiment.

## Results

Everything the run records goes in `autoresearch-results/`, which is never committed:

| Path | Purpose |
|---|---|
| `run.json` | The settings you confirmed; never changes |
| `events.jsonl` | Every baseline, experiment, stop, and completion, in order; only appended to |
| `logs/` | Full metric, guard, and background worker output |
| `runtime.json` | Background process state |
| `runtime.log` | What the background controller did |
| `report.html` | Optional visual report, rebuilt on request |

`events.jsonl` is the source of truth. If it's missing or damaged, the skill stops and says so. It never guesses results from old files or from the conversation.

## Review Results

Ask the skill for the history:

```text
$codex-autoresearch show experiment history
```

```text
Codex Autoresearch
Run: 0a516883  Status: complete  Mode: foreground
Metric: error_count  2 -> 0  Target: 0 (lower is better)

SEQ  ITER  EVENT     PREVIOUS  TRIAL  RETAINED  DESCRIPTION
---  ----  --------  --------  -----  --------  ------------------------------------
  0     0  baseline         -      -         2  Initial measurement
  1     1  discard          2      3         2  Broaden parser fallback
  2     2  keep             2      1         1  Fix nested parser branch
  3     3  keep             1      0         0  Remove final parser error
  4     3  complete         -      -         0  retained metric satisfies the target
```

You can also export it as TSV or get a self-contained HTML report:

```text
$codex-autoresearch export experiment history as TSV
$codex-autoresearch generate an HTML report
```

The report goes to `autoresearch-results/report.html`. It's only a snapshot, so delete or regenerate it whenever you like.

<p align="center">
  <img src="image/autoresearch-report.png" width="900" alt="Codex Autoresearch HTML report showing metric trajectory and experiment history">
</p>

## Safety Model

- Every experiment is a Git commit.
- If it doesn't improve the metric or fails the guard, it is rolled back with `git revert`.
- Edits outside the scope, a switched branch or moved HEAD, invalid metric output, command errors, timeouts, and commands that leave files behind stop the run with diagnostics.
- Leave the run's checkout alone until it stops: anything you edit inside the scope gets committed with the current experiment. To keep working, use a separate `git worktree`.
- The results folder is never staged.
- A run is `complete` only when the kept result actually reaches the target.
- `blocked` is reserved for real outside problems, such as missing credentials or data. A hard problem or a failed idea is not a blocker.

This is strict on purpose. If a long unattended run quietly papered over problems, you couldn't trust its results.

## Good Metrics

The verify command has to exit successfully and print one finite number on its last non-empty stdout line. It can print a JSON object there instead, as long as Codex names the numeric key to read.

```text
7
```

```json
{"error_count": 7, "passed": 12}
```

Use a guard for anything the metric doesn't cover, such as running the test suite while you optimize latency. The guard has to pass before the run starts.

Keep the verify script and its data out of the scope, so experiments can't change how they are measured. If the same code gives different numbers from run to run, report the median of several runs.

## Documentation

| Guide | Contents |
|---|---|
| [Installation](docs/INSTALL.md) | Install, update, and verify the skill |
| [User Guide](docs/GUIDE.md) | Setup, how runs work, and troubleshooting |
| [Examples](docs/EXAMPLES.md) | Practical prompts and metric patterns |
| [Contributing](CONTRIBUTING.md) | Architecture and validation for contributors |

## FAQ

**Does installation change my Codex settings?**

No. It only copies the skill files. You do need a recent Codex release, because foreground runs rely on Codex Goals.

**Why Full Access?**

Every experiment makes or reverts a Git commit, and restricted sandboxes may block writes under `.git`. So background runs default to Full Access. You can still choose `workspace-write` if you accept that Git writes may fail.

**Can I stop and resume?**

Yes. In the foreground, interrupt or pause the Goal. In the background, ask `$codex-autoresearch` for status, stop, or resume. Just saying "resume" continues the same experiment; you can add a new direction if you like.

**Can it run without Git or across several repos?**

No. Git is how the run remembers what it tried and how it rolls back. One run per repository keeps it clear which commits and numbers belong to which run.

**Is this only for small changes?**

No. Each experiment tests one idea, and it can be as big as that idea needs, as long as it can be measured and rolled back on its own.

## Acknowledgments

Inspired by [Karpathy's autoresearch](https://github.com/karpathy/autoresearch), generalized for Codex and software repositories.

## Citation

```bibtex
@misc{codex-autoresearch,
  author = {Li, Linxiao},
  title = {Codex Autoresearch: Autonomous Goal-Driven Experimentation for Codex},
  year = {2026},
  publisher = {GitHub},
  url = {https://github.com/leo-lilinxiao/codex-autoresearch}
}
```

GitHub also reads [CITATION.cff](CITATION.cff) for its **Cite this repository** menu.

## Star History

<a href="https://www.star-history.com/?repos=leo-lilinxiao%2Fcodex-autoresearch&type=timeline&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/image?repos=leo-lilinxiao/codex-autoresearch&type=timeline&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/image?repos=leo-lilinxiao/codex-autoresearch&type=timeline&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/image?repos=leo-lilinxiao/codex-autoresearch&type=timeline&legend=top-left" />
 </picture>
</a>

## License

MIT, see [LICENSE](LICENSE).
