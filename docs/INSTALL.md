# Installation

## Requirements

- a current Codex CLI release with Skills and Goals;
- Python 3.11 or newer;
- Git;
- a configured Git author and committer identity;
- a clean, named branch for each new run.

Full Access is recommended because autoresearch creates and reverts Git commits:

```bash
codex --dangerously-bypass-approvals-and-sandbox
```

## Skill Installer

In Codex, run:

```text
$skill-installer install https://github.com/leo-lilinxiao/codex-autoresearch
```

Then open the target repository and invoke `$codex-autoresearch`.

## Manual Repository Install

Use this when the skill should travel with one project:

```bash
git clone https://github.com/leo-lilinxiao/codex-autoresearch.git
mkdir -p your-project/.agents/skills
cp -R codex-autoresearch your-project/.agents/skills/codex-autoresearch
```

## Manual User Install

Use this for all projects owned by the current user:

```bash
git clone https://github.com/leo-lilinxiao/codex-autoresearch.git
mkdir -p ~/.agents/skills
cp -R codex-autoresearch ~/.agents/skills/codex-autoresearch
```

Do not install both a repository copy and a user copy unless you intentionally want two independently discovered versions.

## Development Symlink

```bash
git clone https://github.com/leo-lilinxiao/codex-autoresearch.git
mkdir -p your-project/.agents/skills
ln -s "$(pwd)/codex-autoresearch" your-project/.agents/skills/codex-autoresearch
```

Edits to the source checkout are then visible through the symlink.

## Verify

Open Codex in the target repository, type `$`, and select `codex-autoresearch`. A valid installation should:

1. inspect the repository without editing it;
2. propose a metric, target, scope, guard, and run mode;
3. obtain any missing launch approval before creating `autoresearch-results/`.

The skill does not modify Codex configuration.

## Update

- Skill installer: run the installer again with the same repository URL.
- Copied install: replace the installed `codex-autoresearch` directory with a fresh checkout.
- Symlink: run `git pull` in the source checkout.

Keep only one discovered copy for a given scope to avoid duplicate skill entries.
