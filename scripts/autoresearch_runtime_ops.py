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
    LAUNCH_MANIFEST_NAME,
    default_workspace_artifacts,
    detect_legacy_repo_root_artifacts,
    legacy_layout_error,
    repo_targets_from_config,
    read_launch_manifest,
    require_context_for_repo,
    resolve_context_workspace_root,
    RESULTS_FILE_NAME,
    resolve_state_path_for_log,
    RUNTIME_LOG_NAME,
    RUNTIME_STATE_NAME,
    STATE_FILE_NAME,
    sync_state_session_mode,
    utc_now,
    write_json_atomic,
)
from autoresearch_hook_context import update_hook_context_pointer, write_hook_context_pointer
from autoresearch_launch_gate import (
    evaluate_launch_context,
    inspect_process_identity,
    pid_is_alive,
    runtime_process_state,
)
from autoresearch_preflight import evaluate_managed_repos_preflight
from autoresearch_resume_prompt import build_runtime_prompt
from autoresearch_supervisor_status import evaluate_supervisor_status
from autoresearch_platform import (
    command_is_executable,
    current_runtime_process_group_id,
    runtime_popen_kwargs,
    runtime_process_group_id,
    signal_runtime_process_group,
)
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
    resolve_workspace_root,
)

STOP_POLL_INTERVAL_SECONDS = 0.1
STOP_KILL_WAIT_SECONDS = 1.0
HOOK_ACTIVE_ENV = "AUTORESEARCH_HOOK_ACTIVE"
HOOK_RESULTS_PATH_ENV = "AUTORESEARCH_HOOK_RESULTS_PATH"
HOOK_STATE_PATH_ENV = "AUTORESEARCH_HOOK_STATE_PATH"
HOOK_LAUNCH_PATH_ENV = "AUTORESEARCH_HOOK_LAUNCH_PATH"
HOOK_RUNTIME_PATH_ENV = "AUTORESEARCH_HOOK_RUNTIME_PATH"


def _resolve_workspace_relative(base: Path, raw: str | None, default_path: Path) -> Path:
    if raw is None:
        return default_path
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = base / candidate
    return candidate.resolve()


def resolve_runtime_paths(
    *,
    repo: Path,
    workspace_root_arg: str | None,
    results_path_arg: str | None,
    state_path_arg: str | None,
    launch_path_arg: str | None,
    runtime_path_arg: str | None,
    log_path_arg: str | None,
    require_context: bool,
) -> dict[str, Path | str]:
    existing_context = require_context_for_repo(repo) if require_context else None
    workspace_root = (
        resolve_context_workspace_root(
            repo=repo,
            context=existing_context,
            raw_workspace_root=workspace_root_arg,
        )
        if existing_context is not None
        else resolve_workspace_root(repo, workspace_root_arg)
    )
    defaults = default_workspace_artifacts(workspace_root)
    results_default = existing_context.results_path if existing_context is not None else defaults.results_path
    state_default = existing_context.state_path if existing_context is not None else defaults.state_path
    launch_default = (
        existing_context.launch_path
        if existing_context is not None and existing_context.launch_path is not None
        else defaults.launch_path
    )
    runtime_default = (
        existing_context.runtime_path
        if existing_context is not None and existing_context.runtime_path is not None
        else defaults.runtime_path
    )
    log_default = (
        existing_context.log_path
        if existing_context is not None and existing_context.log_path is not None
        else defaults.log_path
    )
    return {
        "workspace_root": workspace_root,
        "artifact_root": existing_context.artifact_root if existing_context is not None else defaults.artifact_root,
        "results_path": (
            results_default
            if results_path_arg in {None, DEFAULT_RESULTS_PATH}
            else _resolve_workspace_relative(workspace_root, results_path_arg, results_default)
        ),
        "state_path": _resolve_workspace_relative(workspace_root, state_path_arg, state_default)
        if state_path_arg is not None
        else state_default,
        "launch_path": _resolve_workspace_relative(workspace_root, launch_path_arg, launch_default),
        "runtime_path": _resolve_workspace_relative(workspace_root, runtime_path_arg, runtime_default),
        "log_path": _resolve_workspace_relative(workspace_root, log_path_arg, log_default),
    }


