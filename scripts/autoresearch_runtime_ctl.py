#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from autoresearch_helpers import (
    AutoresearchError,
    default_launch_manifest_path,
    default_runtime_state_path,
)
from autoresearch_runtime_common import (
    DEFAULT_HEALTH_MIN_FREE_MB,
    DEFAULT_RESULTS_PATH,
    DEFAULT_EXECUTION_POLICY,
    EXECUTION_POLICY_CHOICES,
    resolve_repo_path,
    resolve_repo_relative,
)
from autoresearch_runtime_ops import (
    create_launch_manifest,
    launch_and_start_runtime,
    run_runtime,
    runtime_summary,
    start_runtime,
    stop_runtime,
)


def add_manifest_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo")
    parser.add_argument("--launch-path")
    parser.add_argument("--original-goal", required=True)
    parser.add_argument("--prompt-text")
    parser.add_argument("--mode", default="loop")
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
        help="How nested Codex sessions should execute. Defaults to danger_full_access.",
    )
    parser.add_argument("--iterations", type=int)
    parser.add_argument("--run-tag")
    parser.add_argument("--stop-condition")
    parser.add_argument(
        "--required-stop-label",
        action="append",
        default=[],
        help=(
            "Require retained keep labels before stop_condition can mechanically stop the run. "
            "May be repeated."
        ),
    )
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
    runner_path = Path(__file__).resolve()

    if args.command == "create-launch":
        print(json.dumps(create_launch_manifest(args), indent=2, sort_keys=True))
        return 0
    if args.command == "launch":
        print(json.dumps(launch_and_start_runtime(args, runner_path=runner_path), indent=2, sort_keys=True))
        return 0
    if args.command == "start":
        print(json.dumps(start_runtime(args, runner_path=runner_path), indent=2, sort_keys=True))
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
