#!/usr/bin/env python3
from __future__ import annotations

import argparse
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
    command_is_executable,
    default_launch_manifest_path,
    default_runtime_log_path,
    default_runtime_state_path,
    repo_targets_from_config,
    read_launch_manifest,
    resolve_state_path,
    resolve_state_path_for_log,
    sync_state_session_mode,
    utc_now,
    write_json_atomic,
)
from autoresearch_launch_gate import evaluate_launch_context, pid_is_alive
from autoresearch_preflight import evaluate_managed_repos_preflight
from autoresearch_resume_prompt import build_runtime_prompt
from autoresearch_supervisor_status import evaluate_supervisor_status
from autoresearch_runtime_common import (
    DEFAULT_EXECUTION_POLICY,
    DEFAULT_RESULTS_PATH,
    append_completion_summary_if_possible,
    codex_args_for_execution_policy,
    destructive_rollback_approved,
    ensure_runtime_not_running,
    load_runtime_if_exists,
    load_runtime_with_error,
    manifest_config_from_args,
    parse_key_value_pairs,
    persist_runtime,
    resolve_repo_path,
    resolve_repo_relative,
)

STOP_POLL_INTERVAL_SECONDS = 0.1
STOP_KILL_WAIT_SECONDS = 1.0


def build_codex_exec_command(
    *,
    codex_bin: str,
    codex_args: list[str],
    repo: Path,
) -> list[str]:
    return [codex_bin, "exec", *codex_args, "-C", str(repo), "-"]


def mark_runtime_needs_human(
    *,
    runtime: dict[str, Any],
    runtime_path: Path,
    launch_context: dict[str, Any],
    reason: str,
    error: str | None = None,
) -> int:
    runtime["status"] = "needs_human"
    runtime["terminal_reason"] = reason
    runtime["last_decision"] = "needs_human"
    runtime["last_reason"] = reason
    runtime["launch_context"] = launch_context
    if error:
        runtime["last_error"] = error
    else:
        runtime.pop("last_error", None)
    persist_runtime(runtime_path, runtime)
    return 2


def wait_for_process_exit(pid: int | None, *, timeout: float) -> bool:
    if not pid_is_alive(pid):
        return True
    deadline = time.time() + max(timeout, 0.0)
    while time.time() < deadline:
        time.sleep(STOP_POLL_INTERVAL_SECONDS)
        if not pid_is_alive(pid):
            return True
    return not pid_is_alive(pid)


def persisted_runtime_summary(
    *,
    runtime: dict[str, Any],
    runtime_path: Path,
    launch_path: Path,
    results_path: Path,
    state_path: Path,
    status: str | None = None,
    reason: str | None = None,
    runtime_running: bool = False,
    error: str | None = None,
) -> dict[str, Any]:
    payload = {
        "status": status or runtime.get("status"),
        "pid": runtime.get("pid"),
        "pgid": runtime.get("pgid"),
        "runtime_path": str(runtime_path),
        "log_path": runtime.get("log_path", ""),
        "reason": reason or runtime.get("terminal_reason", "none"),
        "launch_path": str(launch_path),
        "results_path": str(results_path),
        "state_path": str(state_path),
        "last_health_check": runtime.get("last_health_check"),
        "last_commit_gate": runtime.get("last_commit_gate"),
    }
    if runtime_running:
        payload["runtime_running"] = True
    effective_error = error or runtime.get("last_error")
    if effective_error:
        payload["error"] = effective_error
    return payload