def resolve_explicit_runtime_paths(
    *,
    repo: Path,
    workspace_root_arg: str | None,
    results_path_arg: str | None,
    state_path_arg: str | None,
    launch_path_arg: str | None,
    runtime_path_arg: str | None,
    log_path_arg: str | None,
) -> dict[str, Path | str]:
    workspace_root = (
        resolve_workspace_root(repo, workspace_root_arg)
        if workspace_root_arg is not None
        else Path.cwd().resolve()
    )
    anchor_arg = next(
        (
            value
            for value in (
                None if results_path_arg in {None, DEFAULT_RESULTS_PATH} else results_path_arg,
                state_path_arg,
                launch_path_arg,
                runtime_path_arg,
                log_path_arg,
            )
            if value is not None
        ),
        None,
    )
    if anchor_arg is None:
        raise AutoresearchError("Explicit artifact paths require at least one artifact path argument.")
    anchor_path = _resolve_workspace_relative(workspace_root, anchor_arg, Path(anchor_arg))
    artifact_root = anchor_path.parent
    results_default = artifact_root / RESULTS_FILE_NAME
    state_default = artifact_root / STATE_FILE_NAME
    launch_default = artifact_root / LAUNCH_MANIFEST_NAME
    runtime_default = artifact_root / RUNTIME_STATE_NAME
    log_default = artifact_root / RUNTIME_LOG_NAME
    return {
        "workspace_root": workspace_root,
        "artifact_root": artifact_root,
        "results_path": (
            results_default
            if results_path_arg in {None, DEFAULT_RESULTS_PATH}
            else _resolve_workspace_relative(workspace_root, results_path_arg, results_default)
        ),
        "state_path": _resolve_workspace_relative(workspace_root, state_path_arg, state_default)
        if state_path_arg is not None
        else state_default,
        "launch_path": _resolve_workspace_relative(workspace_root, launch_path_arg, launch_default),
        "runtime_path": _resolve_workspace_relative(workspace_root, runtime_path_arg, runtime_default),
        "log_path": _resolve_workspace_relative(workspace_root, log_path_arg, log_default),
    }


def build_codex_exec_command(
    *,
    codex_bin: str,
    codex_args: list[str],
    repo: Path,
) -> list[str]:
    return [codex_bin, "exec", *codex_args, "-C", str(repo), "-"]


