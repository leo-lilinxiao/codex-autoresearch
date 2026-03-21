#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from autoresearch_helpers import (
    AutoresearchError,
    archive_path_to_prev,
    build_launch_manifest,
    build_runtime_payload,
    default_launch_manifest_path,
    default_runtime_log_path,
    default_runtime_state_path,
    read_state_payload,
    read_launch_manifest,
    read_runtime_payload,
    resolve_state_path,
    resolve_state_path_for_log,
    synthesize_launch_manifest_from_state,
    utc_now,
    write_json_atomic,
)
from autoresearch_lessons import append_summary_lesson_if_needed, lessons_path_from_results
from autoresearch_launch_gate import evaluate_launch_context, pid_is_alive
from autoresearch_preflight import evaluate_repo_preflight
from autoresearch_resume_prompt import build_runtime_prompt
from autoresearch_supervisor_status import evaluate_supervisor_status


DEFAULT_RESULTS_PATH = "research-results.tsv"
DEFAULT_CODEX_ARGS = ["--full-auto"]
DEFAULT_HEALTH_MIN_FREE_MB = 500


def resolve_repo_path(repo_arg: str | None) -> Path:
    return Path(repo_arg or Path.cwd()).resolve()


def resolve_repo_relative(repo: Path, raw: str | None, default_path: Path) -> Path:
    if raw is None:
        return default_path
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = repo / candidate
    return candidate.resolve()


