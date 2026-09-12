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

Tell Codex what measurable result you want. Codex inspects the repository, confirms the experiment with you, changes one thing, verifies it, keeps improvements, reverts failures, and repeats until the target is reached.

Autoresearch works for test failures, coverage, type errors, warnings, latency, binary size, reproducible security findings, and any other outcome a command can measure.

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

Codex launches the confirmed run. No Codex configuration changes or special prompt syntax are required.

See [Installation](docs/INSTALL.md) for manual and development installs.

## The Loop

```text
inspect evidence
      |
change one focused thing
      |
commit and measure
      |
      +-- improved + guard passes --> keep
      |
      +-- otherwise ---------------> revert
      |
append an audit event
      |
repeat until target
```

The control script owns commits, verification, rollback, and state. Codex owns the hypotheses and code changes.

## Foreground And Background

| | Foreground | Background |
|---|---|---|
| Runs in | Current Codex task | Detached controller |
| Continuation | Official Codex Goal | One `codex exec` worker per iteration |
| Best for | Watching and steering live | Long or overnight runs |
| Control | Codex Goal pause/resume | Ask `$codex-autoresearch` for status, stop, or resume |

Foreground and background use the same experiment rules. A run uses one mode at a time. Foreground continuation uses a Codex Goal; background continuation belongs to the detached controller.

## What Gets Confirmed

Before the first write, Codex shows:

- the goal and numeric target;
- repository-relative paths it may change;
- the metric command and explicit parser;
- an optional regression guard;
- foreground or background mode;
- an optional iteration limit.

Initialization requires a clean named Git branch. One run manages one repository.

Codex reuses choices and approval you have already given. Once the experiment is confirmed, it keeps working without asking you to approve each iteration.

## Results

Run artifacts live in `autoresearch-results/` and stay uncommitted:

| Path | Purpose |
|---|---|
| `run.json` | Immutable confirmed configuration |
| `events.jsonl` | Append-only baseline, iteration, stop, and completion history |
| `logs/` | Full metric, guard, and background worker output |
| `runtime.json` | Background process state |
| `runtime.log` | Background controller lifecycle events |
| `report.html` | Optional, regenerated visual snapshot |

`events.jsonl` is the state history. Missing, malformed, contradictory, or partial state is an error; the skill never guesses a result from old files or conversational memory.

## Review Results

Ask the skill to show the validated experiment history:

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

The same validated events can be exported as TSV or rendered as a self-contained static report:

```text
$codex-autoresearch export experiment history as TSV
$codex-autoresearch generate an HTML report
```

The report is written to `autoresearch-results/report.html`. It is a replaceable snapshot, not runtime state.

<p align="center">
  <img src="image/autoresearch-report.png" width="900" alt="Codex Autoresearch HTML report showing metric trajectory and experiment history">
</p>

## Safety Model

- Every trial is a Git commit.
- A non-improving trial or failed guard is reverted with `git revert`.
- Out-of-scope edits, branch changes, HEAD drift, malformed metrics, command failures, timeouts, and generated byproducts stop the run with an exact error and log path.
- Autoresearch artifacts are never staged.
- A run reports `complete` only when the retained metric reaches the confirmed target.
- A genuine external blocker is reported explicitly; a difficult or unsuccessful hypothesis is not treated as blocked.

This strictness is intentional. Silent recovery makes long autonomous runs impossible to trust.

## Good Metrics

The verify command must exit successfully and place one finite number on its final non-empty stdout line. It may instead print a JSON object on that line when Codex names one numeric key explicitly.

```text
7
```

```json
{"error_count": 7, "passed": 12}
```

Use a guard for behavior the metric does not protect, such as a test suite around a latency benchmark. The guard must pass at baseline.

## Documentation

| Guide | Contents |
|---|---|
| [Installation](docs/INSTALL.md) | Install, update, and verify the skill |
| [User Guide](docs/GUIDE.md) | Configuration, lifecycle, state, and troubleshooting |
| [Examples](docs/EXAMPLES.md) | Practical prompts and metric patterns |
| [Contributing](CONTRIBUTING.md) | Architecture and validation for contributors |

## FAQ

**Does installation change my Codex settings?**

No. Installation copies the skill files. Use a current Codex release so foreground runs can use the built-in Goal capability.

**Why Full Access?**

Each iteration creates or reverts a Git commit. Restricted sandboxes may block writes under `.git`. Background runs therefore default to Full Access; `workspace-write` remains an explicit option when its limitations are acceptable.

**Can I stop and resume?**

Yes. Interrupt or pause a foreground Goal. For background, invoke `$codex-autoresearch` and ask for status, stop, or resume. A new direction is optional; "resume" continues the confirmed experiment.

**Can it run without Git or across several repos?**

No. Git is the experiment memory and rollback boundary. Use one run per repository so commit ownership and metrics remain unambiguous.

**Is this only for small changes?**

No. One experiment should test one coherent hypothesis. Its size should match the hypothesis, while still being independently measurable and reversible.

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
