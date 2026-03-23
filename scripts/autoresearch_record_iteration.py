#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from autoresearch_decision import apply_status_transition, requires_trial_commit
from autoresearch_helpers import (
    AutoresearchError,
    append_rows,
    improvement,
    make_row,
    parse_decimal,
    parse_results_log,
    repo_commit_map_for_targets,
    repo_targets_from_config,
    require_consistent_state,
    resolve_state_path_for_log,
    results_repo_root,
    write_json_atomic,
)
from autoresearch_lessons import append_iteration_lesson, lessons_path_from_results


STATUSES = ["keep", "discard", "crash", "no-op", "blocked", "drift", "refine", "pivot", "search"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Append one main iteration row and atomically update autoresearch-state.json."
    )
    parser.add_argument("--results-path", default="research-results.tsv")
    parser.add_argument(
        "--state-path",
        help=(
            "State JSON path. Defaults to autoresearch-state.json, except logs tagged "
            "with '# mode: exec' default to the deterministic exec scratch state."
        ),
    )
    parser.add_argument("--status", required=True, choices=STATUSES)
    parser.add_argument("--metric")
    parser.add_argument("--commit", default="-")
    parser.add_argument("--guard", default="-")
    parser.add_argument("--description", required=True)
    parser.add_argument(
        "--repo-commit",
        action="append",
        default=[],
        help="Record per-repo commit provenance using PATH=COMMIT. May be repeated.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    results_path = Path(args.results_path)
    repo_hint = results_path.parent if results_path.is_absolute() else None
    parsed = parse_results_log(results_path)
    state_path = resolve_state_path_for_log(args.state_path, parsed, cwd=repo_hint)
    parsed, payload, reconstructed, direction = require_consistent_state(
        results_path,
        state_path,
        parsed=parsed,
    )
    next_iteration = reconstructed["iteration"] + 1
    current_metric = reconstructed["current_metric"]

    if args.status in {"crash", "no-op", "blocked", "refine", "pivot", "search"}:
        metric = current_metric if args.metric is None else parse_decimal(args.metric, "metric")
    else:
        if args.metric is None:
            raise AutoresearchError(f"--metric is required for status {args.status}")
        metric = parse_decimal(args.metric, "metric")

    if requires_trial_commit(args.status, args.metric is not None, args.guard) and args.commit == "-":
        raise AutoresearchError(
            f"Status {args.status} must provide --commit to preserve trial provenance."
        )
    if args.status == "keep" and not improvement(metric, current_metric, direction):
        raise AutoresearchError("Keep iterations must improve over the retained metric.")

    new_row = make_row(
        iteration=str(next_iteration),
        commit=args.commit,
        metric=metric,
        delta=metric - current_metric,
        guard=args.guard,
        status=args.status,
        description=args.description,
    )
    append_rows(results_path, [new_row])

    repo_targets = repo_targets_from_config(results_repo_root(results_path), payload.get("config", {}))
    state = payload["state"]
    repo_commit_map = repo_commit_map_for_targets(
        repo_targets=repo_targets,
        primary_commit=args.commit,
        repo_commit_specs=args.repo_commit,
        existing=state.get("last_trial_repo_commits") or state.get("last_repo_commits"),
    )

    final_payload = apply_status_transition(
        payload,
        status=args.status,
        metric=metric,
        commit=args.commit,
        direction=direction,
        next_iteration=next_iteration,
        repo_commit_map=repo_commit_map,
    )
    write_json_atomic(state_path, final_payload)

    append_iteration_lesson(
        lessons_path=lessons_path_from_results(results_path),
        state_payload=final_payload,
        status=args.status,
        description=args.description,
        iteration=next_iteration,
    )

    print(
        json.dumps(
            {
                "iteration": next_iteration,
                "status": args.status,
                "retained_metric": final_payload["state"]["current_metric"],
                "trial_metric": final_payload["state"]["last_trial_metric"],
                "trial_repo_commits": final_payload["state"].get("last_trial_repo_commits", {}),
                "results_path": str(results_path),
                "state_path": str(state_path),
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
