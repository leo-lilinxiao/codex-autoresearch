# Installation

`codex-autoresearch` is a Markdown-first Codex skill package with bundled helper scripts. No build step, no third-party runtime dependencies.

## Prerequisites

- Codex with skills enabled.
- macOS or Linux.
- Git for iterative modes, because the loop commits, verifies, and reverts experiments.
- Python 3 for the bundled helper scripts.
- A working `codex` CLI in `PATH` for managed background runs and `exec` mode.

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

## Required Session Hooks

The interactive skill requires these user-level Codex session hooks and auto-installs or repairs them right after the initial repo scan whenever `autoresearch_hooks_ctl.py status` is not ready for future sessions. This bootstrap happens before the first clarification question. If you want to preinstall or inspect them manually:

```bash
python3 /absolute/path/to/codex-autoresearch/scripts/autoresearch_hooks_ctl.py install
```

Inspect the current state first if you want:

```bash
python3 /absolute/path/to/codex-autoresearch/scripts/autoresearch_hooks_ctl.py status
```

What they do:

- `SessionStart` reinjects the short runtime checklist when a future session starts or resumes.
- `Stop` lets Codex continue only when the autoresearch run still looks active/resumable.

Important:

- For the interactive skill, these hooks are required bootstrap infrastructure and are installed automatically when needed.
- Hooks only attach to later Codex sessions that clearly look like `codex-autoresearch` work. They do not retroactively change the currently open foreground session, and unrelated Codex conversations in the same repo are left alone.
- If the skill just installed them in the current session, `background` can use them immediately.
- The currently open foreground session will not use them mid-session. To get hooks there, reopen/resume the same thread in a new Codex session. In the CLI this is often `codex resume`; in the app, reopen the same thread in a new session.
- Managed `background` runs explicitly pass the workspace-owned Results directory into nested sessions.
- Future `foreground` sessions can also recover the run context through the repo's git-local pointer, but hooks still require an explicit autoresearch session signal before they attach.

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
