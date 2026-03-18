#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

required_paths=(
  "$ROOT/SKILL.md"
  "$ROOT/README.md"
  "$ROOT/README_ZH.md"
  "$ROOT/INSTALL.md"
  "$ROOT/GUIDE.md"
  "$ROOT/EXAMPLES.md"
  "$ROOT/CONTRIBUTING.md"
  "$ROOT/references"
  "$ROOT/agents/openai.yaml"
)

for path in "${required_paths[@]}"; do
  if [[ ! -e "$path" ]]; then
    echo "Missing required path: $path" >&2
    exit 1
  fi
done

if ! grep -n '^name:' "$ROOT/SKILL.md" >/dev/null; then
  echo "SKILL.md is missing name metadata" >&2
  exit 1
fi

if ! grep -n '^description:' "$ROOT/SKILL.md" >/dev/null; then
  echo "SKILL.md is missing description metadata" >&2
  exit 1
fi

if ! grep -n '^\s*display_name:' "$ROOT/agents/openai.yaml" >/dev/null; then
  echo "agents/openai.yaml is missing display_name metadata" >&2
  exit 1
fi

if ! grep -n 'allow_implicit_invocation:' "$ROOT/agents/openai.yaml" >/dev/null; then
  echo "agents/openai.yaml is missing allow_implicit_invocation policy" >&2
  exit 1
fi

if ! grep -rn '\.agents/skills' "$ROOT/README.md" "$ROOT/README_ZH.md" "$ROOT/INSTALL.md" >/dev/null; then
  echo "Install docs must mention .agents/skills" >&2
  exit 1
fi

if ! grep -rn '\$codex-autoresearch' "$ROOT/SKILL.md" "$ROOT/README.md" "$ROOT/README_ZH.md" "$ROOT/GUIDE.md" >/dev/null; then
  echo "Explicit skill invocation examples are missing" >&2
  exit 1
fi

echo "Skill structure looks valid."
