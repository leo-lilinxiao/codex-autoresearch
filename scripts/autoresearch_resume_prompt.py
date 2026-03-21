#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from autoresearch_helpers import (
    AutoresearchError,
    read_launch_manifest,
    resolve_repo_managed_path,
)
from autoresearch_launch_gate import evaluate_launch_context


OPTIONAL_CONFIG_FIELDS = (
    ("guard", "Guard"),
    ("iterations", "Iterations"),
    ("stop_condition", "Stop condition"),
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
    lines = [
        "$codex-autoresearch",
        "This repo is managed by the autoresearch runtime controller.",
        "The human already completed the confirmation phase for this run.",
        f"Use {launch_path} as the authoritative launch manifest.",
        f"Runtime launch decision: {decision} ({strategy}).",
        "",
        f"Original ask: {launch_manifest['original_goal']}",
        f"Mode: {launch_manifest.get('mode', 'loop')}",
        f"Goal: {config.get('goal', '')}",
        f"Scope: {config.get('scope', '')}",
        f"Metric: {config.get('metric', '')}",
        f"Direction: {config.get('direction', '')}",
        f"Verify: {config.get('verify', '')}",
    ]
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
            "- Continue autonomously until a terminal condition or blocker is reached.",
            "- Keep all run-control decisions aligned with the launch manifest and current state.",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate the runtime-managed resume prompt from the launch manifest and current state."
    )
    parser.add_argument("--results-path", default="research-results.tsv")
    parser.add_argument("--state-path")
    parser.add_argument("--launch-path")
    parser.add_argument("--runtime-path")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    results_path = Path(args.results_path)

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
