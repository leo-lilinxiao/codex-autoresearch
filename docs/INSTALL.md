# Installation

`codex-autoresearch` is a Markdown-first Codex skill package with bundled helper scripts. No build step, no third-party runtime dependencies.

## Prerequisites

- Codex with skills enabled.
- macOS or Linux.
- Git for iterative modes, because the loop commits, verifies, and reverts experiments.
- Python 3.11+ for the bundled helper scripts.
- A working `codex` CLI in `PATH` for managed background runs and `exec` mode.

> [!IMPORTANT]
> Recommended launch command:
>
> ```bash
> codex --enable goals --enable hooks --dangerously-bypass-approvals-and-sandbox
> ```
>
> Use this before starting autoresearch for the smoothest foreground and background experience.

## Install

### Via Skill Installer (recommended)

In Codex, run:

```text
$skill-installer install https://github.com/leo-lilinxiao/codex-autoresearch
```

Restart Codex after installation.

### Option A: Clone into a repository

```bash
git clone https://github.com/leo-lilinxiao/codex-autoresearch.git
cp -r codex-autoresearch your-project/.agents/skills/codex-autoresearch
```

### Option B: Install for all projects (user scope)

```bash
git clone https://github.com/leo-lilinxiao/codex-autoresearch.git
cp -r codex-autoresearch ~/.agents/skills/codex-autoresearch
```

### Option C: Symlink for live development

```bash
git clone https://github.com/leo-lilinxiao/codex-autoresearch.git
ln -s $(pwd)/codex-autoresearch your-project/.agents/skills/codex-autoresearch
```

Codex supports symlinked skill folders. Edits to the source repo take effect immediately.

## Skill Discovery Locations

Codex scans these directories for skills:

| Scope | Location | Use case |
|-------|----------|----------|
| Repo (CWD) | `$CWD/.agents/skills/` | Skills for the current working directory |
| Repo (parent) | `$CWD/../.agents/skills/` | Shared skills in a parent folder (monorepo) |
| Repo (root) | `$REPO_ROOT/.agents/skills/` | Root skills available to all subfolders |
| User | `~/.agents/skills/` | Personal skills across all projects |
| Admin | `/etc/codex/skills/` | Machine-wide defaults for all users |
| System | Bundled with Codex | Built-in skills by OpenAI |

## Verify Installation

Open Codex in the target repo and verify:

1. Type `$` and confirm `codex-autoresearch` appears in the skill list.
2. Invoke the skill:

```text
$codex-autoresearch
I want to reduce my failing tests to zero
```

Expected behavior:

- Codex recognizes the skill,
- loads `SKILL.md`,
- loads the relevant workflow for the request,
- and collects any missing fields via the wizard.

## Codex Integration

Autoresearch includes a small Codex integration for continuity across reopen, resume, stop, and background handoff. The skill prepares it automatically after it scans the repo and before it asks launch questions. You normally do not need to run anything yourself. If you want to preinstall or inspect it manually:

```bash
python3 /absolute/path/to/codex-autoresearch/scripts/autoresearch_hooks_ctl.py install
```

Inspect the current state first if you want:

```bash
python3 /absolute/path/to/codex-autoresearch/scripts/autoresearch_hooks_ctl.py status
```

What it does:

- `SessionStart` restores the short runtime checklist when you reopen or resume an autoresearch run.
- `Stop` lets Codex continue only when the autoresearch run still looks active/resumable.

Important:

- They only attach to conversations that clearly look like `codex-autoresearch` work; unrelated Codex conversations in the same repo are left alone.
- The recommended launch command above gives both foreground and background runs the intended capabilities from the start.
- Managed `background` runs keep their workspace-owned Results directory attached automatically.

## Updating

If installed by copy: re-clone and replace the installed folder.

If installed by symlink: `git pull` in the source repo. Changes are live immediately.

If an update does not appear, restart Codex.

## Disable Without Deleting

Use `~/.codex/config.toml`:

```toml
[[skills.config]]
path = "/absolute/path/to/codex-autoresearch/SKILL.md"
enabled = false
```

Restart Codex after changing the config.
