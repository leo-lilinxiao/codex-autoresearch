#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from autoresearch_helpers import (
    AutoresearchError,
    format_repo_target_label,
    LAUNCH_MANIFEST_NAME,
    repo_targets_from_config,
    read_launch_manifest,
    require_context_for_repo,
    resolve_context_workspace_root,
    resolve_repo_path,
    resolve_repo_relative,
    RUNTIME_STATE_NAME,
    STATE_FILE_NAME,
)
from autoresearch_launch_gate import evaluate_launch_context
from autoresearch_workspace import default_workspace_artifacts, resolve_workspace_root


RUNTIME_CHECKLIST = (
    "Baseline first, then initialize fresh artifacts if they do not exist yet.",
    "Record every completed experiment before starting the next one.",
    "Use helper scripts for authoritative TSV/state updates.",
    "Let helper logic own keep/stop gating and retained-state semantics.",
)
OPTIONAL_CONFIG_FIELDS = (
    ("verify_cwd", "Verify cwd"),
    ("verify_format", "Verify format"),
    ("primary_metric_key", "Primary metric key"),
    ("execution_policy", "Execution policy"),
    ("guard", "Guard"),
    ("iterations", "Iterations"),
    ("stop_condition", "Stop condition"),
    ("acceptance_criteria", "Acceptance criteria"),
    ("required_keep_criteria", "Required keep criteria"),
    ("required_keep_labels", "Required keep labels"),
    ("required_stop_labels", "Required stop labels"),
    ("rollback_policy", "Rollback policy"),
    ("parallel_mode", "Parallel mode"),
    ("web_search", "Web search"),
)


def build_runtime_prompt(
    *,
    launch_manifest: dict,
    launch_context: dict,
    launch_path: Path,
    results_path: Path,
    state_path: Path,
) -> str:
    decision = launch_context["decision"]
    strategy = launch_context["resume_strategy"]
    config = launch_manifest["config"]
    primary_repo_config = config.get("primary_repo")
    if not isinstance(primary_repo_config, str) or not primary_repo_config.strip():
        raise AutoresearchError("Launch config.primary_repo is required.")
    primary_repo = Path(primary_repo_config).expanduser().resolve()
    repo_targets = repo_targets_from_config(primary_repo, config)
    lines = [
        "$codex-autoresearch",
        "This repo is managed by the autoresearch runtime controller.",
        "The human already completed the confirmation phase for this run.",
        f"Use {launch_path} as the authoritative launch manifest.",
        f"Runtime launch decision: {decision} ({strategy}).",
        "",
        f"Original ask: {launch_manifest['original_goal']}",
        f"Session mode: {config.get('session_mode', 'background')}",
        f"Mode: {launch_manifest.get('mode', 'loop')}",
        f"Goal: {config.get('goal', '')}",
        f"Scope: {repo_targets[0].scope}",
        f"Metric: {config.get('metric', '')}",
        f"Direction: {config.get('direction', '')}",
        f"Verify: {config.get('verify', '')}",
    ]
    if len(repo_targets) > 1:
        lines.append("Managed repos:")
        for target in repo_targets:
            lines.append(
                f"- {format_repo_target_label(target, primary_repo)} ({target.role}) :: {target.scope}"
            )
    for field_name, label in OPTIONAL_CONFIG_FIELDS:
        value = config.get(field_name)
        if value not in (None, "", []):
            lines.append(f"{label}: {value}")

    lines.extend(
        [
            "",
            f"Results path: {results_path}",
            f"State path: {state_path}",
            "",
            "Runtime checklist:",
            *[f"- {item}" for item in RUNTIME_CHECKLIST],
            "",
            "Instructions:",
            "- Do not run the interactive wizard again.",
            "- Do not ask the user for launch confirmation again.",
            "- If results/state artifacts exist, resume from them.",
            "- If they do not exist yet, initialize a fresh run from the launch manifest.",
            "- When initializing fresh artifacts for this managed run, call autoresearch_init_run.py with --repo <primary_repo>, --workspace-root <workspace_root>, and --session-mode background.",
            "- Continue autonomously until a terminal condition or blocker is reached.",
            "- Keep all run-control decisions aligned with the launch manifest and current state.",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate the runtime-managed resume prompt from the launch manifest and current state."
    )
    parser.add_argument(
        "--repo",
        required=True,
        help="Primary repo root. Run context is resolved from this repo's git-local pointer.",
    )
    parser.add_argument("--workspace-root")
    parser.add_argument(
        "--results-path",
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--state-path", help=argparse.SUPPRESS)
    parser.add_argument("--launch-path", help=argparse.SUPPRESS)
    parser.add_argument("--runtime-path", help=argparse.SUPPRESS)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    repo = resolve_repo_path(args.repo)
    if args.results_path is not None:
        workspace_root = (
            resolve_workspace_root(repo, args.workspace_root)
            if args.workspace_root is not None
            else Path.cwd().resolve()
        )
        results_path = resolve_repo_relative(workspace_root, args.results_path, Path(args.results_path))
        artifact_root = results_path.parent
        state_default = artifact_root / STATE_FILE_NAME
        launch_path = resolve_repo_relative(
            workspace_root,
            args.launch_path,
            artifact_root / LAUNCH_MANIFEST_NAME,
        )
        runtime_path = resolve_repo_relative(
            workspace_root,
            args.runtime_path,
            artifact_root / RUNTIME_STATE_NAME,
        )
    else:
        context = require_context_for_repo(repo)
        workspace_root = resolve_context_workspace_root(
            repo=repo,
            context=context,
            raw_workspace_root=args.workspace_root,
        )
        defaults = default_workspace_artifacts(context.workspace_root)
        state_default = context.state_path
        launch_path = resolve_repo_relative(
            workspace_root,
            args.launch_path,
            context.launch_path or defaults.launch_path,
        )
        runtime_path = resolve_repo_relative(
            workspace_root,
            args.runtime_path,
            context.runtime_path or defaults.runtime_path,
        )
        results_path = context.results_path
    context = evaluate_launch_context(
        results_path=results_path,
        state_path_arg=args.state_path,
        launch_path=launch_path,
        runtime_path=runtime_path,
        default_state_path=state_default,
        ignore_running_runtime=True,
    )
    if context["decision"] not in {"fresh", "resumable"}:
        raise AutoresearchError(
            f"Cannot generate a runtime prompt for decision={context['decision']}: {context['reason']}"
        )
    if not launch_path.exists():
        raise AutoresearchError(f"Missing JSON file: {launch_path}")
    launch_manifest = read_launch_manifest(launch_path)

    print(
        build_runtime_prompt(
            launch_manifest=launch_manifest,
            launch_context=context,
            launch_path=launch_path,
            results_path=Path(context["results_path"]),
            state_path=Path(context["state_path"]),
        ),
        end="",
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutoresearchError as exc:
        raise SystemExit(f"error: {exc}")
