#!/usr/bin/env python3
"""Command line control plane for codex-autoresearch."""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import signal
import subprocess
import sys
import time
import traceback
import uuid
from pathlib import Path
from typing import Any, NoReturn

from autoresearch_core import (
    AutoresearchError,
    Paths,
    RunState,
    SCHEMA_VERSION,
    append_event,
    append_json_line,
    commit_trial,
    decimal_json,
    git_branch,
    git_head,
    improved,
    json_text,
    load_context,
    load_run,
    load_runtime,
    next_command_log,
    normalize_scopes,
    parse_decimal,
    parse_json,
    parse_metric_output,
    paths_for,
    process_alive,
    relative_log_path,
    require_clean_repo,
    require_artifacts_untracked,
    require_git_repo,
    require_git_identity,
    require_no_staged_artifacts,
    require_exact_keys,
    require_paths_in_scope,
    revert_trial,
    run_command,
    status_payload,
    target_reached,
    terminate_process_tree,
    utc_now,
    validate_run,
    working_paths,
    write_json_atomic,
    write_runtime,
    write_text_atomic,
)
from autoresearch_report import render_history_table, render_history_tsv, render_html_report


def print_json(payload: dict[str, Any]) -> None:
    print(json_text(payload, pretty=True))


def add_repo_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo", required=True, help="Absolute or relative Git repository root.")


def add_run_arguments(parser: argparse.ArgumentParser, *, background: bool) -> None:
    add_repo_argument(parser)
    parser.add_argument("--goal", required=True)
    parser.add_argument(
        "--scope",
        action="append",
        required=True,
        help="Repository-relative file or directory. Repeat for multiple paths; globs are rejected.",
    )
    parser.add_argument("--metric-name", required=True)
    parser.add_argument("--direction", choices=["lower", "higher"], required=True)
    parser.add_argument("--verify", required=True, help="Command whose final stdout line is the metric.")
    parser.add_argument("--metric-key", help="Read the metric from this key in a final-line JSON object.")
    parser.add_argument("--target", required=True)
    parser.add_argument("--guard", help="Regression command; exit code 0 means pass.")
    parser.add_argument("--max-iterations", type=int)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    if background:
        parser.add_argument(
            "--execution-policy",
            choices=["danger-full-access", "workspace-write"],
            default="danger-full-access",
            help="Permission policy for background codex exec workers.",
        )
        parser.add_argument("--codex-bin", default="codex")
        parser.add_argument("--model")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run measurable, Git-backed autoresearch experiments with strict state validation."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Validate and initialize a foreground run.")
    add_run_arguments(init_parser, background=False)
    init_parser.set_defaults(mode="foreground")

    launch_parser = subparsers.add_parser("launch", help="Initialize and detach a background run.")
    add_run_arguments(launch_parser, background=True)
    launch_parser.set_defaults(mode="background")

    finish_parser = subparsers.add_parser(
        "finish", help="Commit, verify, and keep or revert one focused experiment."
    )
    add_repo_argument(finish_parser)
    finish_parser.add_argument("--description", required=True)

    block_parser = subparsers.add_parser("block", help="Stop on a genuine external blocker.")
    add_repo_argument(block_parser)
    block_parser.add_argument("--reason", required=True)

    status_parser = subparsers.add_parser("status", help="Print validated run and runtime status.")
    add_repo_argument(status_parser)

    history_parser = subparsers.add_parser(
        "history", help="Print a validated human-readable or TSV experiment history."
    )
    add_repo_argument(history_parser)
    history_parser.add_argument("--format", choices=["table", "tsv"], default="table")

    report_parser = subparsers.add_parser(
        "report", help="Generate a self-contained static HTML report."
    )
    add_repo_argument(report_parser)

    stop_parser = subparsers.add_parser("stop", help="Stop a detached background run.")
    add_repo_argument(stop_parser)

    resume_parser = subparsers.add_parser("resume", help="Resume a stopped or blocked run.")
    add_repo_argument(resume_parser)
    resume_parser.add_argument(
        "--note",
        default="Continue the confirmed experiment.",
        help="Optional new direction or explanation of what changed.",
    )

    archive_parser = subparsers.add_parser(
        "archive", help="Archive the current run before starting a different one."
    )
    add_repo_argument(archive_parser)

    controller_parser = subparsers.add_parser(
        "_controller", help="Internal entry point for the detached background controller."
    )
    add_repo_argument(controller_parser)

    return parser


def ensure_new_results_root(repo: Path) -> None:
    paths = paths_for(repo)
    existing = []
    if paths.root.exists():
        existing = sorted(child.name for child in paths.root.iterdir() if child.name != "archive")
    if existing:
        raise AutoresearchError(
            f"Autoresearch state already exists at {paths.root}: {', '.join(existing)}. "
            "Use status, resume, or archive before starting a new run."
        )
    paths.root.mkdir(parents=True, exist_ok=True)
    paths.logs.mkdir(parents=True, exist_ok=True)


def write_init_error(repo: Path, error: Exception) -> None:
    paths = paths_for(repo)
    if not paths.root.exists():
        return
    write_json_atomic(
        paths.root / "init-error.json",
        {
            "time": utc_now(),
            "error_type": type(error).__name__,
            "message": str(error),
            "traceback": traceback.format_exc(),
        },
    )


def require_no_initialized_state(paths: Paths, *, command_name: str, log_path: Path) -> None:
    created = [
        path
        for path in paths.root.iterdir()
        if path.name not in {"archive", paths.logs.name}
    ]
    if created:
        raise AutoresearchError(
            f"{command_name} created autoresearch control files: "
            + ", ".join(str(path) for path in created)
            + f". Full output: {log_path}"
        )


def control_state_snapshot(paths: Paths) -> tuple[bytes, bytes]:
    try:
        return paths.run.read_bytes(), paths.events.read_bytes()
    except OSError as exc:
        raise AutoresearchError(f"Cannot snapshot autoresearch control state: {exc}") from exc


