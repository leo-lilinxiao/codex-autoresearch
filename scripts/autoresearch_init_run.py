#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from autoresearch_helpers import (
    AutoresearchError,
    archive_path_to_prev,
    build_repo_targets,
    repo_commit_map_for_targets,
    build_state_payload,
    cleanup_exec_state,
    default_state_path,
    decimal_to_json_number,
    find_repo_root,
    format_decimal,
    make_row,
    parse_decimal,
    resolve_state_path,
    serialize_repo_targets,
    write_json_atomic,
    write_results_log,
)
from autoresearch_core import SESSION_MODE_CHOICES
from autoresearch_preflight import evaluate_managed_repos_preflight
from autoresearch_runtime_common import DEFAULT_EXECUTION_POLICY, EXECUTION_POLICY_CHOICES


class HardBlockerError(AutoresearchError):
    pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Initialize research-results.tsv and autoresearch-state.json from the baseline measurement."
    )
    parser.add_argument("--results-path", default="research-results.tsv")
    parser.add_argument(
        "--state-path",
        help="State JSON path. Defaults to autoresearch-state.json, except exec mode uses scratch state under /tmp.",
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
    parser.add_argument("--parallel-mode", choices=["serial", "parallel"], default="serial")
    parser.add_argument("--web-search", choices=["enabled", "disabled"], default="disabled")
    parser.add_argument("--environment-summary")
    parser.add_argument("--baseline-metric", required=True)
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


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    results_path = Path(args.results_path)
    repo_hint = results_path.parent if results_path.is_absolute() else None
    repo_context = repo_hint or Path.cwd()
    repo = find_repo_root(repo_context)
    state_path = resolve_state_path(args.state_path, mode=args.mode, cwd=repo_context)
    repo_targets = build_repo_targets(
        primary_repo=repo,
        primary_scope=args.scope,
        companion_repo_scopes=args.companion_repo_scope,
    )

    if args.mode == "exec":
        preflight = evaluate_managed_repos_preflight(
            primary_repo=repo,
            results_path=results_path,
            state_path_arg=args.state_path,
            verify_command=args.verify,
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

    # Exec mode is documented to start fresh. If the default scratch state was
    # left behind by a previous crashed run, clear it before checking for
    # existing artifacts so the next unattended run can start cleanly.
    if args.mode == "exec" and args.state_path is None and not args.force:
        if state_path.exists():
            cleanup_exec_state(repo)
        archive_path_to_prev(results_path)
        archive_path_to_prev(default_state_path(repo))

    if not args.force:
        for path in (results_path, state_path):
            if path.exists():
                raise AutoresearchError(f"{path} already exists. Use --force after moving old artifacts.")

    baseline_metric = parse_decimal(args.baseline_metric, "baseline metric")
    comments = [f"# metric_direction: {args.direction}"]
    if args.environment_summary:
        comments.insert(0, f"# environment: {args.environment_summary}")
    comments.append(f"# mode: {args.mode}")
    if args.run_tag:
        comments.append(f"# run_tag: {args.run_tag}")
    comments.append(f"# parallel: {args.parallel_mode}")
    comments.append(f"# web_search: {args.web_search}")

    baseline_row = make_row(
        iteration="0",
        commit=args.baseline_commit,
        metric=baseline_metric,
        delta=parse_decimal("0", "delta"),
        guard="-",
        status="baseline",
        description=args.baseline_description,
    )
    write_results_log(results_path, comments, [baseline_row])

    session_mode = args.session_mode
    if args.mode != "exec" and session_mode is None:
        session_mode = "foreground"

    config = {
        "goal": args.goal,
        "scope": repo_targets[0].scope,
        "repos": serialize_repo_targets(repo_targets),
        "metric": args.metric_name,
        "direction": args.direction,
        "verify": args.verify,
        "guard": args.guard,
        "iterations": args.iterations,
        "stop_condition": args.stop_condition,
        "rollback_policy": args.rollback_policy,
        "parallel_mode": args.parallel_mode,
        "web_search": args.web_search,
    }
    if session_mode is not None:
        config["session_mode"] = session_mode
    if args.mode == "exec" or session_mode == "background":
        config["execution_policy"] = args.execution_policy
    summary = {
        "iteration": 0,
        "baseline_metric": baseline_metric,
        "best_metric": baseline_metric,
        "best_iteration": 0,
        "current_metric": baseline_metric,
        "last_commit": args.baseline_commit,
        "last_trial_commit": args.baseline_commit,
        "last_trial_metric": baseline_metric,
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

    print(
        json.dumps(
            {
                "results_path": str(results_path),
                "state_path": str(state_path),
                "baseline_metric": decimal_to_json_number(baseline_metric),
                "baseline_commit": args.baseline_commit,
                "parallel_mode": args.parallel_mode,
                "session_mode": session_mode,
                "message": f"Initialized run at baseline metric {format_decimal(baseline_metric)}.",
            },
            indent=2,
            sort_keys=True,
        )
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
