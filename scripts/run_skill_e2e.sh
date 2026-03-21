#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${1:-}"
KEEP_TEMP=1
DANGEROUS=1

usage() {
  cat <<'EOF'
Usage:
  bash scripts/run_skill_e2e.sh exec-smoke [--sandboxed] [--clean]
  bash scripts/run_skill_e2e.sh runtime-smoke [--clean]
  bash scripts/run_skill_e2e.sh interactive-smoke [--clean]

Modes:
  exec-smoke         Prepare a disposable repo, run `codex exec` against the real skill,
                     and validate artifacts with check_skill_invariants.py.
  runtime-smoke      Prepare a disposable repo, install the skill, exercise the
                     detached runtime launch/status/stop path with a fake Codex,
                     and validate runtime-control artifacts automatically.
  interactive-smoke  Prepare a disposable repo and print the exact manual smoke-test steps
                     for the interactive wizard + go boundary.

Flags:
  --dangerous        Legacy alias for the default exec-smoke behavior:
                     pass --dangerously-bypass-approvals-and-sandbox to codex exec
                     inside the disposable temp repo created by this harness.
  --sandboxed        Force exec-smoke to use --full-auto instead. This is useful for
                     reproducing sandbox-related blockers, but may fail protocol checks
                     because git commit/revert writes inside .git are sandboxed.
  --clean            Delete the temp repo after the command finishes successfully.
EOF
}

if [[ -z "$MODE" ]]; then
  usage
  exit 1
fi
shift || true

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dangerous)
      DANGEROUS=1
      ;;
    --sandboxed)
      DANGEROUS=0
      ;;
    --clean)
      KEEP_TEMP=0
      ;;
    *)
      echo "Unknown flag: $1" >&2
      usage
      exit 1
      ;;
  esac
  shift
done

require_tool() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required tool: $1" >&2
    exit 1
  fi
}

copy_fixture() {
  local fixture_name="$1"
  local dest_repo="$2"
  mkdir -p "$dest_repo"
  cp -R "$ROOT/tests/e2e-fixtures/$fixture_name/." "$dest_repo/"
}

copy_skill() {
  local dest_skill_root="$1"
  mkdir -p "$(dirname "$dest_skill_root")"
  cp -R "$ROOT" "$dest_skill_root"
  rm -rf "$dest_skill_root/.git"
  find "$dest_skill_root" -type d -name '__pycache__' -prune -exec rm -rf {} +
}

init_git_repo() {
  local repo="$1"
  git -C "$repo" init -b main >/dev/null
  git -C "$repo" config user.name e2e-bot
  git -C "$repo" config user.email e2e@example.com
  git -C "$repo" add .
  git -C "$repo" commit -m "fixture baseline" >/dev/null
}

prepare_skill_repo() {
  local fixture_name="$1"
  local tmpdir="$2"
  local repo="$tmpdir/repo"
  copy_fixture "$fixture_name" "$repo"
  copy_skill "$repo/.agents/skills/codex-autoresearch"
  init_git_repo "$repo"
  printf '%s\n' "$repo"
}

write_sleeping_fake_codex() {
  local path="$1"
  cat > "$path" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
repo=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    -C) repo="$2"; shift 2 ;;
    *) shift ;;
  esac
done
if [[ -n "$repo" ]]; then
  cd "$repo"
fi
sleep 30
EOF
  chmod +x "$path"
}

cleanup_if_requested() {
  local tmpdir="$1"
  if [[ "$KEEP_TEMP" -eq 0 ]]; then
    rm -rf "$tmpdir"
  else
    echo "Temp repo kept at: $tmpdir"
  fi
}