def parse_key_value_pairs(values: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise AutoresearchError(f"Expected KEY=VALUE, got: {value!r}")
        key, raw_value = value.split("=", 1)
        key = key.strip()
        if not key:
            raise AutoresearchError(f"Invalid empty key in: {value!r}")
        parsed[key] = raw_value.strip()
    return parsed


def load_runtime_if_exists(runtime_path: Path) -> dict[str, Any] | None:
    if not runtime_path.exists():
        return None
    return read_runtime_payload(runtime_path)


def persist_runtime(runtime_path: Path, payload: dict[str, Any]) -> None:
    payload = dict(payload)
    payload["updated_at"] = utc_now()
    write_json_atomic(runtime_path, payload)


def append_completion_summary_if_possible(
    *,
    results_path: Path,
    state_path: Path,
) -> None:
    if not results_path.exists() or not state_path.exists():
        return
    try:
        state_payload = read_state_payload(state_path)
        append_summary_lesson_if_needed(
            lessons_path=lessons_path_from_results(results_path),
            state_payload=state_payload,
            current_iteration=int(state_payload.get("state", {}).get("iteration", 0)),
        )
    except (AutoresearchError, OSError, ValueError, TypeError):
        return


def manifest_config_from_args(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "goal": args.goal,
        "scope": args.scope,
        "metric": args.metric_name,
        "direction": args.direction,
        "verify": args.verify,
        "guard": args.guard,
        "iterations": args.iterations,
        "run_tag": args.run_tag,
        "stop_condition": args.stop_condition,
        "rollback_policy": args.rollback_policy,
        "parallel_mode": args.parallel_mode,
        "web_search": args.web_search,
    }


def destructive_rollback_approved(launch_manifest: dict[str, Any]) -> bool:
    approvals = launch_manifest.get("approvals", {})
    if not isinstance(approvals, dict):
        return False
    for key in ("destructive_rollback", "rollback", "destructive"):
        value = approvals.get(key)
        if value in {True, "true", "yes", "approved", "allow"}:
            return True
    return False


def runtime_summary(
    *,
    repo: Path,
    results_path: Path,
    state_path_arg: str | None,
    launch_path: Path,
    runtime_path: Path,
) -> dict[str, Any]:
    runtime = load_runtime_if_exists(runtime_path)
    resolved_state_path = resolve_state_path_for_log(state_path_arg, None, cwd=repo)

    if runtime is not None and pid_is_alive(runtime.get("pid")):
        return {
            "status": "running",
            "pid": runtime.get("pid"),
            "pgid": runtime.get("pgid"),
            "runtime_path": str(runtime_path),
            "log_path": runtime.get("log_path", ""),
            "reason": "runtime_active",
            "launch_path": str(launch_path),
            "results_path": str(results_path),
            "state_path": str(resolved_state_path),
            "last_health_check": runtime.get("last_health_check"),
            "last_commit_gate": runtime.get("last_commit_gate"),
        }

    if runtime is not None and runtime.get("status") in {"terminal", "needs_human", "stopped"}:
        return {
            "status": runtime.get("status"),
            "pid": runtime.get("pid"),
            "pgid": runtime.get("pgid"),
            "runtime_path": str(runtime_path),
            "log_path": runtime.get("log_path", ""),
            "reason": runtime.get("terminal_reason", "none"),
            "launch_path": str(launch_path),
            "results_path": str(results_path),
            "state_path": str(resolved_state_path),
            "last_health_check": runtime.get("last_health_check"),
            "last_commit_gate": runtime.get("last_commit_gate"),
        }

    launch_context = evaluate_launch_context(
        results_path=results_path,
        state_path_arg=state_path_arg,
        launch_path=launch_path,
        runtime_path=runtime_path,
        ignore_running_runtime=True,
    )
    try:
        supervisor = evaluate_supervisor_status(
            results_path=results_path,
            state_path_arg=str(resolved_state_path),
            max_stagnation=3,
            after_run=False,
            write_state=False,
        )
    except AutoresearchError:
        supervisor = None

    if supervisor is not None:
        if supervisor["decision"] == "stop":
            return {
                "status": "terminal",
                "runtime_path": str(runtime_path),
                "log_path": runtime.get("log_path", "") if runtime else "",
                "reason": supervisor["reason"],
                "launch_context": launch_context,
                "supervisor": supervisor,
            }
        if supervisor["decision"] == "needs_human":
            return {
                "status": "needs_human",
                "runtime_path": str(runtime_path),
                "log_path": runtime.get("log_path", "") if runtime else "",
                "reason": supervisor["reason"],
                "launch_context": launch_context,
                "supervisor": supervisor,
            }
        return {
            "status": "idle",
            "runtime_path": str(runtime_path),
            "log_path": runtime.get("log_path", "") if runtime else "",
            "reason": launch_context["reason"],
            "launch_context": launch_context,
            "supervisor": supervisor,
        }

    return {
        "status": "idle",
        "runtime_path": str(runtime_path),
        "log_path": runtime.get("log_path", "") if runtime else "",
        "reason": launch_context["reason"],
        "launch_context": launch_context,
    }


def create_launch_manifest(args: argparse.Namespace) -> dict[str, Any]:
    repo = resolve_repo_path(args.repo)
    launch_path = resolve_repo_relative(repo, args.launch_path, default_launch_manifest_path(repo))
    if launch_path.exists() and not args.force:
        raise AutoresearchError(f"{launch_path} already exists. Use --force to replace it.")

    manifest = build_launch_manifest(
        original_goal=args.original_goal,
        prompt_text=args.prompt_text or args.original_goal,
        mode=args.mode,
        config=manifest_config_from_args(args),
        approvals=parse_key_value_pairs(args.approval),
        defaults=parse_key_value_pairs(args.default),
        resume_seed=parse_key_value_pairs(args.resume_seed),
        notes=args.note,
    )
    write_json_atomic(launch_path, manifest)
    return {
        "launch_path": str(launch_path),
        "mode": args.mode,
        "goal": args.goal,
        "original_goal": args.original_goal,
    }


def archive_interactive_fresh_start_artifacts(
    *,
    repo: Path,
    results_path: Path,
    state_path_arg: str | None,
    mode: str,
) -> list[str]:
    if mode == "exec":
        return []

    archived: list[str] = []
    archived_results = archive_path_to_prev(results_path)
    if archived_results is not None:
        archived.append(str(archived_results))

    state_path = resolve_state_path(state_path_arg, mode=mode, cwd=repo)
    archived_state = archive_path_to_prev(state_path)
    if archived_state is not None:
        archived.append(str(archived_state))
    return archived


def evaluate_runtime_preflight(
    *,
    repo: Path,
    results_path: Path,
    state_path_arg: str | None,
    launch_manifest: dict[str, Any],
    min_free_mb: int,
) -> dict[str, Any]:
    config = dict(launch_manifest.get("config", {}))
    return evaluate_repo_preflight(
        repo=repo,
        results_path=results_path,
        state_path_arg=state_path_arg,
        verify_command=str(config.get("verify", "")),
        scope_text=str(config.get("scope") or ""),
        commit_phase="precommit",
        min_free_mb=min_free_mb,
        include_health=True,
        rollback_policy=str(config.get("rollback_policy") or ""),
        destructive_approved=destructive_rollback_approved(launch_manifest),
    )


def start_runtime(args: argparse.Namespace) -> dict[str, Any]:
    repo = resolve_repo_path(args.repo)
    launch_path = resolve_repo_relative(repo, args.launch_path, default_launch_manifest_path(repo))
    results_path = resolve_repo_relative(repo, args.results_path, repo / DEFAULT_RESULTS_PATH)
    runtime_path = resolve_repo_relative(repo, args.runtime_path, default_runtime_state_path(repo))
    log_path = resolve_repo_relative(repo, args.log_path, default_runtime_log_path(repo))
    state_path_arg = args.state_path

    existing = load_runtime_if_exists(runtime_path)
    if existing is not None and pid_is_alive(existing.get("pid")):
        raise AutoresearchError("An autoresearch runtime is already running for this repo.")

    launch_context = evaluate_launch_context(
        results_path=results_path,
        state_path_arg=state_path_arg,
        launch_path=launch_path,
        runtime_path=runtime_path,
    )
    if launch_context["decision"] not in {"fresh", "resumable"}:
        raise AutoresearchError(
            f"Cannot start runtime while launch gate reports {launch_context['decision']}: {launch_context['reason']}"
        )

    if not launch_path.exists():
        if launch_context["reason"] != "legacy_resume":
            raise AutoresearchError(f"Missing JSON file: {launch_path}")
        synthesize_launch_manifest_from_state(
            launch_path=launch_path,
            state_path=Path(launch_context["state_path"]),
        )

    # The detached runtime is only valid after the interactive "go" boundary has
    # produced a confirmed launch manifest or the controller has synthesized one
    # from a validated legacy full-resume state.
    launch_manifest = read_launch_manifest(launch_path)
    preflight = evaluate_runtime_preflight(
        repo=repo,
        results_path=results_path,
        state_path_arg=state_path_arg,
        launch_manifest=launch_manifest,
        min_free_mb=args.min_free_mb,
    )
    if preflight["decision"] == "block":
        raise AutoresearchError("Runtime preflight failed: " + "; ".join(preflight["blockers"]))

    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_handle = log_path.open("a", encoding="utf-8")
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "run",
        "--repo",
        str(repo),
        "--launch-path",
        str(launch_path),
        "--results-path",
        str(results_path),
        "--runtime-path",
        str(runtime_path),
        "--log-path",
        str(log_path),
        "--sleep-seconds",
        str(args.sleep_seconds),
        "--max-stagnation",
        str(args.max_stagnation),
        "--codex-bin",
        args.codex_bin,
    ]
    if state_path_arg:
        command.extend(["--state-path", state_path_arg])
    for value in args.codex_arg:
        command.extend(["--codex-arg", value])

    process = subprocess.Popen(
        command,
        cwd=repo,
        stdin=subprocess.DEVNULL,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )
    log_handle.close()
    pgid = os.getpgid(process.pid)
    runtime = build_runtime_payload(
        repo=repo,
        launch_path=launch_path,
        results_path=results_path,
        state_path=resolve_state_path_for_log(state_path_arg, None, cwd=repo),
        log_path=log_path,
        status="running",
        pid=process.pid,
        pgid=pgid,
        command=command,
        terminal_reason="none",
    )
    runtime["launch_context"] = launch_context
    runtime["last_health_check"] = preflight["health_check"]
    runtime["last_commit_gate"] = preflight["commit_gate"]
    persist_runtime(runtime_path, runtime)
    return {
        "status": "running",
        "pid": process.pid,
        "pgid": pgid,
        "runtime_path": str(runtime_path),
        "launch_path": str(launch_path),
        "log_path": str(log_path),
    }