def require_control_state_unchanged(
    paths: Paths,
    snapshot: tuple[bytes, bytes],
    *,
    command_name: str,
    log_path: Path,
) -> None:
    try:
        current = (paths.run.read_bytes(), paths.events.read_bytes())
    except OSError as exc:
        raise AutoresearchError(
            f"{command_name} removed or replaced autoresearch control state: {exc}. "
            f"Full output: {log_path}"
        ) from exc
    if current != snapshot:
        raise AutoresearchError(
            f"{command_name} modified run.json or events.jsonl. Full output: {log_path}"
        )


def require_command_preserved_repository(
    repo: Path,
    *,
    expected_head: str,
    expected_branch: str,
    command_name: str,
    log_path: Path,
) -> None:
    problems: list[str] = []
    dirty = working_paths(repo)
    if dirty:
        problems.append("changed paths " + ", ".join(dirty))
    current_head = git_head(repo)
    if current_head != expected_head:
        problems.append(f"moved HEAD from {expected_head} to {current_head}")
    try:
        current_branch = git_branch(repo)
    except AutoresearchError as exc:
        problems.append(str(exc))
    else:
        if current_branch != expected_branch:
            problems.append(f"switched branch from {expected_branch} to {current_branch}")
    if problems:
        raise AutoresearchError(
            f"{command_name} modified the repository: {'; '.join(problems)}. "
            f"Full output: {log_path}"
        )


def initialize_run(args: argparse.Namespace) -> dict[str, Any]:
    repo = Path(args.repo).expanduser().resolve()
    require_git_repo(repo)
    require_git_identity(repo)
    require_artifacts_untracked(repo)
    require_clean_repo(repo)
    require_no_staged_artifacts(repo)
    goal = " ".join(args.goal.split())
    metric_name = " ".join(args.metric_name.split())
    verify = args.verify.strip()
    metric_key = None if args.metric_key is None else args.metric_key.strip()
    guard = None if args.guard is None else args.guard.strip()
    codex_bin: str | None = None
    model: str | None = None
    if not goal:
        raise AutoresearchError("--goal cannot be empty")
    if not metric_name:
        raise AutoresearchError("--metric-name cannot be empty")
    if not verify:
        raise AutoresearchError("--verify cannot be empty")
    if args.metric_key is not None and not metric_key:
        raise AutoresearchError("--metric-key cannot be empty")
    if args.guard is not None and not guard:
        raise AutoresearchError("--guard cannot be empty")
    if args.mode == "background":
        codex_bin = args.codex_bin.strip()
        model = None if args.model is None else args.model.strip()
        if not codex_bin:
            raise AutoresearchError("--codex-bin cannot be empty")
        if args.model is not None and not model:
            raise AutoresearchError("--model cannot be empty")
        resolved_codex = shutil.which(codex_bin)
        if resolved_codex is None:
            raise AutoresearchError(f"Background Codex executable was not found: {codex_bin}")
        codex_bin = str(Path(resolved_codex).resolve())
    if args.max_iterations is not None and args.max_iterations <= 0:
        raise AutoresearchError("--max-iterations must be a positive integer")
    if args.timeout_seconds <= 0:
        raise AutoresearchError("--timeout-seconds must be a positive integer")
    target = parse_decimal(args.target, field="--target")
    target_json = decimal_json(target)
    scopes = normalize_scopes(repo, args.scope)
    branch = git_branch(repo)
    head = git_head(repo)
    ensure_new_results_root(repo)
    paths = paths_for(repo)

    try:
        verify_result = run_command(
            command=verify,
            cwd=repo,
            timeout_seconds=args.timeout_seconds,
            log_path=next_command_log(paths, 0, "baseline-verify"),
        )
        require_no_initialized_state(
            paths,
            command_name="Baseline metric command",
            log_path=verify_result.log_path,
        )
        require_command_preserved_repository(
            repo,
            expected_head=head,
            expected_branch=branch,
            command_name="Baseline metric command",
            log_path=verify_result.log_path,
        )
        baseline = parse_metric_output(verify_result, json_key=metric_key)
        guard_log = None
        if guard:
            guard_result = run_command(
                command=guard,
                cwd=repo,
                timeout_seconds=args.timeout_seconds,
                log_path=next_command_log(paths, 0, "baseline-guard"),
            )
            guard_log = guard_result.log_path
            require_no_initialized_state(
                paths,
                command_name="Baseline guard command",
                log_path=guard_result.log_path,
            )
            require_command_preserved_repository(
                repo,
                expected_head=head,
                expected_branch=branch,
                command_name="Baseline guard command",
                log_path=guard_result.log_path,
            )
            if guard_result.returncode != 0:
                raise AutoresearchError(
                    f"Baseline guard exited {guard_result.returncode}: {guard}. "
                    f"Full output: {guard_result.log_path}"
                )
        run_id = uuid.uuid4().hex
        run = {
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "created_at": utc_now(),
            "repo": str(repo),
            "branch": branch,
            "mode": args.mode,
            "goal": goal,
            "scope": scopes,
            "metric": {
                "name": metric_name,
                "direction": args.direction,
                "command": verify,
                "json_key": metric_key,
            },
            "guard": guard,
            "target": target_json,
            "max_iterations": args.max_iterations,
            "timeout_seconds": args.timeout_seconds,
            "background": (
                {
                    "execution_policy": args.execution_policy,
                    "codex_bin": codex_bin,
                    "model": model,
                }
                if args.mode == "background"
                else None
            ),
        }
        validate_run(run, source="new run")
        write_json_atomic(paths.run, run)
        events: list[dict[str, Any]] = []
        baseline_event = append_event(
            paths,
            run,
            events,
            event="baseline",
            head=head,
            metric=decimal_json(baseline),
            verify_log=relative_log_path(paths, verify_result.log_path),
            guard_log=relative_log_path(paths, guard_log),
        )
        events.append(baseline_event)
        status = "active"
        if target_reached(baseline, target, args.direction):
            complete_event = append_event(
                paths,
                run,
                events,
                event="complete",
                reason="baseline already satisfies the target",
                head=head,
                metric=decimal_json(baseline),
            )
            events.append(complete_event)
            status = "complete"
        return {
            "run_id": run_id,
            "mode": args.mode,
            "status": status,
            "baseline": decimal_json(baseline),
            "target": target_json,
            "results": str(paths.root),
        }
    except Exception as exc:
        try:
            write_init_error(repo, exc)
        except Exception as log_error:
            raise AutoresearchError(
                f"Initialization failed: {exc}; writing init-error.json also failed: {log_error}"
            ) from exc
        if isinstance(exc, AutoresearchError):
            diagnostic = paths_for(repo).root / "init-error.json"
            raise AutoresearchError(
                f"{exc}. Initialization diagnostics: {diagnostic}. "
                "Archive the failed initialization before retrying."
            ) from exc
        raise