def runtime_summary(
    *,
    repo: Path,
    results_path: Path,
    state_path_arg: str | None,
    launch_path: Path,
    runtime_path: Path,
) -> dict[str, Any]:
    runtime, runtime_error = load_runtime_with_error(runtime_path)
    resolved_state_path = resolve_state_path_for_log(state_path_arg, None, cwd=repo)

    if runtime_error is not None:
        return {
            "status": "needs_human",
            "runtime_path": str(runtime_path),
            "log_path": "",
            "reason": "invalid_runtime_state",
            "error": runtime_error,
            "launch_path": str(launch_path),
            "results_path": str(results_path),
            "state_path": str(resolved_state_path),
        }

    runtime_alive = runtime is not None and pid_is_alive(runtime.get("pid"))

    if runtime is not None and runtime.get("status") == "needs_human":
        return persisted_runtime_summary(
            runtime=runtime,
            runtime_path=runtime_path,
            launch_path=launch_path,
            results_path=results_path,
            state_path=resolved_state_path,
            runtime_running=bool(runtime_alive),
        )

    if runtime is not None and runtime.get("status") == "stopped" and runtime_alive:
        error = runtime.get("last_error") or "Runtime process is still alive after a stop request."
        return persisted_runtime_summary(
            runtime=runtime,
            runtime_path=runtime_path,
            launch_path=launch_path,
            results_path=results_path,
            state_path=resolved_state_path,
            status="needs_human",
            reason="stop_failed",
            runtime_running=True,
            error=error,
        )

    if runtime is not None and runtime_alive:
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
        return persisted_runtime_summary(
            runtime=runtime,
            runtime_path=runtime_path,
            launch_path=launch_path,
            results_path=results_path,
            state_path=resolved_state_path,
        )

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
    launch_path: Path,
    runtime_path: Path,
    log_path: Path,
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
    archived_launch = archive_path_to_prev(launch_path)
    if archived_launch is not None:
        archived.append(str(archived_launch))
    archived_runtime = archive_path_to_prev(runtime_path)
    if archived_runtime is not None:
        archived.append(str(archived_runtime))
    archived_log = archive_path_to_prev(log_path)
    if archived_log is not None:
        archived.append(str(archived_log))
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
    return evaluate_managed_repos_preflight(
        primary_repo=repo,
        results_path=results_path,
        state_path_arg=state_path_arg,
        verify_command=str(config.get("verify", "")),
        commit_phase="precommit",
        repo_targets=repo_targets_from_config(repo, config),
        min_free_mb=min_free_mb,
        include_health=True,
        rollback_policy=str(config.get("rollback_policy") or ""),
        destructive_approved=destructive_rollback_approved(launch_manifest),
    )