def launch_and_start_runtime(args: argparse.Namespace) -> dict[str, Any]:
    archived_paths: list[str] = []
    if args.fresh_start:
        repo = resolve_repo_path(args.repo)
        results_path = resolve_repo_relative(repo, args.results_path, repo / DEFAULT_RESULTS_PATH)
        archived_paths = archive_interactive_fresh_start_artifacts(
            repo=repo,
            results_path=results_path,
            state_path_arg=args.state_path,
            mode=args.mode,
        )
        args.force = True
    created = create_launch_manifest(args)
    started = start_runtime(args)
    payload = {
        "status": started["status"],
        "pid": started["pid"],
        "pgid": started["pgid"],
        "launch_path": created["launch_path"],
        "runtime_path": started["runtime_path"],
        "log_path": started["log_path"],
        "mode": created["mode"],
        "goal": created["goal"],
    }
    if archived_paths:
        payload["archived_paths"] = archived_paths
    return payload


def run_runtime(args: argparse.Namespace) -> int:
    repo = resolve_repo_path(args.repo)
    launch_path = resolve_repo_relative(repo, args.launch_path, default_launch_manifest_path(repo))
    launch_manifest = read_launch_manifest(launch_path)
    results_path = resolve_repo_relative(repo, args.results_path, repo / DEFAULT_RESULTS_PATH)
    runtime_path = resolve_repo_relative(repo, args.runtime_path, default_runtime_state_path(repo))
    log_path = resolve_repo_relative(repo, args.log_path, default_runtime_log_path(repo))
    state_path_arg = args.state_path
    runtime = load_runtime_if_exists(runtime_path)
    if runtime is None:
        runtime = build_runtime_payload(
            repo=repo,
            launch_path=launch_path,
            results_path=results_path,
            state_path=resolve_state_path_for_log(state_path_arg, None, cwd=repo),
            log_path=log_path,
            status="running",
            pid=os.getpid(),
            pgid=os.getpgid(0),
            command=[],
        )
        persist_runtime(runtime_path, runtime)

    codex_args = list(DEFAULT_CODEX_ARGS)
    if args.codex_arg:
        codex_args = args.codex_arg
    startup_failure_count = 0
    while True:
        launch_context = evaluate_launch_context(
            results_path=results_path,
            state_path_arg=state_path_arg,
            launch_path=launch_path,
            runtime_path=runtime_path,
            ignore_running_runtime=True,
        )
        if launch_context["decision"] not in {"fresh", "resumable"}:
            runtime["status"] = "needs_human"
            runtime["terminal_reason"] = launch_context["reason"]
            runtime["last_decision"] = launch_context["decision"]
            runtime["last_reason"] = launch_context["reason"]
            runtime["launch_context"] = launch_context
            persist_runtime(runtime_path, runtime)
            return 2

        preflight = evaluate_runtime_preflight(
            repo=repo,
            results_path=results_path,
            state_path_arg=state_path_arg,
            launch_manifest=launch_manifest,
            min_free_mb=args.min_free_mb,
        )
        runtime["last_health_check"] = preflight["health_check"]
        runtime["last_commit_gate"] = preflight["commit_gate"]
        if preflight["decision"] == "block":
            runtime["status"] = "needs_human"
            runtime["terminal_reason"] = preflight["reason"]
            runtime["last_decision"] = "needs_human"
            runtime["last_reason"] = preflight["reason"]
            runtime["launch_context"] = launch_context
            persist_runtime(runtime_path, runtime)
            return 2

        prompt_text = build_runtime_prompt(
            launch_manifest=launch_manifest,
            launch_context=launch_context,
            launch_path=launch_path,
            results_path=results_path,
            state_path=Path(launch_context["state_path"]),
        )
        codex_cmd = [args.codex_bin, *codex_args, "-C", str(repo), prompt_text]
        codex_exit = subprocess.run(codex_cmd, cwd=repo).returncode

        supervisor = evaluate_supervisor_status(
            results_path=results_path,
            state_path_arg=state_path_arg,
            max_stagnation=args.max_stagnation,
            after_run=True,
            write_state=True,
        )
        decision = supervisor["decision"]
        reason = supervisor["reason"]
        if reason == "missing_artifacts":
            startup_failure_count += 1
            if codex_exit == 0:
                decision = "needs_human"
                reason = "missing_artifacts_after_success"
            elif startup_failure_count >= args.max_stagnation:
                decision = "needs_human"
                reason = "startup_failed_before_artifacts"
        else:
            startup_failure_count = 0

        runtime["last_decision"] = decision
        runtime["last_reason"] = reason
        runtime["last_seen_iteration"] = supervisor.get("iteration")
        runtime["last_seen_status"] = supervisor.get("last_status", "")
        runtime["launch_context"] = launch_context

        if decision == "relaunch":
            runtime["status"] = "running"
            runtime["terminal_reason"] = "none"
            persist_runtime(runtime_path, runtime)
            time.sleep(args.sleep_seconds)
            continue

        if decision in {"stop", "needs_human"}:
            append_completion_summary_if_possible(
                results_path=results_path,
                state_path=Path(str(runtime["state_path"])),
            )

        runtime["status"] = "terminal" if decision == "stop" else "needs_human"
        runtime["terminal_reason"] = reason
        persist_runtime(runtime_path, runtime)
        return 0 if decision == "stop" else 2