def append_error(
    *,
    paths: Paths,
    run: dict[str, Any],
    events: list[dict[str, Any]],
    state: RunState,
    reason: str,
    head: str | None = None,
    trial_commit: str | None = None,
    revert_commit: str | None = None,
    log: Path | None = None,
) -> None:
    append_event(
        paths,
        run,
        events,
        event="error",
        reason=reason,
        head=head or state.head,
        metric=decimal_json(state.metric),
        trial_commit=trial_commit,
        revert_commit=revert_commit,
        log=relative_log_path(paths, log),
    )


def safely_revert_after_error(
    *,
    repo: Path,
    paths: Paths,
    run: dict[str, Any],
    events: list[dict[str, Any]],
    state: RunState,
    trial_commit: str,
    reason: str,
    log: Path | None,
) -> None:
    current_head = git_head(repo)
    try:
        current_branch = git_branch(repo)
    except AutoresearchError as branch_error:
        current_branch = None
        reason += f"; {branch_error}"
    if current_head != trial_commit or current_branch != run["branch"]:
        append_error(
            paths=paths,
            run=run,
            events=events,
            state=state,
            reason=(
                reason
                + "; automatic rollback was not attempted because Git moved away from "
                + f"trial {trial_commit} on branch {run['branch']} "
                + f"(current HEAD {current_head}, branch {current_branch or 'detached'})"
            ),
            head=trial_commit,
            trial_commit=trial_commit,
            log=log,
        )
        return
    dirty = working_paths(repo)
    if dirty:
        append_error(
            paths=paths,
            run=run,
            events=events,
            state=state,
            reason=reason + "; automatic rollback was not attempted because commands left changes: " + ", ".join(dirty),
            head=trial_commit,
            trial_commit=trial_commit,
            log=log,
        )
        return
    try:
        revert_commit = revert_trial(repo, trial_commit)
    except AutoresearchError as revert_error:
        current_head = git_head(repo)
        append_error(
            paths=paths,
            run=run,
            events=events,
            state=state,
            reason=(
                f"{reason}; rollback failed: {revert_error}; "
                f"current HEAD is {current_head}"
            ),
            head=trial_commit,
            trial_commit=trial_commit,
            log=log,
        )
        return
    append_error(
        paths=paths,
        run=run,
        events=events,
        state=state,
        reason=reason,
        head=revert_commit,
        trial_commit=trial_commit,
        revert_commit=revert_commit,
        log=log,
    )