def start_runtime(args: argparse.Namespace, *, runner_path: Path) -> dict[str, Any]:
    repo = resolve_repo_path(args.repo)
    launch_path = resolve_repo_relative(repo, args.launch_path, default_launch_manifest_path(repo))
    results_path = resolve_repo_relative(repo, args.results_path, repo / DEFAULT_RESULTS_PATH)
    runtime_path = resolve_repo_relative(repo, args.runtime_path, default_runtime_state_path(repo))
    log_path = resolve_repo_relative(repo, args.log_path, default_runtime_log_path(repo))
    state_path_arg = args.state_path

    if not command_is_executable(args.codex_bin):
        raise AutoresearchError(f"Codex executable is not available: {args.codex_bin}")

    ensure_runtime_not_running(runtime_path)

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
        raise AutoresearchError(f"Missing JSON file: {launch_path}")

    launch_manifest = read_launch_manifest(launch_path)
    execution_policy = str(
        launch_manifest.get("config", {}).get("execution_policy") or DEFAULT_EXECUTION_POLICY
    )
    codex_args_for_execution_policy(
        execution_policy,
        extra_args=args.codex_arg,
    )
    preflight = evaluate_runtime_preflight(
        repo=repo,
        results_path=results_path,
        state_path_arg=state_path_arg,
        launch_manifest=launch_manifest,
        min_free_mb=args.min_free_mb,
    )
    if preflight["decision"] == "block":
        raise AutoresearchError("Runtime preflight failed: " + "; ".join(preflight["blockers"]))

    state_path = Path(launch_context["state_path"])
    if state_path.exists():
        sync_state_session_mode(
            state_path,
            session_mode="background",
            execution_policy=execution_policy,
        )

    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_handle = log_path.open("a", encoding="utf-8")
    command = [
        sys.executable,
        str(runner_path),
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


def launch_and_start_runtime(args: argparse.Namespace, *, runner_path: Path) -> dict[str, Any]:
    archived_paths: list[str] = []
    repo = resolve_repo_path(args.repo)
    launch_path = resolve_repo_relative(repo, args.launch_path, default_launch_manifest_path(repo))
    runtime_path = resolve_repo_relative(repo, args.runtime_path, default_runtime_state_path(repo))
    log_path = resolve_repo_relative(repo, args.log_path, default_runtime_log_path(repo))
    ensure_runtime_not_running(runtime_path)
    if args.fresh_start:
        results_path = resolve_repo_relative(repo, args.results_path, repo / DEFAULT_RESULTS_PATH)
        archived_paths = archive_interactive_fresh_start_artifacts(
            repo=repo,
            results_path=results_path,
            state_path_arg=args.state_path,
            launch_path=launch_path,
            runtime_path=runtime_path,
            log_path=log_path,
            mode=args.mode,
        )
        args.force = True
    created = create_launch_manifest(args)
    started = start_runtime(args, runner_path=runner_path)
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

    execution_policy = str(
        launch_manifest.get("config", {}).get("execution_policy") or DEFAULT_EXECUTION_POLICY
    )
    codex_args = codex_args_for_execution_policy(
        execution_policy,
        extra_args=args.codex_arg,
    )
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
            return mark_runtime_needs_human(
                runtime=runtime,
                runtime_path=runtime_path,
                launch_context=launch_context,
                reason=preflight["reason"],
            )

        state_path = Path(launch_context["state_path"])
        if state_path.exists():
            sync_state_session_mode(
                state_path,
                session_mode="background",
                execution_policy=execution_policy,
            )

        prompt_text = build_runtime_prompt(
            launch_manifest=launch_manifest,
            launch_context=launch_context,
            launch_path=launch_path,
            results_path=results_path,
            state_path=Path(launch_context["state_path"]),
        )
        runtime.pop("last_error", None)
        if not command_is_executable(args.codex_bin):
            return mark_runtime_needs_human(
                runtime=runtime,
                runtime_path=runtime_path,
                launch_context=launch_context,
                reason="codex_exec_unavailable",
                error=f"Codex executable is not available: {args.codex_bin}",
            )
        codex_cmd = build_codex_exec_command(
            codex_bin=args.codex_bin,
            codex_args=codex_args,
            repo=repo,
        )
        try:
            codex_exit = subprocess.run(
                codex_cmd,
                cwd=repo,
                input=prompt_text,
                text=True,
            ).returncode
        except OSError as exc:
            return mark_runtime_needs_human(
                runtime=runtime,
                runtime_path=runtime_path,
                launch_context=launch_context,
                reason="codex_exec_unavailable",
                error=f"Failed to launch codex exec: {exc}",
            )

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
    runtime, runtime_error = load_runtime_with_error(runtime_path)
    if runtime_error is not None:
        return {
            "status": "needs_human",
            "runtime_path": str(runtime_path),
            "reason": "invalid_runtime_state",
            "error": runtime_error,
        }
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
        stopped_after_term = wait_for_process_exit(pid, timeout=args.grace_seconds)
        if not stopped_after_term:
            try:
                os.killpg(int(pgid), signal.SIGKILL)
            except ProcessLookupError:
                pass
            stopped_after_kill = wait_for_process_exit(pid, timeout=STOP_KILL_WAIT_SECONDS)
            if not stopped_after_kill:
                error = f"Runtime process {pid} remained alive after SIGKILL."
                runtime["status"] = "needs_human"
                runtime["terminal_reason"] = "stop_failed"
                runtime["last_decision"] = "needs_human"
                runtime["last_reason"] = "stop_failed"
                runtime["last_error"] = error
                persist_runtime(runtime_path, runtime)
                return {
                    "status": "needs_human",
                    "runtime_path": str(runtime_path),
                    "pid": pid,
                    "pgid": pgid,
                    "reason": "stop_failed",
                    "error": error,
                }

    append_completion_summary_if_possible(
        results_path=Path(str(runtime["results_path"])),
        state_path=Path(str(runtime["state_path"])),
    )
    runtime["status"] = "stopped"
    runtime["terminal_reason"] = "user_stopped"
    runtime.pop("last_error", None)
    persist_runtime(runtime_path, runtime)
    return {
        "status": "stopped",
        "runtime_path": str(runtime_path),
        "pid": pid,
        "pgid": pgid,
        "reason": "user_stopped",
    }