def stop_runtime(args: argparse.Namespace) -> dict[str, Any]:
    repo = resolve_repo_path(args.repo)
    runtime_path = resolve_repo_relative(repo, args.runtime_path, default_runtime_state_path(repo))
    runtime = load_runtime_if_exists(runtime_path)
    if runtime is None:
        raise AutoresearchError(f"No runtime file found at {runtime_path}")

    pid = runtime.get("pid")
    pgid = runtime.get("pgid") or pid
    runtime["requested_stop_at"] = utc_now()
    persist_runtime(runtime_path, runtime)

    if pid_is_alive(pid):
        try:
            os.killpg(int(pgid), signal.SIGTERM)
        except ProcessLookupError:
            pass
        deadline = time.time() + args.grace_seconds
        while time.time() < deadline and pid_is_alive(pid):
            time.sleep(0.1)
        if pid_is_alive(pid):
            try:
                os.killpg(int(pgid), signal.SIGKILL)
            except ProcessLookupError:
                pass

    append_completion_summary_if_possible(
        results_path=Path(str(runtime["results_path"])),
        state_path=Path(str(runtime["state_path"])),
    )
    runtime["status"] = "stopped"
    runtime["terminal_reason"] = "user_stopped"
    persist_runtime(runtime_path, runtime)
    return {
        "status": "stopped",
        "runtime_path": str(runtime_path),
        "pid": pid,
        "pgid": pgid,
        "reason": "user_stopped",
    }


