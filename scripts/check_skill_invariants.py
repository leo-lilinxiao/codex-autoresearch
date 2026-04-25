#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path

from autoresearch_helpers import (
    AutoresearchError,
    default_exec_state_path,
    default_workspace_artifacts,
    improvement,
    load_context_for_repo,
    log_summary,
    parse_results_log,
    read_launch_manifest,
    read_runtime_payload,
)


def resolve_workspace_context_for_repo(repo: Path, *, mode_name: str):
    """Resolve the managed workspace context for invariant checks.

    Real managed runs in git repos must persist a valid git-local pointer plus
    canonical context. Lightweight fixture tests may still use non-git temp
    directories and validate repo-local artifacts directly.
    """
    context = load_context_for_repo(repo)
    if context is not None:
        return context.workspace_root, context
    if (repo / ".git").exists():
        raise AutoresearchError(
            f"{mode_name} invariants require a valid git-local pointer and canonical context for {repo}."
        )
    return repo, None


BUNDLED_HELPER_RE = re.compile(
    r"(?:"
    r"(?:\.agents/skills|\.codex/skills)/[^\s\"']+"
    r"|~/(?:\.agents|\.codex)/skills/[^\s\"']+"
    r"|/etc/codex/skills/[^\s\"']+"
    r"|(?:~|/)[^\s\"']*/codex-autoresearch"
    r")/scripts/"
    r"autoresearch_(init_run|record_iteration|resume_check|select_parallel_batch|exec_state|launch_gate|resume_prompt|runtime_ctl|commit_gate|decision|health_check|lessons)\.py\b"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate real skill-run artifacts against mode-specific invariants."
    )
    subparsers = parser.add_subparsers(dest="mode", required=True)

    exec_parser = subparsers.add_parser("exec", help="Check exec-mode artifact invariants.")
    exec_parser.add_argument("--repo", required=True)
    exec_parser.add_argument("--last-message-file")
    exec_parser.add_argument("--event-log")
    exec_parser.add_argument("--lessons-sha256")
    exec_parser.add_argument("--expect-prev-results", action="store_true")
    exec_parser.add_argument("--expect-prev-state", action="store_true")
    exec_parser.add_argument("--expect-improvement", action="store_true")

    interactive_parser = subparsers.add_parser(
        "interactive", help="Check foreground interactive-mode artifacts after a manual smoke run."
    )
    interactive_parser.add_argument("--repo", required=True)
    interactive_parser.add_argument("--verify-cmd", required=True)
    interactive_parser.add_argument("--expect-improvement", action="store_true")

    runtime_parser = subparsers.add_parser(
        "runtime", help="Check background detached-runtime launch/status/stop artifacts."
    )
    runtime_parser.add_argument("--repo", required=True)
    runtime_parser.add_argument("--expect-status", default="stopped")
    runtime_parser.add_argument("--expect-terminal-reason", default="user_stopped")

    return parser.parse_args()


def commit_exists(repo: Path, commit: str) -> bool:
    completed = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", f"{commit}^{{commit}}"],
        capture_output=True,
        text=True,
    )
    return completed.returncode == 0


def validate_keep_rows_have_commits(repo: Path, parsed) -> None:
    for row in parsed.rows:
        if row.status == "keep" and row.commit == "-":
            raise AutoresearchError(
                f"keep row at {row.iteration} is missing a commit hash"
            )
        if row.commit != "-" and (repo / ".git").exists() and not commit_exists(repo, row.commit):
            raise AutoresearchError(
                f"results log references unknown commit {row.commit!r} at iteration {row.iteration}"
            )


