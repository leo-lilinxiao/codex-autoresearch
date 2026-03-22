#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from autoresearch_core import SESSION_MODE_CHOICES
from autoresearch_helpers import (
    AutoresearchError,
    default_runtime_state_path,
    parse_results_log,
    results_repo_root,
    resolve_state_path_for_log,
    sync_state_session_mode,
)
from autoresearch_launch_gate import pid_is_alive
from autoresearch_runtime_common import (
    DEFAULT_EXECUTION_POLICY,
    EXECUTION_POLICY_CHOICES,
    load_runtime_with_error,
    resolve_repo_relative,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Synchronize autoresearch-state.json with the active interactive session mode."
    )
    parser.add_argument("--results-path", default="research-results.tsv")
    parser.add_argument("--state-path")
    parser.add_argument(
        "--runtime-path",
        help=(
            "Runtime control JSON path. Defaults to autoresearch-runtime.json in the "
            "primary repo rooted at --results-path."
        ),
    )
    parser.add_argument("--session-mode", required=True, choices=SESSION_MODE_CHOICES)
    parser.add_argument(
        "--execution-policy",
        choices=EXECUTION_POLICY_CHOICES,
        default=DEFAULT_EXECUTION_POLICY,
        help="Execution policy to persist when switching into background mode.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    results_path = Path(args.results_path)
    repo = results_repo_root(results_path)
    repo_hint = results_path.parent if results_path.is_absolute() else repo
    parsed = parse_results_log(results_path) if results_path.exists() else None
    state_path = resolve_state_path_for_log(args.state_path, parsed, cwd=repo_hint)
    runtime_path = resolve_repo_relative(
        repo,
        args.runtime_path,
        default_runtime_state_path(repo),
    )
    runtime, runtime_error = load_runtime_with_error(runtime_path)
    if runtime_error is not None:
        raise AutoresearchError(runtime_error)
    if runtime is not None and pid_is_alive(runtime.get("pid")):
        raise AutoresearchError(
            "Cannot switch interactive session mode while a background runtime is still active. "
            "Stop the detached runtime first."
        )

    updated = sync_state_session_mode(
        state_path,
        session_mode=args.session_mode,
        execution_policy=args.execution_policy if args.session_mode == "background" else None,
    )

    print(
        json.dumps(
            {
                "results_path": str(results_path),
                "state_path": str(state_path),
                "runtime_path": str(runtime_path),
                "session_mode": updated.get("session_mode", ""),
                "execution_policy": updated.get("config", {}).get("execution_policy", ""),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutoresearchError as exc:
        raise SystemExit(f"error: {exc}")
