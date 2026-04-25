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
  "$ROOT/tests"
  "$ROOT/tests/e2e-fixtures"
  "$ROOT/tests/e2e-fixtures/exec_marker_reduction/autoresearch-results/lessons.md"
  "$ROOT/tests/e2e-fixtures/exec_marker_reduction/autoresearch-results/state.json"
  "$ROOT/tests/e2e-fixtures/exec_marker_reduction/autoresearch-results/results.tsv"
)

# Core reference files
required_references=(
  "$ROOT/references/core-principles.md"
  "$ROOT/references/runtime-hard-invariants.md"
  "$ROOT/references/loop-workflow.md"
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

required_scripts=(
  "$ROOT/scripts/validate_skill_structure.sh"
  "$ROOT/scripts/autoresearch_helpers.py"
  "$ROOT/scripts/autoresearch_launch_gate.py"
  "$ROOT/scripts/autoresearch_resume_prompt.py"
  "$ROOT/scripts/autoresearch_runtime_ctl.py"
  "$ROOT/scripts/autoresearch_preflight.py"
  "$ROOT/scripts/autoresearch_commit_gate.py"
  "$ROOT/scripts/autoresearch_decision.py"
  "$ROOT/scripts/autoresearch_health_check.py"
  "$ROOT/scripts/autoresearch_lessons.py"
  "$ROOT/scripts/autoresearch_exec_state.py"
  "$ROOT/scripts/autoresearch_hook_session_start.py"
  "$ROOT/scripts/autoresearch_hook_stop.py"
  "$ROOT/scripts/autoresearch_init_run.py"
  "$ROOT/scripts/autoresearch_hooks_ctl.py"
  "$ROOT/scripts/autoresearch_record_iteration.py"
  "$ROOT/scripts/autoresearch_resume_check.py"
  "$ROOT/scripts/autoresearch_supervisor_status.py"
  "$ROOT/scripts/autoresearch_select_parallel_batch.py"
  "$ROOT/scripts/check_skill_invariants.py"
  "$ROOT/scripts/run_skill_e2e.sh"
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

for path in "${required_scripts[@]}"; do
  if [[ ! -e "$path" ]]; then
    echo "Missing required script: $path" >&2
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

if ! grep -n '^\s*allow_implicit_invocation:\s*false\s*$' "$ROOT/agents/openai.yaml" >/dev/null; then
  echo "agents/openai.yaml must disable implicit invocation to preserve hook identity" >&2
  exit 1
fi

if ! grep -rn '\.agents/skills' "$ROOT/README.md" "$ROOT/docs/INSTALL.md" >/dev/null; then
  echo "Install docs must mention .agents/skills" >&2
  exit 1
fi

if ! grep -q 'autoresearch_hooks_ctl.py' "$ROOT/README.md" "$ROOT/docs/INSTALL.md" "$ROOT/docs/GUIDE.md" "$ROOT/references/interaction-wizard.md"; then
  echo "Long-running hook docs are missing autoresearch_hooks_ctl.py guidance" >&2
  exit 1
fi

if ! grep -rn '\$codex-autoresearch' "$ROOT/SKILL.md" "$ROOT/README.md" "$ROOT/docs/GUIDE.md" >/dev/null; then
  echo "Explicit skill invocation examples are missing" >&2
  exit 1
fi

# Verify SKILL.md references all new protocol files
for ref in runtime-hard-invariants loop-workflow lessons-protocol pivot-protocol web-search-protocol environment-awareness \
           parallel-experiments-protocol session-resume-protocol health-check-protocol \
           hypothesis-perspectives exec-workflow; do
  if ! grep -q "$ref" "$ROOT/SKILL.md"; then
    echo "SKILL.md does not reference $ref" >&2
    exit 1
  fi
done

nonempty_runtime_lines=$(grep -cve '^[[:space:]]*$' "$ROOT/references/runtime-hard-invariants.md")
if [[ "$nonempty_runtime_lines" -gt 32 ]]; then
  echo "runtime-hard-invariants.md is too long ($nonempty_runtime_lines non-empty lines)" >&2
  exit 1
fi

if ! grep -q 'references/runtime-hard-invariants.md' "$ROOT/SKILL.md"; then
  echo "SKILL.md must load runtime-hard-invariants.md" >&2
  exit 1
fi

if ! grep -q 'references/loop-workflow.md' "$ROOT/SKILL.md"; then
  echo "SKILL.md must route loop mode through loop-workflow.md" >&2
  exit 1
fi

if grep -q 'load `autonomous-loop-protocol.md` for all iterating modes' "$ROOT/references/modes.md"; then
  echo "modes.md still treats autonomous-loop-protocol.md as a default runtime load" >&2
  exit 1
fi

if ! grep -q 'load `runtime-hard-invariants.md` for active execution' "$ROOT/references/modes.md"; then
  echo "modes.md must require runtime-hard-invariants.md for active execution" >&2
  exit 1
fi

if grep -q 'NEVER STOP\. NEVER ASK "should I continue\?"' "$ROOT/references/autonomous-loop-protocol.md"; then
  echo "autonomous-loop-protocol.md still contains the old NEVER STOP runtime contract" >&2
  exit 1
fi

if grep -q 'Hard Rule 13 (NEVER STOP)' "$ROOT/references/autonomous-loop-protocol.md"; then
  echo "autonomous-loop-protocol.md still contains stale hard-rule fingerprint content" >&2
  exit 1
fi

if ! grep -q 'Use `runtime-hard-invariants.md` plus the selected mode workflow as the source of truth\.' "$ROOT/references/autonomous-loop-protocol.md"; then
  echo "autonomous-loop-protocol.md must anchor Phase 8.7 to runtime-hard-invariants.md" >&2
  exit 1
fi

if ! grep -q 'Log every completed experiment before the next one starts\.' "$ROOT/references/interaction-wizard.md"; then
  echo "interaction-wizard.md is missing the runtime logging checklist reminder" >&2
  exit 1
fi

# Verify autonomous-loop-protocol.md contains Phase 8.7 and Re-Anchor
if ! grep -q "Phase 8.7" "$ROOT/references/autonomous-loop-protocol.md"; then
  echo "autonomous-loop-protocol.md is missing Phase 8.7" >&2
  exit 1
fi
if ! grep -q "Re-Anchor" "$ROOT/references/autonomous-loop-protocol.md"; then
  echo "autonomous-loop-protocol.md is missing Re-Anchor content" >&2
  exit 1
fi

echo "Skill structure looks valid. ($(ls "$ROOT/references/"*.md | wc -l) reference files found)"