def finish_iteration(args: argparse.Namespace) -> dict[str, Any]:
    repo = Path(args.repo).expanduser().resolve()
    paths, run, events, state = load_context(repo)
    if state.status != "active":
        raise AutoresearchError(f"Cannot finish an iteration while run status is {state.status}")
    if git_branch(repo) != run["branch"]:
        raise AutoresearchError(
            f"Run is pinned to branch {run['branch']}, current branch is {git_branch(repo)}"
        )
    if git_head(repo) != state.head:
        raise AutoresearchError(
            f"Git HEAD changed outside autoresearch: expected {state.head}, got {git_head(repo)}"
        )
    require_no_staged_artifacts(repo)
    changed = working_paths(repo)
    if not changed:
        raise AutoresearchError("No experiment changes found; make one focused change before finish")
    require_paths_in_scope(changed, run["scope"])

    trial_commit = commit_trial(repo, paths=changed, description=args.description)
    iteration = state.iterations + 1
    verify_log = next_command_log(paths, iteration, "verify")
    guard_log: Path | None = None
    control_snapshot = control_state_snapshot(paths)
    try:
        verify_result = run_command(
            command=run["metric"]["command"],
            cwd=repo,
            timeout_seconds=run["timeout_seconds"],
            log_path=verify_log,
        )
        require_control_state_unchanged(
            paths,
            control_snapshot,
            command_name="Metric command",
            log_path=verify_log,
        )
        require_command_preserved_repository(
            repo,
            expected_head=trial_commit,
            expected_branch=run["branch"],
            command_name="Metric command",
            log_path=verify_log,
        )
        trial_metric = parse_metric_output(
            verify_result,
            json_key=run["metric"]["json_key"],
        )
    except AutoresearchError as exc:
        require_control_state_unchanged(
            paths,
            control_snapshot,
            command_name="Metric command",
            log_path=verify_log,
        )
        safely_revert_after_error(
            repo=repo,
            paths=paths,
            run=run,
            events=events,
            state=state,
            trial_commit=trial_commit,
            reason=str(exc),
            log=verify_log,
        )
        raise

    outcome = "discard"
    guard_status = "not_run"
    retained_metric = state.metric
    revert_commit: str | None = None
    head = trial_commit
    if improved(trial_metric, state.metric, run["metric"]["direction"]):
        if run["guard"]:
            guard_log = next_command_log(paths, iteration, "guard")
            try:
                control_snapshot = control_state_snapshot(paths)
                guard_result = run_command(
                    command=run["guard"],
                    cwd=repo,
                    timeout_seconds=run["timeout_seconds"],
                    log_path=guard_log,
                )
                require_control_state_unchanged(
                    paths,
                    control_snapshot,
                    command_name="Guard command",
                    log_path=guard_log,
                )
                require_command_preserved_repository(
                    repo,
                    expected_head=trial_commit,
                    expected_branch=run["branch"],
                    command_name="Guard command",
                    log_path=guard_log,
                )
            except AutoresearchError as exc:
                require_control_state_unchanged(
                    paths,
                    control_snapshot,
                    command_name="Guard command",
                    log_path=guard_log,
                )
                safely_revert_after_error(
                    repo=repo,
                    paths=paths,
                    run=run,
                    events=events,
                    state=state,
                    trial_commit=trial_commit,
                    reason=str(exc),
                    log=guard_log,
                )
                raise
            guard_status = "pass" if guard_result.returncode == 0 else "fail"
        else:
            guard_status = "pass"

        if guard_status == "pass":
            outcome = "keep"
            retained_metric = trial_metric

    if outcome == "discard":
        try:
            revert_commit = revert_trial(repo, trial_commit)
        except AutoresearchError as exc:
            current_head = git_head(repo)
            append_error(
                paths=paths,
                run=run,
                events=events,
                state=state,
                reason=(
                    f"Experiment should be discarded but rollback failed: {exc}; "
                    f"current HEAD is {current_head}"
                ),
                head=trial_commit,
                trial_commit=trial_commit,
                log=guard_log or verify_log,
            )
            raise
        head = revert_commit

    event = append_event(
        paths,
        run,
        events,
        event="iteration",
        iteration=iteration,
        outcome=outcome,
        description=" ".join(args.description.split()),
        previous_metric=decimal_json(state.metric),
        trial_metric=decimal_json(trial_metric),
        retained_metric=decimal_json(retained_metric),
        trial_commit=trial_commit,
        head=head,
        revert_commit=revert_commit,
        guard=guard_status,
        verify_log=relative_log_path(paths, verify_log),
        guard_log=relative_log_path(paths, guard_log),
    )
    events.append(event)

    status = "active"
    target = parse_decimal(run["target"], field="run.target")
    if target_reached(retained_metric, target, run["metric"]["direction"]):
        complete = append_event(
            paths,
            run,
            events,
            event="complete",
            reason="retained metric satisfies the target",
            head=head,
            metric=decimal_json(retained_metric),
        )
        events.append(complete)
        status = "complete"
    elif run["max_iterations"] is not None and iteration >= run["max_iterations"]:
        stopped = append_event(
            paths,
            run,
            events,
            event="stopped",
            reason="configured iteration limit reached",
            head=head,
            metric=decimal_json(retained_metric),
        )
        events.append(stopped)
        status = "stopped"

    if run["mode"] == "background":
        instruction = "Iteration recorded. Exit this worker now."
    elif status == "active":
        instruction = "Continue with the next experiment using the recorded evidence."
    else:
        instruction = f"Run is {status}. Stop experimenting and report the result."
    return {
        "status": status,
        "iteration": iteration,
        "outcome": outcome,
        "trial_metric": decimal_json(trial_metric),
        "retained_metric": decimal_json(retained_metric),
        "target": run["target"],
        "head": head,
        "instruction": instruction,
    }


def block_run(args: argparse.Namespace) -> dict[str, Any]:
    repo = Path(args.repo).expanduser().resolve()
    paths, run, events, state = load_context(repo)
    reason = args.reason.strip()
    if not reason:
        raise AutoresearchError("--reason cannot be empty")
    if state.status != "active":
        raise AutoresearchError(f"Cannot block a run whose status is {state.status}")
    require_clean_repo(repo, expected_head=state.head, expected_branch=run["branch"])
    event = append_event(
        paths,
        run,
        events,
        event="blocked",
        reason=reason,
        head=state.head,
        metric=decimal_json(state.metric),
    )
    return {"status": "blocked", "reason": event["reason"]}


def show_status(args: argparse.Namespace) -> dict[str, Any]:
    paths = paths_for(args.repo)
    require_git_repo(paths.repo)
    if not paths.run.is_file():
        if not paths.root.exists():
            return {"status": "not_initialized", "repo": str(paths.repo)}
        current = sorted(
            child.name for child in paths.root.iterdir() if child.name != "archive"
        )
        if not current:
            return {"status": "not_initialized", "repo": str(paths.repo)}
        diagnostic_path = paths.root / "init-error.json"
        allowed = {"init-error.json", "logs"}
        unexpected = sorted(set(current) - allowed)
        if unexpected:
            raise AutoresearchError(
                f"Incomplete autoresearch initialization has unexpected files at {paths.root}: "
                + ", ".join(unexpected)
            )
        if not diagnostic_path.is_file():
            raise AutoresearchError(
                f"Incomplete autoresearch initialization has no run.json or init-error.json at {paths.root}"
            )
        try:
            diagnostic = parse_json(
                diagnostic_path.read_text(encoding="utf-8"),
                source=str(diagnostic_path),
            )
        except OSError as exc:
            raise AutoresearchError(f"Cannot read {diagnostic_path}: {exc}") from exc
        if not isinstance(diagnostic, dict):
            raise AutoresearchError(f"{diagnostic_path} must contain a JSON object")
        require_exact_keys(
            diagnostic,
            required={"time", "error_type", "message", "traceback"},
            source=str(diagnostic_path),
        )
        if any(not isinstance(diagnostic[key], str) for key in diagnostic):
            raise AutoresearchError(f"{diagnostic_path} fields must all be strings")
        return {
            "status": "initialization_failed",
            "repo": str(paths.repo),
            "error_type": diagnostic["error_type"],
            "message": diagnostic["message"],
            "diagnostic": str(diagnostic_path),
            "logs": str(paths.logs),
        }
    paths, run, events, state = load_context(args.repo)
    payload = status_payload(paths, run, events, state)
    current_head = git_head(paths.repo)
    branch_error: str | None = None
    try:
        current_branch = git_branch(paths.repo)
    except AutoresearchError as exc:
        current_branch = None
        branch_error = str(exc)
    dirty = working_paths(paths.repo)
    payload["repository"] = {
        "expected_head": state.head,
        "current_head": current_head,
        "expected_branch": run["branch"],
        "current_branch": current_branch,
        "branch_error": branch_error,
        "dirty_paths": dirty,
        "consistent": (
            current_head == state.head
            and current_branch == run["branch"]
            and not dirty
        ),
    }
    return payload


