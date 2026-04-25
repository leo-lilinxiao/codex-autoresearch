#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from autoresearch_helpers import (
    AutoresearchError,
    acceptance_state,
    archive_path_to_prev,
    build_repo_targets,
    build_state_payload,
    cleanup_exec_state,
    decimal_to_json_number,
    format_decimal,
    legacy_layout_error,
    make_row,
    normalize_criteria_config,
    normalize_labels,
    parse_decimal,
    parse_metrics_json_output,
    repo_commit_map_for_targets,
    resolve_repo_path,
    resolve_state_path,
    serialize_metrics,
    serialize_repo_targets,
    write_json_atomic,
    write_results_log,
)
from autoresearch_core import SESSION_MODE_CHOICES, json_dumps, print_json
from autoresearch_hook_context import write_hook_context_pointer
from autoresearch_preflight import evaluate_managed_repos_preflight
from autoresearch_runtime_common import (
    DEFAULT_EXECUTION_POLICY,
    DEFAULT_RESULTS_PATH,
    DEFAULT_VERIFY_CWD,
    EXECUTION_POLICY_CHOICES,
    VERIFY_CWD_CHOICES,
    VERIFY_FORMAT_CHOICES,
    parse_optional_json_argument,
    resolve_workspace_root,
)
from autoresearch_workspace import default_workspace_artifacts, require_managed_git_repos