def validate_exec_event_log(event_log: Path) -> None:
    if not event_log.exists():
        raise AutoresearchError(f"missing exec event log: {event_log}")

    event_text = event_log.read_text(encoding="utf-8")
    helper_matches = BUNDLED_HELPER_RE.findall(event_text)
    if not helper_matches:
        raise AutoresearchError(
            "exec run did not execute bundled helper scripts via the skill path"
        )

    required_helpers = {
        "init_run": "autoresearch_init_run.py",
        "exec_state": "autoresearch_exec_state.py",
    }
    for helper_key, helper_name in required_helpers.items():
        if helper_key not in helper_matches:
            raise AutoresearchError(f"exec run did not execute {helper_name}")

    if not any(
        helper_name in helper_matches
        for helper_name in ("record_iteration", "select_parallel_batch")
    ):
        raise AutoresearchError(
            "exec run did not record iterations through the bundled helper scripts"
        )


def parse_exec_message_records(text: str) -> list[tuple[int, dict[str, object]]]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        records: list[tuple[int, dict[str, object]]] = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise AutoresearchError(
                    f"exec completion stream contains invalid JSON on line {line_number}"
                ) from exc
            if not isinstance(payload, dict):
                raise AutoresearchError(
                    f"exec completion stream line {line_number} must be a JSON object"
                )
            records.append((line_number, payload))
        if not records:
            raise AutoresearchError("last message file is empty")
        return records

    if not isinstance(payload, dict):
        raise AutoresearchError("exec completion message must be a JSON object")
    return [(1, payload)]


