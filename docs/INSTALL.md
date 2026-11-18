# Installation

## Requirements

- a current Codex CLI release with Skills and Goals.
- Python 3.11 or newer.
- Git and system process tools (`ps` on macOS/Linux or `taskkill` on Windows).
- a configured Git author and committer identity.
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

Use this to make it available in all your projects:

```bash
git clone https://github.com/leo-lilinxiao/codex-autoresearch.git
mkdir -p ~/.agents/skills
cp -R codex-autoresearch ~/.agents/skills/codex-autoresearch
```

Don't install both a repository copy and a user copy unless you want Codex to see two separate versions.

## Development Symlink

```bash
git clone https://github.com/leo-lilinxiao/codex-autoresearch.git
mkdir -p your-project/.agents/skills
ln -s "$(pwd)/codex-autoresearch" your-project/.agents/skills/codex-autoresearch
```

Edits in your checkout are visible through the symlink.

## Verify

Open Codex in the target repository, type `$`, and select `codex-autoresearch`. If it's installed correctly, Codex should:

1. Look through the repository without editing it.
2. Propose a metric, target, scope, guard, and run mode.
3. Ask for any missing choices or approval before creating `autoresearch-results/`.

The skill does not modify Codex configuration.

## Update

Finish or stop an active run before updating. If the new version reports an unsupported run format, archive the old run before starting a new one. Archiving preserves its files without converting them.

- Skill installer: move the existing `codex-autoresearch` directory outside the skills directories as a backup, then run the installation command again. The installer does not overwrite an existing installation.
- Copied install: replace the installed `codex-autoresearch` directory with a fresh checkout.
- Symlink: run `git pull` in the source checkout.

Keep backups outside the skills directories so Codex doesn't discover them as duplicate skills.
