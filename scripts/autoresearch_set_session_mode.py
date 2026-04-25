#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from autoresearch_core import SESSION_MODE_CHOICES, print_json
from autoresearch_hook_context import update_hook_context_pointer
from autoresearch_helpers import (
    ARTIFACT_DIR_NAME,
    RESULTS_FILE_NAME,
    AutoresearchError,
    default_workspace_artifacts,
    require_context_for_repo,
    resolve_context_workspace_root,
    resolve_repo_path,
    resolve_repo_relative,
    resolve_state_path,
    sync_state_session_mode,
)
from autoresearch_launch_gate import runtime_process_state
from autoresearch_runtime_common import (
    DEFAULT_EXECUTION_POLICY,
    EXECUTION_POLICY_CHOICES,
    load_runtime_with_error,
)
from autoresearch_workspace import resolve_workspace_root


DEFAULT_RESULTS_PATH = f"{ARTIFACT_DIR_NAME}/{RESULTS_FILE_NAME}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Synchronize autoresearch-results/state.json with the active interactive session mode."
    )
    parser.add_argument(
        "--repo",
        help="Primary repo root. Preferred entrypoint when syncing interactive session mode.",
    )
    parser.add_argument("--workspace-root")
    parser.add_argument(
        "--results-path",
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--state-path", help=argparse.SUPPRESS)
    parser.add_argument(
        "--runtime-path",
        help=argparse.SUPPRESS,
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

    if args.repo is None:
        raise AutoresearchError("--repo is required; run context is resolved from explicit repo metadata.")
    repo = resolve_repo_path(args.repo)
    context = require_context_for_repo(repo)
    workspace_root = resolve_context_workspace_root(
        repo=repo,
        context=context,
        raw_workspace_root=args.workspace_root,
    )
    defaults = default_workspace_artifacts(context.workspace_root)
    results_default = context.results_path
    results_path = resolve_repo_relative(workspace_root, args.results_path, results_default)
    runtime_default = (
        context.runtime_path if context.runtime_path is not None else defaults.runtime_path
    )
    if args.state_path is not None:
        state_path = resolve_state_path(args.state_path, cwd=workspace_root)
    else:
        state_path = context.state_path
    runtime_path = resolve_repo_relative(
        workspace_root,
        args.runtime_path,
        runtime_default,
    )
    runtime, runtime_error = load_runtime_with_error(runtime_path)
    if runtime_error is not None:
        raise AutoresearchError(runtime_error)
    if runtime is not None:
        runtime_state = runtime_process_state(runtime)
        if bool(runtime_state["alive"]) and bool(runtime_state["matches"]):
            raise AutoresearchError(
                "Cannot switch interactive session mode while a background runtime is still active. "
                "Stop the detached runtime first."
            )
        if bool(runtime_state["alive"]) and not bool(runtime_state["matches"]):
            raise AutoresearchError(str(runtime_state["message"]))

    updated = sync_state_session_mode(
        state_path,
        session_mode=args.session_mode,
        execution_policy=args.execution_policy if args.session_mode == "background" else None,
    )
    update_hook_context_pointer(
        repo=repo,
        active=True,
        session_mode=args.session_mode,
        results_path=results_path.resolve(),
        state_path=state_path.resolve(),
        runtime_path=runtime_path.resolve(),
    )

    print_json(
        {
            "results_path": str(results_path),
            "state_path": str(state_path),
            "runtime_path": str(runtime_path),
            "session_mode": updated.get("config", {}).get("session_mode", ""),
            "execution_policy": updated.get("config", {}).get("execution_policy", ""),
        }
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutoresearchError as exc:
        raise SystemExit(f"error: {exc}")
