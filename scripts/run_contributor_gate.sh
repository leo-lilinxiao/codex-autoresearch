#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${1:-skill}"

usage() {
  cat <<'EOF'
Usage:
  bash scripts/run_contributor_gate.sh docs
  bash scripts/run_contributor_gate.sh skill
  bash scripts/run_contributor_gate.sh help

Modes:
  docs   Run the lightweight gate for documentation-first changes:
         - validate skill structure

  skill  Run the automated gate for behavior-changing work:
         - validate skill structure
         - helper/invariant unit tests
         - workspace-owned multi-repo helper smoke test
         - detached runtime launch/status/stop smoke test
         - real codex exec smoke test

Notes:
  - Interactive wizard quality requires a MANUAL foreground smoke run (not automated):
      bash scripts/run_skill_e2e.sh interactive-smoke
  - The launch/status/stop control-plane handoff is covered automatically by:
      bash scripts/run_skill_e2e.sh runtime-smoke --clean
  - The skill gate assumes `codex`, `python3`, and `git` are available locally.
EOF
}

run_docs_gate() {
  bash "$ROOT/scripts/validate_skill_structure.sh"
}

run_skill_gate() {
  run_docs_gate
  python3 -m unittest discover -s "$ROOT/tests" -q
  bash "$ROOT/scripts/run_skill_e2e.sh" multi-repo-smoke --clean
  bash "$ROOT/scripts/run_skill_e2e.sh" runtime-smoke --clean
  bash "$ROOT/scripts/run_skill_e2e.sh" exec-smoke --clean
}

case "$MODE" in
  docs)
    run_docs_gate
    ;;
  skill)
    run_skill_gate
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    echo "Unknown mode: $MODE" >&2
    usage >&2
    exit 1
    ;;
esac
