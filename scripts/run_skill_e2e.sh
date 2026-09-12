#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${1:-help}"
CLEAN=0

if [[ "$MODE" != "help" ]]; then
  shift
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --clean)
      CLEAN=1
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 2
      ;;
  esac
  shift
done

usage() {
  cat <<'EOF'
Usage:
  bash scripts/run_skill_e2e.sh foreground-smoke [--clean]
  bash scripts/run_skill_e2e.sh runtime-smoke [--clean]
  bash scripts/run_skill_e2e.sh real-foreground [--clean]
  bash scripts/run_skill_e2e.sh real-background [--clean]

Modes:
  foreground-smoke  Deterministic init/finish/complete run in a disposable installed skill repo.
  runtime-smoke     Deterministic two-worker detached controller run with a local test worker.
  real-foreground   Prepare a disposable repo and open the real Codex TUI for a human-driven Goal run.
  real-background   Launch real authenticated codex exec workers and wait for target completion.

The deterministic modes validate control-plane mechanics and run in CI. The real modes require
local Codex authentication and are never represented as mock/model validation.
EOF
}

require_tool() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required tool: $1" >&2
    exit 1
  fi
}

copy_skill() {
  local destination="$1"
  mkdir -p "$destination/references" "$destination/scripts" "$destination/agents"
  cp "$ROOT/SKILL.md" "$destination/SKILL.md"
  cp "$ROOT/references/"*.md "$destination/references/"
  cp "$ROOT/scripts/"*.py "$destination/scripts/"
  cp "$ROOT/agents/openai.yaml" "$destination/agents/openai.yaml"
}

prepare_repo() {
  local fixture="$1"
  local temporary="$2"
  local repo="$temporary/repo"
  cp -R "$ROOT/tests/e2e-fixtures/$fixture" "$repo"
  find "$repo" -type d -name __pycache__ -prune -exec rm -rf {} +
  find "$repo" -type f -name '*.pyc' -delete
  copy_skill "$repo/.agents/skills/codex-autoresearch"
  git -C "$repo" init -b main >/dev/null
  git -C "$repo" config user.name e2e
  git -C "$repo" config user.email e2e@example.com
  git -C "$repo" add .
  git -C "$repo" commit -m "fixture baseline" >/dev/null
  printf '%s\n' "$repo"
}

cleanup() {
  local temporary="$1"
  if [[ "$CLEAN" -eq 1 ]]; then
    rm -rf "$temporary"
  else
    echo "Demo repository kept at: $temporary/repo"
  fi
}

assert_status() {
  local control="$1"
  local repo="$2"
  local expected="$3"
  python3 - "$control" "$repo" "$expected" <<'PY'
import json
import subprocess
import sys

control, repo, expected = sys.argv[1:]
payload = json.loads(
    subprocess.check_output(
        [sys.executable, control, "status", "--repo", repo],
        text=True,
        encoding="utf-8",
    )
)
if payload["status"] != expected:
    raise SystemExit(f"expected status {expected}, got {payload}")
PY
}

run_foreground_smoke() {
  require_tool python3
  require_tool git
  local temporary repo control
  temporary="$(mktemp -d)"
  repo="$(prepare_repo interactive_unittest_fix "$temporary")"
  control="$repo/.agents/skills/codex-autoresearch/scripts/autoresearch.py"

  python3 "$control" init \
    --repo "$repo" \
    --goal "Reduce the unit-test failure count to zero" \
    --scope src \
    --metric-name failure_count \
    --direction lower \
    --verify "python3 scripts/score.py" \
    --metric-key failure_count \
    --target 0 >/dev/null

  python3 - "$repo/src/math_utils.py" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
old = "return a - b"
if text.count(old) != 1:
    raise SystemExit(f"expected exactly one fixture bug in {path}")
path.write_text(text.replace(old, "return a + b"), encoding="utf-8")
PY
  python3 "$control" finish --repo "$repo" --description "correct integer addition" >/dev/null
  assert_status "$control" "$repo" complete
  python3 -m unittest discover -s "$repo/tests" -q
  echo "foreground smoke: OK"
  cleanup "$temporary"
}