def show_history(args: argparse.Namespace) -> str:
    _, run, events, state = load_context(Path(args.repo).expanduser().resolve())
    if args.format == "tsv":
        return render_history_tsv(events)
    return render_history_table(run, state, events)


def generate_report(args: argparse.Namespace) -> dict[str, Any]:
    repo = Path(args.repo).expanduser().resolve()
    paths, run, events, state = load_context(repo)
    output = paths.root / "report.html"
    try:
        write_text_atomic(output, render_html_report(run, state, events))
    except OSError as exc:
        raise AutoresearchError(f"Cannot write HTML report {output}: {exc}") from exc
    return {
        "status": state.status,
        "report": str(output),
        "event_count": len(events),
        "iterations": state.iterations,
    }


def runtime_event(paths: Paths, event: str, **fields: Any) -> None:
    append_json_line(
        paths.runtime_log,
        {"time": utc_now(), "source": "controller", "event": event, **fields},
    )


def write_stop_request(paths: Paths, run: dict[str, Any]) -> None:
    write_json_atomic(
        paths.stop_request,
        {"run_id": run["run_id"], "requested_at": utc_now()},
    )


def consume_stop_request(paths: Paths, run: dict[str, Any]) -> bool:
    if not paths.stop_request.exists():
        return False
    try:
        text = paths.stop_request.read_text(encoding="utf-8")
    except OSError as exc:
        raise AutoresearchError(f"Cannot read {paths.stop_request}: {exc}") from exc
    payload = parse_json(text, source=str(paths.stop_request))
    if not isinstance(payload, dict):
        raise AutoresearchError(f"{paths.stop_request} must contain a JSON object")
    require_exact_keys(
        payload,
        required={"run_id", "requested_at"},
        source=str(paths.stop_request),
    )
    if payload["run_id"] != run["run_id"]:
        raise AutoresearchError(
            f"{paths.stop_request}.run_id does not match the active run"
        )
    if not isinstance(payload["requested_at"], str) or not payload["requested_at"]:
        raise AutoresearchError(f"{paths.stop_request}.requested_at must be a non-empty string")
    paths.stop_request.unlink()
    return True


def worker_prompt(repo: Path, script: Path, run: dict[str, Any], state: RunState) -> str:
    python_command = shlex.quote(sys.executable)
    script_command = shlex.quote(str(script))
    repo_argument = shlex.quote(str(repo))
    metric_parser = (
        "final non-empty scalar line"
        if run["metric"]["json_key"] is None
        else f"JSON key {run['metric']['json_key']}"
    )
    guard = run["guard"] or "none"
    limit = "none" if run["max_iterations"] is None else str(run["max_iterations"])
    return f"""You are one background iteration worker for a codex-autoresearch run.
The experiment is already approved. Use the confirmed configuration below.

Repository: {repo}
Control script: {script}
Goal: {run['goal']}
Current metric: {decimal_json(state.metric)}
Target: {run['target']} ({run['metric']['direction']} is better)
Iteration limit: {limit}
Verify command: {run['metric']['command']} ({metric_parser})
Guard command: {guard}
Allowed paths: {', '.join(run['scope'])}

Rules:
1. Run `{python_command} {script_command} status --repo {repo_argument}` and inspect the repository and prior events.
2. Choose one coherent hypothesis from the code and prior results. Keep the evaluation method fixed.
3. Modify only allowed paths. Do not commit, revert, or edit autoresearch-results yourself.
4. Finalize exactly once with `{python_command} {script_command} finish --repo {repo_argument} --description <short-description>`.
5. If and only if no experiment is possible without external input or an environment change, leave the repo clean and run `{python_command} {script_command} block --repo {repo_argument} --reason <precise-reason>`.
6. Do not ask the user questions and do not create or update a Codex Goal. Exit immediately after finish or block.
"""


def controller_command(run: dict[str, Any], repo: Path, last_message: Path) -> list[str]:
    command = [
        run["background"]["codex_bin"],
        "exec",
        "-C",
        str(repo),
        "--ephemeral",
        "--json",
        "--output-last-message",
        str(last_message),
    ]
    if run["background"]["model"]:
        command.extend(["--model", run["background"]["model"]])
    if run["background"]["execution_policy"] == "danger-full-access":
        command.append("--dangerously-bypass-approvals-and-sandbox")
    else:
        command.extend(["--sandbox", "workspace-write"])
    command.append("-")
    return command


def record_controller_error(repo: Path, reason: str, log: Path | None = None) -> None:
    paths, run, events, state = load_context(repo)
    if state.status != "active":
        return
    current_head = git_head(repo)
    if current_head != state.head:
        reason += f"; Git HEAD drifted to {current_head}, retained HEAD is {state.head}"
    append_error(
        paths=paths,
        run=run,
        events=events,
        state=state,
        reason=reason,
        head=state.head,
        log=log,
    )