class HardBlockerError(AutoresearchError):
    pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Initialize workspace-owned autoresearch results and state from the baseline measurement."
    )
    parser.add_argument("--repo", required=True)
    parser.add_argument("--workspace-root", required=True)
    parser.add_argument("--results-path", default=DEFAULT_RESULTS_PATH, help=argparse.SUPPRESS)
    parser.add_argument(
        "--state-path",
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--mode", required=True)
    parser.add_argument(
        "--session-mode",
        choices=SESSION_MODE_CHOICES,
        help=(
            "Session mode for interactive runs. Defaults to foreground for non-exec runs. "
            "Exec remains a separate headless path."
        ),
    )
    parser.add_argument("--goal", required=True)
    parser.add_argument("--scope", required=True)
    parser.add_argument(
        "--companion-repo-scope",
        action="append",
        default=[],
        help="Allow edits in a companion repo using PATH=SCOPE. May be repeated.",
    )
    parser.add_argument("--metric-name", required=True)
    parser.add_argument("--direction", required=True, choices=["lower", "higher"])
    parser.add_argument("--verify", required=True)
    parser.add_argument("--verify-cwd", choices=VERIFY_CWD_CHOICES, default=DEFAULT_VERIFY_CWD)
    parser.add_argument("--verify-format", choices=VERIFY_FORMAT_CHOICES, default="scalar")
    parser.add_argument("--primary-metric-key")
    parser.add_argument("--acceptance-criteria")
    parser.add_argument("--required-keep-criteria")
    parser.add_argument("--guard")
    parser.add_argument(
        "--execution-policy",
        choices=EXECUTION_POLICY_CHOICES,
        default=DEFAULT_EXECUTION_POLICY,
        help="Execution policy used for this run's Codex sessions.",
    )
    parser.add_argument("--iterations", type=int)
    parser.add_argument("--run-tag")
    parser.add_argument("--stop-condition")
    parser.add_argument("--rollback-policy")
    parser.add_argument(
        "--required-stop-label",
        action="append",
        default=[],
        help=(
            "Require retained keep labels before stop_condition can mechanically stop the run. "
            "May be repeated."
        ),
    )
    parser.add_argument(
        "--required-keep-label",
        action="append",
        default=[],
        help=(
            "Require iteration labels before a numerically improved result can be retained as keep. "
            "May be repeated."
        ),
    )
    parser.add_argument("--parallel-mode", choices=["serial", "parallel"], default="serial")
    parser.add_argument("--web-search", choices=["enabled", "disabled"], default="disabled")
    parser.add_argument("--environment-summary")
    parser.add_argument("--baseline-metric", required=True)
    parser.add_argument(
        "--baseline-metrics-json",
        help=(
            "Verify output text whose final non-empty line is the structured baseline "
            "metrics JSON object. Required when --verify-format=metrics_json."
        ),
    )
    parser.add_argument("--baseline-commit", required=True)
    parser.add_argument("--baseline-description", required=True)
    parser.add_argument(
        "--repo-commit",
        action="append",
        default=[],
        help="Record per-repo commit provenance using PATH=COMMIT. May be repeated.",
    )
    parser.add_argument("--force", action="store_true")
    return parser


def resolve_results_path(workspace_root: Path, default_results_path: Path, raw: str) -> Path:
    requested = Path(raw)
    if requested == Path(DEFAULT_RESULTS_PATH):
        return default_results_path
    if requested.is_absolute():
        return requested
    return (workspace_root / requested).resolve()


def resolve_explicit_path(workspace_root: Path, raw: str | None) -> Path | None:
    if raw is None:
        return None
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = workspace_root / candidate
    return candidate.resolve()


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    repo = resolve_repo_path(args.repo)
    workspace_root = resolve_workspace_root(repo, args.workspace_root)
    artifact_defaults = default_workspace_artifacts(workspace_root)
    results_path = resolve_results_path(workspace_root, artifact_defaults.results_path, args.results_path)
    explicit_state_path = resolve_explicit_path(workspace_root, args.state_path)
    state_path = explicit_state_path or (
        resolve_state_path(None, mode="exec", cwd=workspace_root)
        if args.mode == "exec"
        else artifact_defaults.state_path
    )

    repo_targets = build_repo_targets(
        primary_repo=repo,
        primary_scope=args.scope,
        companion_repo_scopes=args.companion_repo_scope,
    )
    require_managed_git_repos(repo, repo_targets)

    legacy_error = legacy_layout_error(repo)
    if legacy_error is not None and not args.force:
        raise AutoresearchError(legacy_error)

    if args.mode == "exec":
        preflight = evaluate_managed_repos_preflight(
            primary_repo=repo,
            workspace_root=workspace_root,
            results_path=results_path,
            state_path_arg=str(state_path) if explicit_state_path is not None else args.state_path,
            verify_command=args.verify,
            verify_cwd=args.verify_cwd,
            commit_phase="prelaunch",
            include_health=False,
            rollback_policy=None,
            destructive_approved=False,
            repo_targets=repo_targets,
        )
        if preflight["decision"] == "block":
            raise HardBlockerError(
                "Exec prelaunch failed: " + "; ".join(preflight["blockers"])
            )

    if args.mode == "exec" and args.state_path is None and not args.force:
        if state_path.exists():
            cleanup_exec_state(workspace_root)
        archive_path_to_prev(results_path)
        archive_path_to_prev(artifact_defaults.state_path)

    if not args.force:
        for path in (results_path, state_path):
            if path.exists():
                raise AutoresearchError(f"{path} already exists. Use --force after moving old artifacts.")

    session_mode = args.session_mode
    if args.mode != "exec" and session_mode is None:
        session_mode = "foreground"

    acceptance_criteria = normalize_criteria_config(
        parse_optional_json_argument(
            args.acceptance_criteria,
            field_name="acceptance_criteria",
        ),
        field_name="acceptance_criteria",
    )
    required_keep_criteria = normalize_criteria_config(
        parse_optional_json_argument(
            args.required_keep_criteria,
            field_name="required_keep_criteria",
        ),
        field_name="required_keep_criteria",
    )
    baseline_metrics = parse_metrics_json_output(
        args.baseline_metrics_json,
        field_name="baseline_metrics_json",
    )
    if args.verify_format == "metrics_json" and baseline_metrics is None:
        raise AutoresearchError("--baseline-metrics-json is required when --verify-format=metrics_json.")

    required_stop_labels = normalize_labels(args.required_stop_label)
    required_keep_labels = normalize_labels(args.required_keep_label)

    config = {
        "workspace_root": str(workspace_root),
        "artifact_root": str(artifact_defaults.artifact_root),
        "primary_repo": str(repo.resolve()),
        "goal": args.goal,
        "scope": repo_targets[0].scope,
        "repos": serialize_repo_targets(repo_targets),
        "metric": args.metric_name,
        "direction": args.direction,
        "verify": args.verify,
        "verify_cwd": args.verify_cwd,
        "verify_format": args.verify_format,
        "primary_metric_key": args.primary_metric_key or args.metric_name,
        "guard": args.guard,
        "iterations": args.iterations,
        "stop_condition": args.stop_condition,
        "rollback_policy": args.rollback_policy,
        "parallel_mode": args.parallel_mode,
        "web_search": args.web_search,
    }
    if acceptance_criteria:
        config["acceptance_criteria"] = acceptance_criteria
    if required_keep_criteria:
        config["required_keep_criteria"] = required_keep_criteria
    if session_mode is not None:
        config["session_mode"] = session_mode
    if args.mode == "exec" or session_mode == "background":
        config["execution_policy"] = args.execution_policy
    if required_stop_labels:
        config["required_stop_labels"] = required_stop_labels
    if required_keep_labels:
        config["required_keep_labels"] = required_keep_labels

    baseline_metric = parse_decimal(args.baseline_metric, "baseline metric")
    baseline_acceptance = acceptance_state(config=config, metric=baseline_metric, metrics=baseline_metrics)

    comments = [f"# metric_direction: {args.direction}"]
    if args.environment_summary:
        comments.insert(0, f"# environment: {args.environment_summary}")
    comments.extend(
        [
            f"# mode: {args.mode}",
            f"# parallel: {args.parallel_mode}",
            f"# web_search: {args.web_search}",
            f"# workspace_root: {workspace_root}",
            f"# artifact_root: {artifact_defaults.artifact_root}",
            f"# primary_repo: {repo.resolve()}",
            f"# goal: {args.goal}",
            f"# scope: {repo_targets[0].scope}",
            "# repos_json: "
            + json_dumps(serialize_repo_targets(repo_targets), sort_keys=True, separators=(",", ":")),
            f"# metric: {args.metric_name}",
            f"# verify: {args.verify}",
            f"# verify_cwd: {args.verify_cwd}",
            f"# verify_format: {args.verify_format}",
            f"# primary_metric_key: {config['primary_metric_key']}",
        ]
    )
    if args.run_tag:
        comments.append(f"# run_tag: {args.run_tag}")
    if args.guard:
        comments.append(f"# guard: {args.guard}")
    if args.iterations is not None:
        comments.append(f"# iterations: {args.iterations}")
    if args.stop_condition:
        comments.append(f"# stop_condition: {args.stop_condition}")
    if args.rollback_policy:
        comments.append(f"# rollback_policy: {args.rollback_policy}")
    if args.mode == "exec" or session_mode == "background":
        comments.append(f"# execution_policy: {args.execution_policy}")
    if required_stop_labels:
        comments.append(f"# required_stop_labels: {', '.join(required_stop_labels)}")
    if required_keep_labels:
        comments.append(f"# required_keep_labels: {', '.join(required_keep_labels)}")
    if acceptance_criteria:
        comments.append(
            "# acceptance_criteria_json: "
            + json_dumps(acceptance_criteria, sort_keys=True, separators=(",", ":"))
        )
    if required_keep_criteria:
        comments.append(
            "# required_keep_criteria_json: "
            + json_dumps(required_keep_criteria, sort_keys=True, separators=(",", ":"))
        )

    baseline_row = make_row(
        iteration="0",
        commit=args.baseline_commit,
        metric=baseline_metric,
        delta=parse_decimal("0", "delta"),
        guard="-",
        status="baseline",
        description=args.baseline_description,
        labels=[],
    )
    write_results_log(results_path, comments, [baseline_row])

    summary = {
        "iteration": 0,
        "baseline_metric": baseline_metric,
        "best_metric": baseline_metric,
        "best_iteration": 0,
        "current_metric": baseline_metric,
        "last_commit": args.baseline_commit,
        "last_trial_commit": args.baseline_commit,
        "last_trial_metric": baseline_metric,
        "current_metrics": serialize_metrics(baseline_acceptance["metrics"]),
        "last_trial_metrics": serialize_metrics(baseline_acceptance["metrics"]),
        "current_acceptance": baseline_acceptance["acceptance_satisfied"],
        "last_trial_acceptance": baseline_acceptance["acceptance_satisfied"],
        "current_required_keep_satisfied": baseline_acceptance["required_keep_satisfied"],
        "last_trial_required_keep_satisfied": baseline_acceptance["required_keep_satisfied"],
        "current_labels": [],
        "last_trial_labels": [],
        "keeps": 0,
        "discards": 0,
        "crashes": 0,
        "no_ops": 0,
        "blocked": 0,
        "consecutive_discards": 0,
        "pivot_count": 0,
        "last_status": "baseline",
    }
    repo_commit_map = repo_commit_map_for_targets(
        repo_targets=repo_targets,
        primary_commit=args.baseline_commit,
        repo_commit_specs=args.repo_commit,
    )
    if repo_commit_map:
        summary["last_repo_commits"] = dict(repo_commit_map)
        summary["last_trial_repo_commits"] = dict(repo_commit_map)

    payload = build_state_payload(
        mode=args.mode,
        run_tag=args.run_tag,
        config=config,
        summary=summary,
    )
    write_json_atomic(state_path, payload)

    write_hook_context_pointer(
        repo=repo,
        active=args.mode != "exec",
        session_mode=session_mode,
        results_path=results_path.resolve(),
        state_path=state_path.resolve(),
        launch_path=None,
        runtime_path=None,
        workspace_root=workspace_root,
        primary_repo=repo,
        repo_targets=repo_targets,
        verify_cwd=args.verify_cwd,
    )

    print_json(
        {
            "workspace_root": str(workspace_root),
            "artifact_root": str(artifact_defaults.artifact_root),
            "primary_repo": str(repo.resolve()),
            "results_path": str(results_path),
            "state_path": str(state_path),
            "baseline_metric": decimal_to_json_number(baseline_metric),
            "baseline_commit": args.baseline_commit,
            "parallel_mode": args.parallel_mode,
            "session_mode": session_mode,
            "message": f"Initialized run at baseline metric {format_decimal(baseline_metric)}.",
        }
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except HardBlockerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
    except AutoresearchError as exc:
        raise SystemExit(f"error: {exc}")
