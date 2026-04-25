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
  bash scripts/run_skill_e2e.sh multi-repo-smoke [--clean]
  bash scripts/run_skill_e2e.sh runtime-smoke [--clean]
  bash scripts/run_skill_e2e.sh interactive-smoke [--clean]

Modes:
  exec-smoke         Prepare a disposable repo, run `codex exec` against the real skill,
                     and validate artifacts with check_skill_invariants.py.
  multi-repo-smoke   Prepare a disposable workspace with primary + companion repos,
                     run the helper scripts through the workspace-owned artifact
                     path, and validate canonical context + git-local pointers.
  runtime-smoke      Prepare a disposable repo, install the skill, exercise the
                     detached runtime launch/status/stop path with a fake Codex,
                     and validate runtime-control artifacts automatically.
  interactive-smoke  [MANUAL] Prepare a disposable repo and print the exact manual
                     smoke-test steps for the interactive wizard + explicit
                     foreground/background choice. Not automated — requires a human
                     to drive the Codex session and visually verify behavior.

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
  rm -rf \
    "$dest_skill_root/.git" \
    "$dest_skill_root/.pytest_cache" \
    "$dest_skill_root/.venv" \
    "$dest_skill_root/autoresearch-results" \
    "$dest_skill_root/debug" \
    "$dest_skill_root/fix" \
    "$dest_skill_root/security" \
    "$dest_skill_root/ship"
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
if [[ "${1:-}" != "exec" ]]; then
  echo "expected codex exec" >&2
  exit 64
fi
shift
repo=""
prompt_from_stdin=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    -C) repo="$2"; shift 2 ;;
    -) prompt_from_stdin=1; shift ;;
    *) shift ;;
  esac
done
if [[ "$prompt_from_stdin" -ne 1 ]]; then
  echo "expected prompt from stdin" >&2
  exit 65
fi
cat >/dev/null
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

sha256_file() {
  local path="$1"
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$path" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$path" | awk '{print $1}'
  else
    python3 - "$path" <<'PY'
import hashlib
import sys

with open(sys.argv[1], "rb") as handle:
    print(hashlib.sha256(handle.read()).hexdigest())
PY
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
  lessons_sha="$(sha256_file "$repo/autoresearch-results/lessons.md")"

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

run_multi_repo_smoke() {
  require_tool python3
  require_tool git

  local tmpdir workspace primary companion skill_root
  local primary_base companion_base primary_head companion_head
  tmpdir="$(mktemp -d)"
  workspace="$tmpdir/workspace"
  primary="$workspace/primary"
  companion="$workspace/companion"

  mkdir -p "$workspace"
  copy_fixture "exec_marker_reduction" "$primary"
  rm -rf "$primary/autoresearch-results"
  copy_skill "$primary/.agents/skills/codex-autoresearch"
  init_git_repo "$primary"

  mkdir -p "$companion/pkg"
  cat > "$companion/pkg/helper.py" <<'EOF'
def status_banner() -> str:
    return "companion:baseline"
EOF
  init_git_repo "$companion"

  skill_root="$primary/.agents/skills/codex-autoresearch"
  primary_base="$(git -C "$primary" rev-parse --short HEAD)"
  companion_base="$(git -C "$companion" rev-parse --short HEAD)"

  python3 "$skill_root/scripts/autoresearch_init_run.py" \
    --repo "$primary" \
    --workspace-root "$workspace" \
    --mode exec \
    --goal "Reduce TODO_REMOVE markers across the workspace while keeping companion provenance in sync" \
    --scope "src/**/*.py" \
    --companion-repo-scope "$companion=pkg/**/*.py" \
    --metric-name "TODO_REMOVE marker count" \
    --direction lower \
    --verify "python3 primary/scripts/count_markers.py" \
    --verify-cwd workspace_root \
    --guard "python3 -m py_compile primary/src/app.py companion/pkg/helper.py" \
    --baseline-metric 2 \
    --baseline-commit "$primary_base" \
    --baseline-description "workspace baseline" \
    --repo-commit "$companion=$companion_base" >/dev/null

  python3 - "$primary/src/app.py" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
path.write_text(text.replace("TODO_REMOVE", "READY", 1), encoding="utf-8")
PY
  git -C "$primary" add src/app.py
  git -C "$primary" commit -m "Reduce one TODO_REMOVE marker" >/dev/null
  primary_head="$(git -C "$primary" rev-parse --short HEAD)"

  python3 - "$companion/pkg/helper.py" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
path.write_text(text.replace("baseline", "improved"), encoding="utf-8")
PY
  git -C "$companion" add pkg/helper.py
  git -C "$companion" commit -m "Update companion provenance" >/dev/null
  companion_head="$(git -C "$companion" rev-parse --short HEAD)"

  python3 "$skill_root/scripts/autoresearch_record_iteration.py" \
    --results-path "$workspace/autoresearch-results/results.tsv" \
    --status keep \
    --metric 1 \
    --commit "$primary_head" \
    --repo-commit "$companion=$companion_head" \
    --guard pass \
    --description "reduced markers across the managed workspace" >/dev/null

  python3 "$skill_root/scripts/autoresearch_exec_state.py" \
    --repo-root "$workspace" \
    --cleanup >/dev/null

  python3 "$skill_root/scripts/check_skill_invariants.py" exec \
    --repo "$primary" \
    --expect-improvement

  python3 - "$workspace" "$primary" "$companion" <<'PY'
import json
import sys
from pathlib import Path

workspace = Path(sys.argv[1]).resolve()
primary = Path(sys.argv[2]).resolve()
companion = Path(sys.argv[3]).resolve()
artifact_root = workspace / "autoresearch-results"
context = json.loads((artifact_root / "context.json").read_text(encoding="utf-8"))

if Path(context["workspace_root"]).resolve() != workspace:
    raise SystemExit("canonical context workspace_root mismatch")
if Path(context["primary_repo"]).resolve() != primary:
    raise SystemExit("canonical context primary_repo mismatch")

for repo in (primary, companion):
    pointer_path = repo / ".git" / "codex-autoresearch" / "pointer.json"
    payload = json.loads(pointer_path.read_text(encoding="utf-8"))
    if Path(payload["artifact_root"]).resolve() != artifact_root:
        raise SystemExit(f"pointer artifact_root mismatch for {repo}")
    if Path(payload["workspace_root"]).resolve() != workspace:
        raise SystemExit(f"pointer workspace_root mismatch for {repo}")
PY

  echo "multi-repo smoke: OK"
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
   codex --dangerously-bypass-approvals-and-sandbox --no-alt-screen -C "$repo"

2. Paste this prompt:
$(sed 's/^/   /' "$repo/prompt.txt")

3. Expected behavior before launch:
   - Codex scans the repo.
   - Codex asks at least one confirmation question before editing.
   - Codex requires an explicit run-mode choice: foreground or background.
   - Choose: foreground
   - You reply: go

4. Expected behavior after "go":
   - Codex stays in the same foreground session and iterates live.
   - Codex does not create autoresearch-results/launch.json, autoresearch-results/runtime.json, or autoresearch-results/runtime.log.
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
    --workspace-root "$repo" \
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
  multi-repo-smoke)
    run_multi_repo_smoke
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