def run_controller(repo: Path) -> int:
    paths, run, events, state = load_context(repo)
    if run["mode"] != "background":
        raise AutoresearchError("Controller can only run a background autoresearch run")
    if state.status != "active":
        return 0

    started_at = utc_now()
    controller_pid = os.getpid()
    child: subprocess.Popen[str] | None = None
    stopping = False

    def request_stop(_signum: int, _frame: Any) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    startup_deadline = time.monotonic() + 5
    while time.monotonic() < startup_deadline:
        runtime = load_runtime(paths, run_id=run["run_id"])
        if runtime and runtime["controller_pid"] == controller_pid:
            break
        time.sleep(0.02)
    else:
        raise AutoresearchError("Controller startup record was not written by the launcher")
    write_runtime(
        paths,
        run,
        controller_pid=controller_pid,
        child_pid=None,
        state="running",
        started_at=started_at,
    )
    runtime_event(paths, "controller_started", pid=controller_pid)
    script = Path(__file__).resolve()

    while True:
        paths, run, events, state = load_context(repo)
        if state.status != "active":
            write_runtime(
                paths,
                run,
                controller_pid=controller_pid,
                child_pid=None,
                state="stopped",
                started_at=started_at,
            )
            runtime_event(paths, "controller_finished", run_status=state.status)
            return 0
        require_clean_repo(repo, expected_head=state.head, expected_branch=run["branch"])
        require_no_staged_artifacts(repo)
        if consume_stop_request(paths, run):
            stopping = True
        if stopping:
            append_event(
                paths,
                run,
                events,
                event="stopped",
                reason="stopped by user",
                head=state.head,
                metric=decimal_json(state.metric),
            )
            continue

        iteration = state.iterations + 1
        worker_sequence = len(events)
        worker_log = paths.logs / f"worker-{worker_sequence:04d}.jsonl"
        last_message = paths.logs / f"worker-{worker_sequence:04d}-last-message.txt"
        command = controller_command(run, repo, last_message)
        prompt = worker_prompt(repo, script, run, state)
        before_count = len(events)
        runtime_event(
            paths,
            "worker_started",
            worker=iteration,
            sequence=worker_sequence,
            command=command,
            log=str(worker_log),
        )
        with worker_log.open("ab") as output:
            worker_kwargs: dict[str, Any] = {
                "cwd": repo,
                "stdin": subprocess.PIPE,
                "stdout": output,
                "stderr": subprocess.STDOUT,
                "text": True,
                "encoding": "utf-8",
                "errors": "strict",
            }
            if os.name == "nt":
                worker_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                worker_kwargs["start_new_session"] = True
            child = subprocess.Popen(command, **worker_kwargs)
            try:
                write_runtime(
                    paths,
                    run,
                    controller_pid=controller_pid,
                    child_pid=child.pid,
                    state="running",
                    started_at=started_at,
                )
                if child.stdin is None:
                    raise AutoresearchError("Worker stdin pipe was not created")
                child.stdin.write(prompt)
                child.stdin.close()
                while child.poll() is None:
                    if consume_stop_request(paths, run):
                        stopping = True
                    if stopping:
                        runtime_event(paths, "worker_stop_requested", pid=child.pid)
                        terminate_process_tree(child)
                        runtime_event(
                            paths,
                            "worker_terminated",
                            pid=child.pid,
                            returncode=child.returncode,
                        )
                    time.sleep(0.1)
                returncode = child.returncode
                if returncode is None:
                    raise AutoresearchError("Worker exited without a return code")
            except Exception as worker_error:
                cleanup_errors: list[str] = []
                try:
                    terminate_process_tree(child)
                except Exception as cleanup_error:
                    cleanup_errors.append(f"process cleanup failed: {cleanup_error}")
                try:
                    runtime_event(
                        paths,
                        "worker_cleanup_after_controller_error",
                        pid=child.pid,
                        returncode=child.returncode,
                        error_type=type(worker_error).__name__,
                        message=str(worker_error),
                        cleanup_errors=cleanup_errors,
                    )
                except Exception as log_error:
                    cleanup_errors.append(f"cleanup logging failed: {log_error}")
                if cleanup_errors:
                    raise AutoresearchError(
                        f"Worker control failed: {worker_error}; " + "; ".join(cleanup_errors)
                    ) from worker_error
                raise
        child = None
        write_runtime(
            paths,
            run,
            controller_pid=controller_pid,
            child_pid=None,
            state="stopping" if stopping else "running",
            started_at=started_at,
        )
        runtime_event(
            paths,
            "worker_finished",
            worker=iteration,
            sequence=worker_sequence,
            returncode=returncode,
            log=str(worker_log),
        )

        paths, run, after_events, after_state = load_context(repo)
        if stopping:
            if after_state.status == "active":
                require_clean_repo(repo, expected_head=after_state.head, expected_branch=run["branch"])
                append_event(
                    paths,
                    run,
                    after_events,
                    event="stopped",
                    reason="stopped by user",
                    head=after_state.head,
                    metric=decimal_json(after_state.metric),
                )
            continue
        if returncode != 0:
            record_controller_error(
                repo,
                f"codex exec worker {iteration} exited with code {returncode}",
                worker_log,
            )
            continue

        new_events = after_events[before_count:]
        event_types = [event["event"] for event in new_events]
        allowed = ["iteration"]
        if event_types not in (allowed, ["iteration", "complete"], ["iteration", "stopped"], ["blocked"], ["error"]):
            reason = (
                f"worker {iteration} violated the one-iteration contract; "
                f"new events: {event_types}"
            )
            runtime_event(
                paths,
                "worker_contract_violation",
                worker=iteration,
                events=event_types,
                log=str(worker_log),
            )
            if after_state.status != "active":
                raise AutoresearchError(reason)
            record_controller_error(repo, reason, worker_log)


def controller_entry(repo: Path) -> int:
    paths = paths_for(repo)
    try:
        return run_controller(repo)
    except Exception as exc:
        runtime_event(
            paths,
            "controller_error",
            error_type=type(exc).__name__,
            message=str(exc),
            traceback=traceback.format_exc(),
        )
        try:
            record_controller_error(repo, f"controller failed: {exc}", paths.runtime_log)
        except Exception as record_error:
            runtime_event(
                paths,
                "controller_error_record_failed",
                error_type=type(record_error).__name__,
                message=str(record_error),
                traceback=traceback.format_exc(),
            )
        try:
            paths_loaded, run = load_run(repo)
            runtime = load_runtime(paths_loaded, run_id=run["run_id"])
            started_at = utc_now() if runtime is None else runtime["started_at"]
            write_runtime(
                paths_loaded,
                run,
                controller_pid=os.getpid(),
                child_pid=None,
                state="error",
                started_at=started_at,
            )
        except Exception as runtime_error:
            runtime_event(
                paths,
                "runtime_error_record_failed",
                error_type=type(runtime_error).__name__,
                message=str(runtime_error),
                traceback=traceback.format_exc(),
            )
        return 1