run_exec_smoke() {
  require_tool codex
  require_tool python3
  require_tool git

  local tmpdir repo e2e_dir last_message event_log codex_flags lessons_sha
  tmpdir="$(mktemp -d)"
  repo="$(prepare_skill_repo "exec_marker_reduction" "$tmpdir")"

  e2e_dir="$tmpdir/e2e"
  mkdir -p "$e2e_dir"
  last_message="$e2e_dir/last-message.txt"
  event_log="$e2e_dir/events.jsonl"
  lessons_sha="$(sha256sum "$repo/autoresearch-lessons.md" | awk '{print $1}')"

  codex_flags=(exec -C "$repo" --json --output-last-message "$last_message")
  if [[ "$DANGEROUS" -eq 1 ]]; then
    codex_flags+=(--dangerously-bypass-approvals-and-sandbox)
  else
    codex_flags+=(--full-auto)
  fi

  if ! codex "${codex_flags[@]}" - < "$repo/prompt.txt" | tee "$event_log"; then
    echo "codex exec failed; temp repo left at: $tmpdir" >&2
    exit 1
  fi

  python3 "$ROOT/scripts/check_skill_invariants.py" exec \
    --repo "$repo" \
    --last-message-file "$last_message" \
    --event-log "$event_log" \
    --lessons-sha256 "$lessons_sha" \
    --expect-prev-results \
    --expect-prev-state \
    --expect-improvement

  echo "exec smoke: OK"
  cleanup_if_requested "$tmpdir"
}

run_interactive_smoke() {
  require_tool python3
  require_tool git

  local tmpdir repo
  tmpdir="$(mktemp -d)"
  repo="$(prepare_skill_repo "interactive_unittest_fix" "$tmpdir")"

  cat <<EOF
Interactive smoke repo prepared at:
  $repo

1. Start Codex:
   codex --full-auto --no-alt-screen -C "$repo"

2. Paste this prompt:
$(sed 's/^/   /' "$repo/prompt.txt")

3. Expected behavior before launch:
   - Codex scans the repo.
   - Codex asks at least one confirmation question before editing.
   - You reply: go

4. Expected behavior after "go":
   - Codex performs a single launch handoff that writes autoresearch-launch.json and starts the detached runtime controller.
   - Codex stops asking questions.
   - It iterates autonomously until tests pass or you interrupt it.

5. After you stop the run, validate artifacts:
   python3 "$ROOT/scripts/check_skill_invariants.py" interactive --repo "$repo" --verify-cmd "python3 -m unittest discover -s tests -q" --expect-improvement
EOF

  cleanup_if_requested "$tmpdir"
}

run_runtime_smoke() {
  require_tool python3
  require_tool git

  local tmpdir repo skill_root fake_codex status_json
  tmpdir="$(mktemp -d)"
  repo="$(prepare_skill_repo "interactive_unittest_fix" "$tmpdir")"

  skill_root="$repo/.agents/skills/codex-autoresearch"
  fake_codex="$tmpdir/fake-codex"
  write_sleeping_fake_codex "$fake_codex"

  python3 "$skill_root/scripts/autoresearch_runtime_ctl.py" launch \
    --repo "$repo" \
    --original-goal "Reduce failing tests in this repo" \
    --mode loop \
    --goal "Reduce failing tests" \
    --scope "src/**/*.py tests/**/*.py" \
    --metric-name "failure count" \
    --direction lower \
    --verify "python3 -m unittest discover -s tests -q" \
    --guard "python3 -m py_compile src tests" \
    --codex-bin "$fake_codex" >/dev/null

  status_json="$(python3 "$skill_root/scripts/autoresearch_runtime_ctl.py" status --repo "$repo")"
  python3 - "$status_json" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
if payload.get("status") != "running":
    raise SystemExit(f"expected running runtime, got {payload!r}")
PY

  python3 "$skill_root/scripts/autoresearch_runtime_ctl.py" stop --repo "$repo" >/dev/null
  python3 "$skill_root/scripts/check_skill_invariants.py" runtime --repo "$repo"

  echo "runtime smoke: OK"
  cleanup_if_requested "$tmpdir"
}

case "$MODE" in
  exec-smoke)
    run_exec_smoke
    ;;
  runtime-smoke)
    run_runtime_smoke
    ;;
  interactive-smoke)
    run_interactive_smoke
    ;;
  *)
    echo "Unknown mode: $MODE" >&2
    usage
    exit 1
    ;;
esac
