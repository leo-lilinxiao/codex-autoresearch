#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

required_paths=(
  "$ROOT/SKILL.md"
  "$ROOT/README.md"
  "$ROOT/CONTRIBUTING.md"
  "$ROOT/docs/INSTALL.md"
  "$ROOT/docs/GUIDE.md"
  "$ROOT/docs/EXAMPLES.md"
  "$ROOT/docs/i18n/README_ZH.md"
  "$ROOT/references"
  "$ROOT/agents/openai.yaml"
)

# Core reference files
required_references=(
  "$ROOT/references/core-principles.md"
  "$ROOT/references/autonomous-loop-protocol.md"
  "$ROOT/references/interaction-wizard.md"
  "$ROOT/references/structured-output-spec.md"
  "$ROOT/references/modes.md"
  "$ROOT/references/results-logging.md"
  "$ROOT/references/plan-workflow.md"
  "$ROOT/references/debug-workflow.md"
  "$ROOT/references/fix-workflow.md"
  "$ROOT/references/security-workflow.md"
  "$ROOT/references/ship-workflow.md"
  "$ROOT/references/exec-workflow.md"
  "$ROOT/references/lessons-protocol.md"
  "$ROOT/references/pivot-protocol.md"
  "$ROOT/references/web-search-protocol.md"
  "$ROOT/references/environment-awareness.md"
  "$ROOT/references/parallel-experiments-protocol.md"
  "$ROOT/references/session-resume-protocol.md"
  "$ROOT/references/health-check-protocol.md"
  "$ROOT/references/hypothesis-perspectives.md"
)

for path in "${required_paths[@]}"; do
  if [[ ! -e "$path" ]]; then
    echo "Missing required path: $path" >&2
    exit 1
  fi
done

for path in "${required_references[@]}"; do
  if [[ ! -e "$path" ]]; then
    echo "Missing required reference: $path" >&2
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

if ! grep -rn '\.agents/skills' "$ROOT/README.md" "$ROOT/docs/INSTALL.md" >/dev/null; then
  echo "Install docs must mention .agents/skills" >&2
  exit 1
fi

if ! grep -rn '\$codex-autoresearch' "$ROOT/SKILL.md" "$ROOT/README.md" "$ROOT/docs/GUIDE.md" >/dev/null; then
  echo "Explicit skill invocation examples are missing" >&2
  exit 1
fi

# Verify SKILL.md references all new protocol files
for ref in lessons-protocol pivot-protocol web-search-protocol environment-awareness \
           parallel-experiments-protocol session-resume-protocol health-check-protocol \
           hypothesis-perspectives exec-workflow; do
  if ! grep -q "$ref" "$ROOT/SKILL.md"; then
    echo "SKILL.md does not reference $ref" >&2
    exit 1
  fi
done

echo "Skill structure looks valid. ($(ls "$ROOT/references/"*.md | wc -l) reference files found)"
