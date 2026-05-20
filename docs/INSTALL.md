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

Then use `$codex-autoresearch`.

### Manual repo-local skill install

```bash
git clone https://github.com/leo-lilinxiao/codex-autoresearch.git
cp -r codex-autoresearch your-project/.agents/skills/codex-autoresearch
```

### Manual user-scope skill install

```bash
git clone https://github.com/leo-lilinxiao/codex-autoresearch.git
cp -r codex-autoresearch ~/.agents/skills/codex-autoresearch
```

### Symlink for live development

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

## Continuity

Autoresearch prepares resume and background handoff support automatically when a run starts. No manual setup is normally needed.

For troubleshooting, you can prepare it directly:

```bash
python3 /absolute/path/to/codex-autoresearch/scripts/autoresearch_hooks_ctl.py install
```

Or inspect the current state:

```bash
python3 /absolute/path/to/codex-autoresearch/scripts/autoresearch_hooks_ctl.py status
```

## Updating

If installed by copy: re-clone and replace the installed folder.

If installed by symlink: `git pull` in the source repo. Changes are live immediately.

## Disable Without Deleting

Use `~/.codex/config.toml`:

```toml
[[skills.config]]
path = "/absolute/path/to/codex-autoresearch/SKILL.md"
enabled = false
```

Use `/skills` to verify the skill is disabled.