write_test_worker() {
  local destination="$1"
  cat > "$destination" <<'PY'
#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


arguments = sys.argv[1:]
repo = Path(arguments[arguments.index("-C") + 1])
prompt = sys.stdin.read()
match = re.search(r"^Control script: (.+)$", prompt, re.MULTILINE)
if match is None:
    raise SystemExit("worker prompt did not contain Control script")
control = match.group(1).strip()
status = json.loads(
    subprocess.check_output(
        [sys.executable, control, "status", "--repo", str(repo)],
        text=True,
        encoding="utf-8",
    )
)
value = int(status["metric"]["current"])
next_value = value - 1
(repo / "src" / "value.txt").write_text(f"{next_value}\n", encoding="utf-8")
subprocess.check_call(
    [
        sys.executable,
        control,
        "finish",
        "--repo",
        str(repo),
        "--description",
        f"reduce counter to {next_value}",
    ]
)
PY
  chmod +x "$destination"
}

wait_for_terminal_status() {
  local control="$1"
  local repo="$2"
  local timeout_seconds="$3"
  python3 - "$control" "$repo" "$timeout_seconds" <<'PY'
import json
import subprocess
import sys
import time

control, repo, timeout_text = sys.argv[1:]
deadline = time.monotonic() + int(timeout_text)
last = None
while time.monotonic() < deadline:
    last = json.loads(
        subprocess.check_output(
            [sys.executable, control, "status", "--repo", repo],
            text=True,
            encoding="utf-8",
        )
    )
    if last["status"] in {"complete", "blocked", "error", "stopped"}:
        print(json.dumps(last, sort_keys=True))
        raise SystemExit(0)
    time.sleep(0.2)
raise SystemExit(f"timed out waiting for terminal status; last={last}")
PY
}

assert_completed_repo() {
  local control="$1"
  local repo="$2"
  local expected_iterations="$3"
  python3 - "$control" "$repo" "$expected_iterations" <<'PY'
import json
import subprocess
import sys
from pathlib import Path

control, repo_text, expected_text = sys.argv[1:]
repo = Path(repo_text)
expected = int(expected_text)
status = json.loads(
    subprocess.check_output(
        [sys.executable, control, "status", "--repo", str(repo)],
        text=True,
        encoding="utf-8",
    )
)
if status["status"] != "complete" or status["metric"]["current"] != status["metric"]["target"]:
    raise SystemExit(f"run did not reach its target: {status}")
if status["iterations"] != expected:
    raise SystemExit(f"expected {expected} iterations, got {status['iterations']}")
events = [
    json.loads(line)
    for line in Path(status["events_path"]).read_text(encoding="utf-8").splitlines()
]
if events[0]["event"] != "baseline" or events[-1]["event"] != "complete":
    raise SystemExit(f"invalid event boundary: {events}")
if sum(event["event"] == "iteration" for event in events) != expected:
    raise SystemExit(f"iteration event count mismatch: {events}")
if any(event["event"] == "iteration" and event["outcome"] != "keep" for event in events):
    raise SystemExit(f"demo unexpectedly retained a discard: {events}")
dirty = subprocess.check_output(
    ["git", "-C", str(repo), "status", "--short"],
    text=True,
    encoding="utf-8",
).strip()
if dirty:
    raise SystemExit(f"demo repository is dirty after completion: {dirty}")
subjects = subprocess.check_output(
    ["git", "-C", str(repo), "log", "--format=%s", f"-{expected + 1}"],
    text=True,
    encoding="utf-8",
)
if subjects.count("autoresearch:") < expected:
    raise SystemExit(f"missing retained autoresearch commits: {subjects}")
worker_logs = sorted((repo / "autoresearch-results" / "logs").glob("worker-*.jsonl"))
if status["mode"] == "background" and len(worker_logs) != expected:
    raise SystemExit(f"expected {expected} worker logs, found {worker_logs}")
if any(path.stat().st_size == 0 for path in worker_logs):
    raise SystemExit(f"empty worker log found: {worker_logs}")
PY
}