def fail_controller_start(
    paths: Paths,
    run: dict[str, Any],
    process: subprocess.Popen[Any],
    started_at: str,
    reason: str,
) -> NoReturn:
    failures: list[str] = []
    if process.poll() is None:
        try:
            terminate_process_tree(process)
        except Exception as exc:
            failures.append(f"controller process cleanup failed: {exc}")
    failure_reason = reason
    if failures:
        failure_reason += "; " + "; ".join(failures)

    try:
        runtime_event(
            paths,
            "controller_start_failed",
            pid=process.pid,
            returncode=process.returncode,
            reason=failure_reason,
            cleanup_failed=bool(failures),
        )
    except Exception as exc:
        failures.append(f"runtime log write failed: {exc}")
    try:
        record_controller_error(paths.repo, failure_reason, paths.runtime_log)
    except Exception as exc:
        failures.append(f"event error record failed: {exc}")
    try:
        write_runtime(
            paths,
            run,
            controller_pid=process.pid,
            child_pid=None,
            state="error",
            started_at=started_at,
        )
    except Exception as exc:
        failures.append(f"runtime state write failed: {exc}")
    if failures:
        failure_reason = reason + "; " + "; ".join(failures)
    raise AutoresearchError(f"{failure_reason}. Inspect {paths.runtime_log}")


def fail_controller_spawn(paths: Paths, reason: str) -> NoReturn:
    failures: list[str] = []
    try:
        runtime_event(paths, "controller_spawn_failed", reason=reason)
    except Exception as exc:
        failures.append(f"runtime log write failed: {exc}")
    try:
        record_controller_error(paths.repo, reason, paths.runtime_log)
    except Exception as exc:
        failures.append(f"event error record failed: {exc}")
    if failures:
        reason += "; " + "; ".join(failures)
    raise AutoresearchError(f"{reason}. Inspect {paths.runtime_log}")


