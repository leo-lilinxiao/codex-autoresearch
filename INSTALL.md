# Installation

`codex-autoresearch` is a Markdown-only Codex skill package. No build step, no dependencies.

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
Mode: plan
Goal: reduce failing tests to zero
```

Expected behavior:

- Codex recognizes the skill,
- loads `SKILL.md`,
- loads the plan workflow,
- and collects any missing fields via the wizard.

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
