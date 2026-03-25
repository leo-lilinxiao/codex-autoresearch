#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from autoresearch_helpers import (
    AutoresearchError,
    format_repo_target_label,
    repo_targets_from_config,
    read_launch_manifest,
    resolve_repo_path,
    resolve_repo_relative,
    results_repo_root,
    resolve_repo_managed_path,
)
from autoresearch_launch_gate import evaluate_launch_context


DEFAULT_RESULTS_PATH = "research-results.tsv"
OPTIONAL_CONFIG_FIELDS = (
    ("execution_policy", "Execution policy"),
    ("guard", "Guard"),
    ("iterations", "Iterations"),
    ("stop_condition", "Stop condition"),
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
    primary_repo = results_repo_root(results_path)
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
            "Instructions:",
            "- Do not run the interactive wizard again.",
            "- Do not ask the user for launch confirmation again.",
            "- If results/state artifacts exist, resume from them.",
            "- If they do not exist yet, initialize a fresh run from the launch manifest.",
            "- When initializing fresh artifacts for this managed run, call autoresearch_init_run.py with --session-mode background.",
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
        help="Primary repo root. Preferred entrypoint when generating a runtime-managed prompt.",
    )
    parser.add_argument(
        "--results-path",
        help=(
            "Results log path. Overrides the repo-derived default when provided. "
            f"Defaults to {DEFAULT_RESULTS_PATH} in --repo or the current directory."
        ),
    )
    parser.add_argument("--state-path")
    parser.add_argument("--launch-path")
    parser.add_argument("--runtime-path")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.repo is not None:
        repo = resolve_repo_path(args.repo)
        results_path = resolve_repo_relative(repo, args.results_path, repo / DEFAULT_RESULTS_PATH)
        launch_path = resolve_repo_relative(repo, args.launch_path, repo / "autoresearch-launch.json")
        runtime_path = resolve_repo_relative(repo, args.runtime_path, repo / "autoresearch-runtime.json")
    else:
        results_path = Path(args.results_path or DEFAULT_RESULTS_PATH)
        launch_path = resolve_repo_managed_path(
            args.launch_path,
            results_path=results_path,
            default_name="autoresearch-launch.json",
        )
        runtime_path = resolve_repo_managed_path(
            args.runtime_path,
            results_path=results_path,
            default_name="autoresearch-runtime.json",
        )
    context = evaluate_launch_context(
        results_path=results_path,
        state_path_arg=args.state_path,
        launch_path=launch_path,
        runtime_path=runtime_path,
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