run_runtime_smoke() {
  require_tool python3
  require_tool git
  local temporary repo control worker terminal
  temporary="$(mktemp -d)"
  repo="$(prepare_repo counter_reduction "$temporary")"
  control="$repo/.agents/skills/codex-autoresearch/scripts/autoresearch.py"
  worker="$temporary/test-codex"
  write_test_worker "$worker"

  python3 "$control" launch \
    --repo "$repo" \
    --goal "Reduce the counter to zero" \
    --scope src \
    --metric-name counter \
    --direction lower \
    --verify "python3 scripts/score.py" \
    --target 0 \
    --codex-bin "$worker" >/dev/null

  terminal="$(wait_for_terminal_status "$control" "$repo" 20)"
  python3 - "$terminal" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
if payload["status"] != "complete" or payload["iterations"] != 2:
    raise SystemExit(f"unexpected runtime result: {payload}")
PY
  assert_completed_repo "$control" "$repo" 2
  echo "runtime smoke: OK"
  cleanup "$temporary"
}

run_real_foreground() {
  require_tool codex
  require_tool python3
  require_tool git
  local temporary repo control prompt terminal iterations
  temporary="$(mktemp -d)"
  repo="$(prepare_repo interactive_unittest_fix "$temporary")"
  control="$repo/.agents/skills/codex-autoresearch/scripts/autoresearch.py"
  prompt="$(cat "$repo/prompt.txt")"
  echo "Starting real foreground demo in: $repo"
  echo "Submit the skill prompt, confirm foreground, then approve with go."
  if ! TERM="${CODEX_E2E_TERM:-xterm-256color}" codex \
    --dangerously-bypass-approvals-and-sandbox --no-alt-screen -C "$repo" \
    "$prompt"; then
    cleanup "$temporary"
    return 1
  fi
  terminal="$(python3 "$control" status --repo "$repo")"
  if ! iterations="$(python3 -c '
import json, sys
status = json.loads(sys.argv[1])
if status["status"] != "complete" or status["iterations"] < 1:
    raise SystemExit(f"real foreground run did not complete: {status}")
print(status["iterations"])
' "$terminal")"; then
    cleanup "$temporary"
    return 1
  fi
  if ! assert_completed_repo "$control" "$repo" "$iterations"; then
    cleanup "$temporary"
    return 1
  fi
  if ! python3 -m unittest discover -s "$repo/tests" -q; then
    cleanup "$temporary"
    return 1
  fi
  echo "real foreground: OK ($iterations iterations)"
  cleanup "$temporary"
}

run_real_background() {
  require_tool codex
  require_tool python3
  require_tool git
  local temporary repo control terminal
  temporary="$(mktemp -d)"
  repo="$(prepare_repo counter_reduction "$temporary")"
  control="$repo/.agents/skills/codex-autoresearch/scripts/autoresearch.py"
  echo "Starting real background demo in: $repo"

  python3 "$control" launch \
    --repo "$repo" \
    --goal "Reduce the integer in src/value.txt to zero through focused experiments" \
    --scope src \
    --metric-name counter \
    --direction lower \
    --verify "python3 scripts/score.py" \
    --target 0 \
    --execution-policy danger-full-access >/dev/null

  terminal="$(wait_for_terminal_status "$control" "$repo" 900)"
  python3 - "$terminal" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
if payload["status"] != "complete" or payload["metric"]["current"] != 0:
    raise SystemExit(f"real background run did not complete: {payload}")
print(f"real background: OK ({payload['iterations']} iterations)")
PY
  iterations="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["iterations"])' "$terminal")"
  assert_completed_repo "$control" "$repo" "$iterations"
  cleanup "$temporary"
}

case "$MODE" in
  foreground-smoke)
    run_foreground_smoke
    ;;
  runtime-smoke)
    run_runtime_smoke
    ;;
  real-foreground)
    run_real_foreground
    ;;
  real-background)
    run_real_background
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    echo "Unknown mode: $MODE" >&2
    usage >&2
    exit 2
    ;;
esac