def spawn_controller(repo: Path) -> dict[str, Any]:
    paths, run, _, state = load_context(repo)
    if run["mode"] != "background":
        raise AutoresearchError("Only background runs can start a detached controller")
    if state.status != "active":
        return {"status": state.status, "controller_pid": None}
    if paths.stop_request.exists():
        raise AutoresearchError(
            f"Stale stop request exists at {paths.stop_request}; resolve or archive it before launch"
        )
    runtime = load_runtime(paths, run_id=run["run_id"])
    if runtime is not None and runtime["controller_pid"] and process_alive(runtime["controller_pid"]):
        raise AutoresearchError(f"Background controller is already running as PID {runtime['controller_pid']}")
    if runtime is not None and runtime["child_pid"] and process_alive(runtime["child_pid"]):
        raise AutoresearchError(
            f"Recorded worker PID {runtime['child_pid']} is still alive without a usable controller. "
            f"Inspect {paths.runtime_log} and stop that process before resuming."
        )

    script = Path(__file__).resolve()
    command = [sys.executable, str(script), "_controller", "--repo", str(repo)]
    popen_kwargs: dict[str, Any] = {
        "cwd": repo,
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_kwargs["start_new_session"] = True
    try:
        process = subprocess.Popen(command, **popen_kwargs)
    except OSError as exc:
        fail_controller_spawn(paths, f"Failed to start background controller: {exc}")
    started_at = utc_now()
    try:
        write_runtime(
            paths,
            run,
            controller_pid=process.pid,
            child_pid=None,
            state="starting",
            started_at=started_at,
        )
    except Exception as exc:
        fail_controller_start(
            paths,
            run,
            process,
            started_at,
            f"Failed to write controller startup state: {exc}",
        )
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            _, _, _, current_state = load_context(repo)
        except Exception as exc:
            fail_controller_start(
                paths,
                run,
                process,
                started_at,
                f"Failed to validate controller startup state: {exc}",
            )
        if current_state.status != "active":
            if current_state.status == "error":
                fail_controller_start(
                    paths,
                    run,
                    process,
                    started_at,
                    "Background controller failed during startup",
                )
            return {
                "status": current_state.status,
                "controller_pid": process.pid,
                "results": str(paths.root),
                "runtime_log": str(paths.runtime_log),
            }
        if process.poll() is not None:
            fail_controller_start(
                paths,
                run,
                process,
                started_at,
                f"Background controller exited during startup with code {process.returncode}",
            )
        try:
            runtime = load_runtime(paths, run_id=run["run_id"])
        except Exception as exc:
            fail_controller_start(
                paths,
                run,
                process,
                started_at,
                f"Failed to validate controller runtime state: {exc}",
            )
        if runtime and runtime["controller_pid"] == process.pid and runtime["state"] == "running":
            if process.poll() is not None:
                fail_controller_start(
                    paths,
                    run,
                    process,
                    started_at,
                    f"Background controller exited during startup with code {process.returncode}",
                )
            return {
                "status": "running",
                "controller_pid": process.pid,
                "results": str(paths.root),
                "runtime_log": str(paths.runtime_log),
            }
        time.sleep(0.05)
    fail_controller_start(
        paths,
        run,
        process,
        started_at,
        "Background controller did not become ready within 5 seconds",
    )


def launch_background(args: argparse.Namespace) -> dict[str, Any]:
    initialized = initialize_run(args)
    if initialized["status"] == "complete":
        return initialized
    started = spawn_controller(Path(args.repo).expanduser().resolve())
    return {**initialized, **started}


def stop_background(args: argparse.Namespace) -> dict[str, Any]:
    repo = Path(args.repo).expanduser().resolve()
    paths, run, events, state = load_context(repo)
    if run["mode"] != "background":
        raise AutoresearchError("Foreground runs are paused or cleared with Codex Goal controls")
    if state.status != "active":
        return {"status": state.status, "message": "Run is not active"}
    runtime = load_runtime(paths, run_id=run["run_id"])
    controller_pid = None if runtime is None else runtime["controller_pid"]
    child_pid = None if runtime is None else runtime["child_pid"]
    if controller_pid is None or not process_alive(controller_pid):
        if child_pid is not None and process_alive(child_pid):
            raise AutoresearchError(
                f"Controller is gone but worker PID {child_pid} is still alive. "
                f"Inspect {paths.runtime_log} and terminate that worker before stopping the run."
            )
        require_clean_repo(repo, expected_head=state.head, expected_branch=run["branch"])
        if paths.stop_request.exists():
            consume_stop_request(paths, run)
        append_event(
            paths,
            run,
            events,
            event="stopped",
            reason="stopped by user after detecting an orphaned controller",
            head=state.head,
            metric=decimal_json(state.metric),
        )
        return {"status": "stopped", "controller_pid": None}

    pid = controller_pid
    write_stop_request(paths, run)
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if not process_alive(pid):
            _, _, _, final_state = load_context(repo)
            if final_state.status == "active":
                raise AutoresearchError(
                    f"Controller {pid} exited without recording a terminal event. "
                    f"Inspect {paths.runtime_log}"
                )
            return {"status": final_state.status, "controller_pid": pid}
        time.sleep(0.1)
    raise AutoresearchError(f"Controller {pid} did not stop within 15 seconds")


def resume_run(args: argparse.Namespace) -> dict[str, Any]:
    repo = Path(args.repo).expanduser().resolve()
    paths, run, events, state = load_context(repo)
    note = args.note.strip()
    if not note:
        raise AutoresearchError("--note cannot be empty")
    if state.status == "complete":
        raise AutoresearchError("A completed run cannot be resumed; archive it and start a new goal")
    if run["max_iterations"] is not None and state.iterations >= run["max_iterations"]:
        raise AutoresearchError(
            "The configured iteration limit has been reached; archive this run and confirm a new limit"
        )
    if (
        state.status == "error"
        and state.last_event.get("trial_commit") is not None
        and state.last_event.get("revert_commit") is None
    ):
        raise AutoresearchError(
            "The failed trial commit was not rolled back. Inspect the recorded command log and Git state, "
            "then archive this run after manual recovery; it cannot be resumed from an unverified commit."
        )
    if state.status == "active":
        if run["mode"] == "background":
            runtime = load_runtime(paths, run_id=run["run_id"])
            if runtime:
                if process_alive(runtime["controller_pid"] or 0):
                    raise AutoresearchError("Background run is already active")
                if process_alive(runtime["child_pid"] or 0):
                    raise AutoresearchError(
                        f"Cannot resume while orphaned worker PID {runtime['child_pid']} is alive"
                    )
            raise AutoresearchError(
                "Background event state is still active but its controller is gone. "
                "Run stop to close the orphaned state before resume."
            )
        else:
            raise AutoresearchError("Foreground run is already active")
    require_clean_repo(repo, expected_head=state.head, expected_branch=run["branch"])
    if paths.stop_request.exists():
        consume_stop_request(paths, run)
    event = append_event(
        paths,
        run,
        events,
        event="resumed",
        note=note,
        head=state.head,
        metric=decimal_json(state.metric),
    )
    if run["mode"] == "background":
        return {"note": event["note"], **spawn_controller(repo)}
    return {
        "status": "active",
        "mode": "foreground",
        "note": event["note"],
        "instruction": "Reuse or create the matching Codex Goal, then continue the experiment loop.",
    }


def archive_run(args: argparse.Namespace) -> dict[str, Any]:
    repo = Path(args.repo).expanduser().resolve()
    paths = paths_for(repo)
    if not paths.root.exists():
        raise AutoresearchError(f"No autoresearch results directory at {paths.root}")
    if paths.runtime.exists():
        runtime = load_runtime(paths)
        if runtime and runtime["controller_pid"] and process_alive(runtime["controller_pid"]):
            raise AutoresearchError("Stop the background controller before archiving")
        if runtime and runtime["child_pid"] and process_alive(runtime["child_pid"]):
            raise AutoresearchError(
                f"Cannot archive while recorded worker PID {runtime['child_pid']} is still alive"
            )
    archive_root = paths.root / "archive"
    archive_root.mkdir(parents=True, exist_ok=True)
    archive_id = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    destination = archive_root / archive_id
    if destination.exists():
        raise AutoresearchError(f"Archive destination already exists: {destination}")
    destination.mkdir()
    moved: list[str] = []
    for child in sorted(paths.root.iterdir(), key=lambda item: item.name):
        if child == archive_root:
            continue
        shutil.move(str(child), destination / child.name)
        moved.append(child.name)
    if not moved:
        destination.rmdir()
        raise AutoresearchError(f"No current run files to archive in {paths.root}")
    return {"status": "archived", "destination": str(destination), "moved": moved}


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "init":
        output = initialize_run(args)
    elif args.command == "launch":
        output = launch_background(args)
    elif args.command == "finish":
        output = finish_iteration(args)
    elif args.command == "block":
        output = block_run(args)
    elif args.command == "status":
        output = show_status(args)
    elif args.command == "history":
        print(show_history(args), end="")
        return 0
    elif args.command == "report":
        output = generate_report(args)
    elif args.command == "stop":
        output = stop_background(args)
    elif args.command == "resume":
        output = resume_run(args)
    elif args.command == "archive":
        output = archive_run(args)
    elif args.command == "_controller":
        return controller_entry(Path(args.repo).expanduser().resolve())
    else:
        raise AutoresearchError(f"Unsupported command: {args.command}")
    print_json(output)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutoresearchError as exc:
        raise SystemExit(f"error: {exc}")