def mark_runtime_needs_human(
    *,
    repo: Path,
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
    update_hook_context_pointer(repo=repo, active=False, session_mode="background")
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
    default_state_path: Path | None = None,
) -> dict[str, Any]:
    runtime, runtime_error = load_runtime_with_error(runtime_path)
    runtime_state_path = runtime.get("state_path") if isinstance(runtime, dict) else None
    resolved_default_state_path = (
        default_state_path
        if default_state_path is not None
        else Path(runtime_state_path)
        if isinstance(runtime_state_path, str) and runtime_state_path
        else None
    )
    resolved_state_path = resolve_state_path_for_log(
        state_path_arg,
        None,
        cwd=repo,
        default_path=resolved_default_state_path,
        results_path=results_path,
    )

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

    runtime_state = runtime_process_state(runtime) if runtime is not None else None
    runtime_alive = (
        runtime_state is not None
        and bool(runtime_state["alive"])
        and bool(runtime_state["matches"])
    )

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

    if runtime is not None and runtime.get("status") in {"terminal", "stopped"}:
        return persisted_runtime_summary(
            runtime=runtime,
            runtime_path=runtime_path,
            launch_path=launch_path,
            results_path=results_path,
            state_path=resolved_state_path,
            runtime_running=bool(runtime_alive),
        )

    if (
        runtime is not None
        and runtime_state is not None
        and bool(runtime_state["alive"])
        and not bool(runtime_state["matches"])
    ):
        error = str(runtime_state["message"])
        reason = str(runtime_state["reason"])
        return persisted_runtime_summary(
            runtime=runtime,
            runtime_path=runtime_path,
            launch_path=launch_path,
            results_path=results_path,
            state_path=resolved_state_path,
            status="needs_human",
            reason=reason if reason != "identity_mismatch" else "runtime_identity_mismatch",
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

    launch_context = evaluate_launch_context(
        results_path=results_path,
        state_path_arg=state_path_arg,
        launch_path=launch_path,
        runtime_path=runtime_path,
        default_state_path=resolved_state_path,
        ignore_running_runtime=True,
    )
    try:
        supervisor = evaluate_supervisor_status(
            results_path=results_path,
            state_path_arg=str(resolved_state_path),
            default_state_path=resolved_state_path,
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
    legacy_error = legacy_layout_error(repo)
    if legacy_error is not None and not args.force:
        raise AutoresearchError(legacy_error)
    paths = resolve_runtime_paths(
        repo=repo,
        workspace_root_arg=getattr(args, "workspace_root", None),
        results_path_arg=getattr(args, "results_path", None),
        state_path_arg=getattr(args, "state_path", None),
        launch_path_arg=args.launch_path,
        runtime_path_arg=getattr(args, "runtime_path", None),
        log_path_arg=getattr(args, "log_path", None),
        require_context=False,
    )
    workspace_root = Path(paths["workspace_root"])
    launch_path = Path(paths["launch_path"])
    results_path = Path(paths["results_path"])
    state_path = Path(paths["state_path"])
    runtime_path = Path(paths["runtime_path"])
    log_path = Path(paths["log_path"])
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
    write_hook_context_pointer(
        repo=repo,
        active=True,
        session_mode="background",
        results_path=results_path,
        state_path=state_path,
        launch_path=launch_path,
        runtime_path=runtime_path,
        log_path=log_path,
        workspace_root=workspace_root,
        primary_repo=repo,
        repo_targets=manifest.get("config", {}).get("repos", []),
        verify_cwd=manifest.get("config", {}).get("verify_cwd"),
    )
    return {
        "workspace_root": str(workspace_root),
        "artifact_root": str(paths["artifact_root"]),
        "launch_path": str(launch_path),
        "mode": args.mode,
        "goal": args.goal,
        "original_goal": args.original_goal,
    }


def archive_interactive_fresh_start_artifacts(
    *,
    workspace_root: Path,
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

    state_path = (
        _resolve_workspace_relative(workspace_root, state_path_arg, default_workspace_artifacts(workspace_root).state_path)
        if state_path_arg is not None
        else default_workspace_artifacts(workspace_root).state_path
    )
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
    archived_hook_context = archive_path_to_prev(default_workspace_artifacts(workspace_root).context_path)
    if archived_hook_context is not None:
        archived.append(str(archived_hook_context))
    return archived


def archive_legacy_fresh_start_artifacts(repo: Path) -> list[str]:
    archived: list[str] = []
    for candidate in detect_legacy_repo_root_artifacts(repo):
        archived_path = archive_path_to_prev(candidate)
        if archived_path is not None:
            archived.append(str(archived_path))
    return archived


def evaluate_runtime_preflight(
    *,
    repo: Path,
    workspace_root: Path,
    results_path: Path,
    state_path_arg: str | None,
    launch_manifest: dict[str, Any],
    min_free_mb: int,
) -> dict[str, Any]:
    config = dict(launch_manifest.get("config", {}))
    return evaluate_managed_repos_preflight(
        primary_repo=repo,
        workspace_root=workspace_root,
        results_path=results_path,
        state_path_arg=state_path_arg,
        verify_command=str(config.get("verify", "")),
        verify_cwd=str(config.get("verify_cwd") or "workspace_root"),
        commit_phase="precommit",
        repo_targets=repo_targets_from_config(repo, config),
        min_free_mb=min_free_mb,
        include_health=True,
        rollback_policy=str(config.get("rollback_policy") or ""),
        destructive_approved=destructive_rollback_approved(launch_manifest),
    )


def start_runtime(args: argparse.Namespace, *, runner_path: Path) -> dict[str, Any]:
    repo = resolve_repo_path(args.repo)
    paths = resolve_runtime_paths(
        repo=repo,
        workspace_root_arg=getattr(args, "workspace_root", None),
        results_path_arg=args.results_path,
        state_path_arg=args.state_path,
        launch_path_arg=args.launch_path,
        runtime_path_arg=args.runtime_path,
        log_path_arg=args.log_path,
        require_context=True,
    )
    workspace_root = Path(paths["workspace_root"])
    launch_path = Path(paths["launch_path"])
    results_path = Path(paths["results_path"])
    runtime_path = Path(paths["runtime_path"])
    log_path = Path(paths["log_path"])
    state_path_arg = str(paths["state_path"])

    if not command_is_executable(args.codex_bin):
        raise AutoresearchError(f"Codex executable is not available: {args.codex_bin}")

    ensure_runtime_not_running(runtime_path)

    launch_context = evaluate_launch_context(
        results_path=results_path,
        state_path_arg=state_path_arg,
        launch_path=launch_path,
        runtime_path=runtime_path,
        default_state_path=Path(state_path_arg),
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
        workspace_root=workspace_root,
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
        "--workspace-root",
        str(workspace_root),
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
        cwd=workspace_root,
        stdin=subprocess.DEVNULL,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
        **runtime_popen_kwargs(),
    )
    log_handle.close()
    pgid = runtime_process_group_id(process.pid)
    identity = inspect_process_identity(process.pid)
    runtime = build_runtime_payload(
        repo=repo,
        launch_path=launch_path,
        results_path=results_path,
        state_path=Path(state_path_arg),
        log_path=log_path,
        status="running",
        pid=process.pid,
        pgid=pgid,
        command=command,
        process_started_at=(
            str(identity["started_at"]) if identity is not None and "started_at" in identity else None
        ),
        process_command=(
            str(identity["command"]) if identity is not None and "command" in identity else None
        ),
        terminal_reason="none",
    )
    runtime["launch_context"] = launch_context
    runtime["last_health_check"] = preflight["health_check"]
    runtime["last_commit_gate"] = preflight["commit_gate"]
    persist_runtime(runtime_path, runtime)
    write_hook_context_pointer(
        repo=repo,
        active=True,
        session_mode="background",
        results_path=results_path.resolve(),
        state_path=state_path.resolve(),
        launch_path=launch_path.resolve(),
        runtime_path=runtime_path.resolve(),
        log_path=log_path.resolve(),
        workspace_root=workspace_root,
        primary_repo=repo,
        repo_targets=launch_manifest.get("config", {}).get("repos", []),
        verify_cwd=launch_manifest.get("config", {}).get("verify_cwd"),
    )
    return {
        "status": "running",
        "pid": process.pid,
        "pgid": pgid,
        "workspace_root": str(workspace_root),
        "runtime_path": str(runtime_path),
        "launch_path": str(launch_path),
        "log_path": str(log_path),
    }


def launch_and_start_runtime(args: argparse.Namespace, *, runner_path: Path) -> dict[str, Any]:
    archived_paths: list[str] = []
    repo = resolve_repo_path(args.repo)
    paths = resolve_runtime_paths(
        repo=repo,
        workspace_root_arg=getattr(args, "workspace_root", None),
        results_path_arg=args.results_path,
        state_path_arg=args.state_path,
        launch_path_arg=args.launch_path,
        runtime_path_arg=args.runtime_path,
        log_path_arg=args.log_path,
        require_context=False,
    )
    workspace_root = Path(paths["workspace_root"])
    launch_path = Path(paths["launch_path"])
    runtime_path = Path(paths["runtime_path"])
    log_path = Path(paths["log_path"])
    ensure_runtime_not_running(runtime_path)
    if args.fresh_start:
        results_path = Path(paths["results_path"])
        archived_paths = archive_interactive_fresh_start_artifacts(
            workspace_root=workspace_root,
            results_path=results_path,
            state_path_arg=str(paths["state_path"]),
            launch_path=launch_path,
            runtime_path=runtime_path,
            log_path=log_path,
            mode=args.mode,
        )
        archived_paths.extend(archive_legacy_fresh_start_artifacts(repo))
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
    paths = resolve_runtime_paths(
        repo=repo,
        workspace_root_arg=getattr(args, "workspace_root", None),
        results_path_arg=args.results_path,
        state_path_arg=args.state_path,
        launch_path_arg=args.launch_path,
        runtime_path_arg=args.runtime_path,
        log_path_arg=args.log_path,
        require_context=True,
    )
    workspace_root = Path(paths["workspace_root"])
    launch_path = Path(paths["launch_path"])
    launch_manifest = read_launch_manifest(launch_path)
    results_path = Path(paths["results_path"])
    runtime_path = Path(paths["runtime_path"])
    log_path = Path(paths["log_path"])
    state_path_arg = str(paths["state_path"])
    runtime = load_runtime_if_exists(runtime_path)
    if runtime is None:
        identity = inspect_process_identity(os.getpid())
        runtime = build_runtime_payload(
            repo=repo,
            launch_path=launch_path,
            results_path=results_path,
            state_path=Path(state_path_arg),
            log_path=log_path,
            status="running",
            pid=os.getpid(),
            pgid=current_runtime_process_group_id(),
            command=[],
            process_started_at=(
                str(identity["started_at"]) if identity is not None and "started_at" in identity else None
            ),
            process_command=(
                str(identity["command"]) if identity is not None and "command" in identity else None
            ),
        )
        persist_runtime(runtime_path, runtime)
        write_hook_context_pointer(
            repo=repo,
            active=True,
            session_mode="background",
            results_path=results_path.resolve(),
            state_path=Path(state_path_arg).resolve(),
            launch_path=launch_path.resolve(),
            runtime_path=runtime_path.resolve(),
            log_path=log_path.resolve(),
            workspace_root=workspace_root,
            primary_repo=repo,
            repo_targets=launch_manifest.get("config", {}).get("repos", []),
            verify_cwd=launch_manifest.get("config", {}).get("verify_cwd"),
        )
    else:
        update_hook_context_pointer(
            repo=repo,
            active=True,
            session_mode="background",
            results_path=results_path.resolve(),
            state_path=Path(state_path_arg).resolve(),
            launch_path=launch_path.resolve(),
            runtime_path=runtime_path.resolve(),
            log_path=log_path.resolve(),
        )

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
            default_state_path=Path(state_path_arg),
            ignore_running_runtime=True,
        )
        if launch_context["decision"] not in {"fresh", "resumable"}:
            runtime["status"] = "needs_human"
            runtime["terminal_reason"] = launch_context["reason"]
            runtime["last_decision"] = launch_context["decision"]
            runtime["last_reason"] = launch_context["reason"]
            runtime["launch_context"] = launch_context
            persist_runtime(runtime_path, runtime)
            update_hook_context_pointer(repo=repo, active=False, session_mode="background")
            return 2

        preflight = evaluate_runtime_preflight(
            repo=repo,
            workspace_root=workspace_root,
            results_path=results_path,
            state_path_arg=state_path_arg,
            launch_manifest=launch_manifest,
            min_free_mb=args.min_free_mb,
        )
        runtime["last_health_check"] = preflight["health_check"]
        runtime["last_commit_gate"] = preflight["commit_gate"]
        if preflight["decision"] == "block":
            return mark_runtime_needs_human(
                repo=repo,
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
                repo=repo,
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
            codex_env = dict(os.environ)
            codex_env[HOOK_ACTIVE_ENV] = "1"
            codex_env[HOOK_RESULTS_PATH_ENV] = str(results_path)
            codex_env[HOOK_STATE_PATH_ENV] = str(state_path)
            codex_env[HOOK_LAUNCH_PATH_ENV] = str(launch_path)
            codex_env[HOOK_RUNTIME_PATH_ENV] = str(runtime_path)
            codex_exit = subprocess.run(
                codex_cmd,
                cwd=workspace_root,
                input=prompt_text,
                text=True,
                encoding="utf-8",
                env=codex_env,
            ).returncode
        except OSError as exc:
            return mark_runtime_needs_human(
                repo=repo,
                runtime=runtime,
                runtime_path=runtime_path,
                launch_context=launch_context,
                reason="codex_exec_unavailable",
                error=f"Failed to launch codex exec: {exc}",
            )

        supervisor = evaluate_supervisor_status(
            results_path=results_path,
            state_path_arg=state_path_arg,
            default_state_path=Path(state_path_arg),
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
            update_hook_context_pointer(repo=repo, active=True, session_mode="background")
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
        update_hook_context_pointer(repo=repo, active=False, session_mode="background")
        return 0 if decision == "stop" else 2


def stop_runtime(args: argparse.Namespace) -> dict[str, Any]:
    repo = resolve_repo_path(args.repo)
    explicit_runtime_path = getattr(args, "runtime_path", None)
    context_required = explicit_runtime_path is None
    if context_required:
        paths = resolve_runtime_paths(
            repo=repo,
            workspace_root_arg=getattr(args, "workspace_root", None),
            results_path_arg=None,
            state_path_arg=None,
            launch_path_arg=None,
            runtime_path_arg=None,
            log_path_arg=None,
            require_context=True,
        )
    else:
        paths = resolve_explicit_runtime_paths(
            repo=repo,
            workspace_root_arg=getattr(args, "workspace_root", None),
            results_path_arg=None,
            state_path_arg=None,
            launch_path_arg=None,
            runtime_path_arg=explicit_runtime_path,
            log_path_arg=None,
        )
    runtime_path = Path(paths["runtime_path"])
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

    runtime_state = runtime_process_state(runtime)
    if bool(runtime_state["alive"]) and not bool(runtime_state["matches"]):
        error = str(runtime_state["message"])
        reason = str(runtime_state["reason"])
        terminal_reason = reason if reason != "identity_mismatch" else "runtime_identity_mismatch"
        runtime["status"] = "needs_human"
        runtime["terminal_reason"] = terminal_reason
        runtime["last_decision"] = "needs_human"
        runtime["last_reason"] = terminal_reason
        runtime["last_error"] = error
        persist_runtime(runtime_path, runtime)
        return {
            "status": "needs_human",
            "runtime_path": str(runtime_path),
            "pid": pid,
            "pgid": pgid,
            "reason": terminal_reason,
            "error": error,
        }

    if bool(runtime_state["alive"]) and bool(runtime_state["matches"]):
        try:
            signal_runtime_process_group(pid=int(pid), pgid=int(pgid), sig=signal.SIGTERM)
        except ProcessLookupError:
            pass
        stopped_after_term = wait_for_process_exit(pid, timeout=args.grace_seconds)
        if not stopped_after_term:
            try:
                signal_runtime_process_group(
                    pid=int(pid),
                    pgid=int(pgid),
                    sig=getattr(signal, "SIGKILL", signal.SIGTERM),
                    force=True,
                )
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
    if context_required:
        update_hook_context_pointer(repo=repo, active=False, session_mode="background")
    else:
        try:
            update_hook_context_pointer(repo=repo, active=False, session_mode="background")
        except AutoresearchError:
            pass
    return {
        "status": "stopped",
        "runtime_path": str(runtime_path),
        "pid": pid,
        "pgid": pgid,
        "reason": "user_stopped",
    }