def is_json_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def is_json_number(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(value)


def require_json_int_field(payload: dict[str, object], field: str, context: str) -> None:
    if not is_json_int(payload[field]):
        raise AutoresearchError(f"{context} field {field} must be an integer")


def require_json_number_field(payload: dict[str, object], field: str, context: str) -> None:
    if not is_json_number(payload[field]):
        raise AutoresearchError(f"{context} field {field} must be a number")


def require_json_string_field(payload: dict[str, object], field: str, context: str) -> None:
    if not isinstance(payload[field], str):
        raise AutoresearchError(f"{context} field {field} must be a string")


def validate_exec_iteration_payload(line_number: int, payload: dict[str, object]) -> None:
    required_fields = {
        "iteration",
        "commit",
        "metric",
        "delta",
        "guard",
        "status",
        "description",
    }
    missing = sorted(required_fields - payload.keys())
    if missing:
        raise AutoresearchError(
            "exec iteration message on line "
            f"{line_number} is missing required fields: {', '.join(missing)}"
        )
    context = f"exec iteration message on line {line_number}"
    require_json_int_field(payload, "iteration", context)
    require_json_string_field(payload, "commit", context)
    require_json_number_field(payload, "metric", context)
    require_json_number_field(payload, "delta", context)
    require_json_string_field(payload, "guard", context)
    require_json_string_field(payload, "status", context)
    require_json_string_field(payload, "description", context)
    if payload["status"] == "completed":
        raise AutoresearchError(
            f"exec iteration message on line {line_number} cannot report status=completed"
        )


def validate_exec_completion_payload(last_message_path: Path) -> dict[str, object]:
    text = last_message_path.read_text(encoding="utf-8").strip()
    if not text:
        raise AutoresearchError("last message file is empty")

    records = parse_exec_message_records(text)
    for line_number, record in records[:-1]:
        validate_exec_iteration_payload(line_number, record)

    _, payload = records[-1]

    if payload.get("status") != "completed":
        raise AutoresearchError("exec completion message must report status=completed")

    required_fields = {
        "status",
        "baseline",
        "best",
        "best_iteration",
        "total_iterations",
        "keeps",
        "discards",
        "crashes",
        "improved",
        "exit_code",
    }
    missing = sorted(required_fields - payload.keys())
    if missing:
        raise AutoresearchError(
            "exec completion message is missing required fields: " + ", ".join(missing)
        )
    context = "exec completion message"
    require_json_number_field(payload, "baseline", context)
    require_json_number_field(payload, "best", context)
    require_json_int_field(payload, "best_iteration", context)
    require_json_int_field(payload, "total_iterations", context)
    require_json_int_field(payload, "keeps", context)
    require_json_int_field(payload, "discards", context)
    require_json_int_field(payload, "crashes", context)
    if not isinstance(payload["improved"], bool):
        raise AutoresearchError("exec completion message field improved must be a boolean")
    require_json_int_field(payload, "exit_code", context)
    return payload


def validate_exec(repo: Path, args: argparse.Namespace) -> None:
    workspace_root, _ = resolve_workspace_context_for_repo(repo, mode_name="exec")
    artifacts = default_workspace_artifacts(workspace_root)
    results_path = artifacts.results_path
    context_path = artifacts.context_path
    prev_results_path = results_path.with_name("results.prev.tsv")
    state_path = artifacts.state_path
    prev_state_path = state_path.with_name("state.prev.json")
    lessons_path = artifacts.lessons_path
    scratch_state_path = default_exec_state_path(workspace_root)

    if not results_path.exists():
        raise AutoresearchError("exec run did not produce autoresearch-results/results.tsv")
    if not context_path.exists():
        raise AutoresearchError("exec run did not persist autoresearch-results/context.json")

    parsed = parse_results_log(results_path)
    direction = parsed.metadata.get("metric_direction")
    if direction not in {"lower", "higher"}:
        raise AutoresearchError("results log is missing a valid metric direction comment")
    summary = log_summary(parsed, direction)
    validate_keep_rows_have_commits(repo, parsed)

    if summary["main_rows"] < 2:
        raise AutoresearchError("exec run did not record any main iteration beyond baseline")
    if args.expect_improvement and not improvement(
        summary["current_metric"], summary["baseline_metric"], direction
    ):
        raise AutoresearchError(
            "exec fixture did not improve the retained metric over the baseline"
        )
    if args.expect_prev_results and not prev_results_path.exists():
        raise AutoresearchError("exec run did not archive the prior results.tsv file")
    if args.expect_prev_state and not prev_state_path.exists():
        raise AutoresearchError("exec run did not archive the prior state.json file")
    if state_path.exists():
        raise AutoresearchError("exec run unexpectedly created autoresearch-results/state.json")
    if scratch_state_path.exists():
        raise AutoresearchError(
            f"exec run left scratch JSON state behind: {scratch_state_path}"
        )
    if args.lessons_sha256:
        if not lessons_path.exists():
            raise AutoresearchError("expected autoresearch-results/lessons.md to remain present")
        if sha256_file(lessons_path) != args.lessons_sha256:
            raise AutoresearchError("exec run modified autoresearch-results/lessons.md")
    if args.last_message_file:
        last_message_path = Path(args.last_message_file)
        if not last_message_path.exists():
            raise AutoresearchError("missing --output-last-message file from codex exec")
        completion_payload = validate_exec_completion_payload(last_message_path)
        if args.expect_improvement and not completion_payload["improved"]:
            raise AutoresearchError(
                "exec completion message did not report improved=true"
            )
    if args.event_log:
        validate_exec_event_log(Path(args.event_log))

    print("exec invariants: OK")


def validate_interactive(repo: Path, args: argparse.Namespace) -> None:
    workspace_root, context = resolve_workspace_context_for_repo(repo, mode_name="interactive")
    artifacts = default_workspace_artifacts(workspace_root)
    results_path = artifacts.results_path
    state_path = artifacts.state_path
    lessons_path = artifacts.lessons_path
    launch_path = artifacts.launch_path
    runtime_path = artifacts.runtime_path
    runtime_log_path = artifacts.log_path

    if not results_path.exists():
        raise AutoresearchError("interactive run did not produce autoresearch-results/results.tsv")
    if not state_path.exists():
        raise AutoresearchError("interactive run did not produce autoresearch-results/state.json")
    if not lessons_path.exists():
        raise AutoresearchError("interactive run did not produce autoresearch-results/lessons.md")
    if launch_path.exists():
        raise AutoresearchError("foreground interactive run unexpectedly created autoresearch-results/launch.json")
    if runtime_path.exists():
        raise AutoresearchError("foreground interactive run unexpectedly created autoresearch-results/runtime.json")
    if runtime_log_path.exists():
        raise AutoresearchError("foreground interactive run unexpectedly created autoresearch-results/runtime.log")

    parsed = parse_results_log(results_path)
    direction = parsed.metadata.get("metric_direction")
    if direction not in {"lower", "higher"}:
        raise AutoresearchError("results log is missing a valid metric direction comment")
    summary = log_summary(parsed, direction)
    validate_keep_rows_have_commits(repo, parsed)
    state_payload = json.loads(state_path.read_text(encoding="utf-8"))
    if state_payload.get("config", {}).get("session_mode") != "foreground":
        raise AutoresearchError("foreground interactive run did not record config.session_mode=foreground")
    if summary["main_rows"] < 2:
        raise AutoresearchError("interactive run did not record any main iteration beyond baseline")
    if args.expect_improvement and not improvement(
        summary["current_metric"], summary["baseline_metric"], direction
    ):
        raise AutoresearchError(
            "interactive fixture did not improve the retained metric over the baseline"
        )
    if not lessons_path.read_text(encoding="utf-8").strip():
        raise AutoresearchError("interactive run left autoresearch-results/lessons.md empty")

    verify_root = workspace_root if context is not None and context.verify_cwd == "workspace_root" else repo
    completed = subprocess.run(
        args.verify_cmd,
        cwd=verify_root,
        shell=True,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise AutoresearchError(
            "interactive verify command still fails:\n"
            + (completed.stdout + completed.stderr).strip()
        )

    print("interactive invariants: OK")


def validate_runtime(repo: Path, args: argparse.Namespace) -> None:
    workspace_root, _ = resolve_workspace_context_for_repo(repo, mode_name="runtime")
    artifacts = default_workspace_artifacts(workspace_root)
    launch_path = artifacts.launch_path
    runtime_path = artifacts.runtime_path

    if not launch_path.exists():
        raise AutoresearchError("runtime smoke did not produce autoresearch-results/launch.json")
    if not runtime_path.exists():
        raise AutoresearchError("runtime smoke did not produce autoresearch-results/runtime.json")

    launch = read_launch_manifest(launch_path)
    runtime = read_runtime_payload(runtime_path)
    log_path = Path(runtime.get("log_path", ""))
    if not log_path.is_absolute():
        log_path = (repo / log_path).resolve()

    if runtime.get("status") != args.expect_status:
        raise AutoresearchError(
            f"runtime status mismatch: expected {args.expect_status!r}, got {runtime.get('status')!r}"
        )
    if runtime.get("terminal_reason") != args.expect_terminal_reason:
        raise AutoresearchError(
            "runtime terminal_reason mismatch: "
            f"expected {args.expect_terminal_reason!r}, got {runtime.get('terminal_reason')!r}"
        )
    if not isinstance(launch.get("original_goal"), str) or not launch["original_goal"].strip():
        raise AutoresearchError("launch manifest is missing original_goal")
    if launch.get("config", {}).get("session_mode") != "background":
        raise AutoresearchError("runtime launch manifest did not record config.session_mode=background")
    if not isinstance(runtime.get("repo"), str) or Path(runtime["repo"]).resolve() != repo:
        raise AutoresearchError("runtime state points at the wrong repo")
    if not log_path.exists():
        raise AutoresearchError("runtime smoke did not produce a runtime log file")

    print("runtime invariants: OK")


def main() -> int:
    args = parse_args()
    repo = Path(args.repo).resolve()
    if not repo.exists():
        raise AutoresearchError(f"repo does not exist: {repo}")

    if args.mode == "exec":
        validate_exec(repo, args)
    elif args.mode == "interactive":
        validate_interactive(repo, args)
    else:
        validate_runtime(repo, args)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutoresearchError as exc:
        raise SystemExit(f"error: {exc}")