def add_manifest_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo")
    parser.add_argument("--launch-path")
    parser.add_argument("--original-goal", required=True)
    parser.add_argument("--prompt-text")
    parser.add_argument("--mode", default="loop")
    parser.add_argument("--goal", required=True)
    parser.add_argument("--scope", required=True)
    parser.add_argument("--metric-name", required=True)
    parser.add_argument("--direction", required=True, choices=["lower", "higher"])
    parser.add_argument("--verify", required=True)
    parser.add_argument("--guard")
    parser.add_argument("--iterations", type=int)
    parser.add_argument("--run-tag")
    parser.add_argument("--stop-condition")
    parser.add_argument("--rollback-policy")
    parser.add_argument("--parallel-mode", choices=["serial", "parallel"], default="serial")
    parser.add_argument("--web-search", choices=["enabled", "disabled"], default="disabled")
    parser.add_argument("--approval", action="append", default=[])
    parser.add_argument("--default", action="append", default=[])
    parser.add_argument("--resume-seed", action="append", default=[])
    parser.add_argument("--note", action="append", default=[])
    parser.add_argument("--force", action="store_true")


def add_runtime_start_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--results-path", default=DEFAULT_RESULTS_PATH)
    parser.add_argument("--state-path")
    parser.add_argument("--runtime-path")
    parser.add_argument("--log-path")
    parser.add_argument("--sleep-seconds", type=int, default=5)
    parser.add_argument("--max-stagnation", type=int, default=3)
    parser.add_argument("--min-free-mb", type=int, default=DEFAULT_HEALTH_MIN_FREE_MB)
    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument("--codex-arg", action="append", default=[])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Control the runtime-managed single-entry autoresearch loop."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create-launch", help="Write the confirmed launch manifest.")
    add_manifest_args(create)

    launch = subparsers.add_parser(
        "launch",
        help="Atomically persist the confirmed launch manifest and start the detached runtime.",
    )
    add_manifest_args(launch)
    add_runtime_start_args(launch)
    launch.add_argument(
        "--fresh-start",
        action="store_true",
        help="Archive prior persistent results/state artifacts before starting a new interactive run.",
    )

    start = subparsers.add_parser("start", help="Start the detached autoresearch runtime.")
    start.add_argument("--repo")
    start.add_argument("--launch-path")
    add_runtime_start_args(start)

    run = subparsers.add_parser("run", help="Internal loop used by the detached runtime.")
    run.add_argument("--repo")
    run.add_argument("--launch-path")
    add_runtime_start_args(run)

    status = subparsers.add_parser("status", help="Inspect the current runtime status.")
    status.add_argument("--repo")
    status.add_argument("--launch-path")
    status.add_argument("--results-path", default=DEFAULT_RESULTS_PATH)
    status.add_argument("--state-path")
    status.add_argument("--runtime-path")

    stop = subparsers.add_parser("stop", help="Stop the detached runtime.")
    stop.add_argument("--repo")
    stop.add_argument("--runtime-path")
    stop.add_argument("--grace-seconds", type=float, default=5.0)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "create-launch":
        print(json.dumps(create_launch_manifest(args), indent=2, sort_keys=True))
        return 0
    if args.command == "launch":
        print(json.dumps(launch_and_start_runtime(args), indent=2, sort_keys=True))
        return 0
    if args.command == "start":
        print(json.dumps(start_runtime(args), indent=2, sort_keys=True))
        return 0
    if args.command == "run":
        return run_runtime(args)
    if args.command == "status":
        repo = resolve_repo_path(args.repo)
        results_path = resolve_repo_relative(repo, args.results_path, repo / DEFAULT_RESULTS_PATH)
        launch_path = resolve_repo_relative(repo, args.launch_path, default_launch_manifest_path(repo))
        runtime_path = resolve_repo_relative(repo, args.runtime_path, default_runtime_state_path(repo))
        print(
            json.dumps(
                runtime_summary(
                    repo=repo,
                    results_path=results_path,
                    state_path_arg=args.state_path,
                    launch_path=launch_path,
                    runtime_path=runtime_path,
                ),
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if args.command == "stop":
        print(json.dumps(stop_runtime(args), indent=2, sort_keys=True))
        return 0
    raise AutoresearchError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutoresearchError as exc:
        raise SystemExit(f"error: {exc}")
