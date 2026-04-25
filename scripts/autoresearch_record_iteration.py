#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from autoresearch_core import print_json
from autoresearch_decision import apply_status_transition, requires_trial_commit
from autoresearch_helpers import (
    AutoresearchError,
    acceptance_state,
    append_description_suffix,
    append_rows,
    evaluate_required_label_gate,
    format_keep_gate_miss_suffix,
    improvement,
    make_row,
    normalize_labels,
    parse_decimal,
    parse_metrics_json_output,
    parse_results_log,
    repo_commit_map_for_targets,
    repo_targets_from_config,
    require_consistent_state,
    retention_is_preferred,
    resolve_state_path_for_log,
    serialize_metrics,
    write_json_atomic,
)
from autoresearch_lessons import append_iteration_lesson, lessons_path_from_results
from autoresearch_runtime_common import DEFAULT_RESULTS_PATH


STATUSES = ["keep", "discard", "crash", "no-op", "blocked", "drift", "refine", "pivot", "search"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Append one main iteration row and atomically update autoresearch-results/state.json."
    )
    parser.add_argument("--results-path", default=DEFAULT_RESULTS_PATH, help=argparse.SUPPRESS)
    parser.add_argument(
        "--state-path",
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--status", required=True, choices=STATUSES)
    parser.add_argument("--metric")
    parser.add_argument("--commit", default="-")
    parser.add_argument("--guard", default="-")
    parser.add_argument("--description", required=True)
    parser.add_argument(
        "--label",
        action="append",
        default=[],
        help="Attach structured labels/tags to this iteration for keep/stop gating and audit. May be repeated.",
    )
    parser.add_argument(
        "--repo-commit",
        action="append",
        default=[],
        help="Record per-repo commit provenance using PATH=COMMIT. May be repeated.",
    )
    parser.add_argument(
        "--metrics-json",
        help=(
            "Verify output text whose final non-empty line is the structured metrics JSON object. "
            "Required for measured keep/discard/drift iterations when config.verify_format=metrics_json."
        ),
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    results_path = Path(args.results_path)
    parsed = parse_results_log(results_path)
    state_path = resolve_state_path_for_log(
        args.state_path,
        parsed,
        cwd=Path.cwd(),
        results_path=results_path,
    )
    parsed, payload, reconstructed, direction = require_consistent_state(
        results_path,
        state_path,
        parsed=parsed,
    )
    next_iteration = reconstructed["iteration"] + 1
    current_metric = reconstructed["current_metric"]
    config = dict(payload.get("config", {}))
    state = payload["state"]
    current_acceptance_state = acceptance_state(
        config=config,
        metric=current_metric,
        metrics=state.get("current_metrics"),
    )

    trial_metrics_input = None
    measured_status = args.status in {"keep", "discard", "drift"}
    if config.get("verify_format") == "metrics_json" and measured_status and not args.metrics_json:
        raise AutoresearchError("--metrics-json is required when config.verify_format=metrics_json.")
    if args.metrics_json:
        trial_metrics_input = parse_metrics_json_output(
            args.metrics_json,
            field_name="--metrics-json",
        )

    if args.status in {"crash", "no-op", "blocked", "refine", "pivot", "search"}:
        metric = current_metric if args.metric is None else parse_decimal(args.metric, "metric")
    else:
        if args.metric is None:
            if config.get("verify_format") == "metrics_json" and trial_metrics_input is not None:
                primary_metric_key = str(
                    config.get("primary_metric_key") or config.get("metric") or "metric"
                ).strip()
                if primary_metric_key not in trial_metrics_input:
                    raise AutoresearchError(
                        "verify_format=metrics_json requires metrics keys: "
                        + primary_metric_key
                    )
                metric = parse_decimal(
                    trial_metrics_input[primary_metric_key],
                    f"metrics_json[{primary_metric_key!r}]",
                )
            else:
                raise AutoresearchError(f"--metric is required for status {args.status}")
        else:
            metric = parse_decimal(args.metric, "metric")

    if requires_trial_commit(args.status, args.metric is not None, args.guard) and args.commit == "-":
        raise AutoresearchError(
            f"Status {args.status} must provide --commit to preserve trial provenance."
        )
    if args.status == "keep" and not improvement(metric, current_metric, direction):
        raise AutoresearchError("Keep iterations must improve over the retained metric.")

    normalized_labels = normalize_labels(args.label)
    if trial_metrics_input is None and not measured_status:
        trial_acceptance_state = current_acceptance_state
    else:
        trial_acceptance_state = acceptance_state(
            config=config,
            metric=metric,
            metrics=trial_metrics_input,
        )
    final_status = args.status
    final_description = args.description
    if args.status == "keep":
        _, normalized_labels, missing_keep_labels = evaluate_required_label_gate(
            config.get("required_keep_labels", []),
            normalized_labels,
        )
        if missing_keep_labels:
            final_status = "discard"
            final_description = append_description_suffix(
                final_description,
                format_keep_gate_miss_suffix(missing_keep_labels),
            )
        elif not trial_acceptance_state["required_keep_satisfied"]:
            final_status = "discard"
            final_description = append_description_suffix(
                final_description,
                "[KEEP-CRITERIA miss] " + "; ".join(trial_acceptance_state["required_keep_failures"]),
            )
        elif not retention_is_preferred(
            direction=direction,
            current_metric=current_metric,
            current_acceptance=bool(current_acceptance_state["acceptance_satisfied"]),
            trial_metric=metric,
            trial_acceptance=bool(trial_acceptance_state["acceptance_satisfied"]),
        ):
            final_status = "discard"
            final_description = append_description_suffix(
                final_description,
                "[ACCEPTANCE preference] retained result already satisfies final acceptance.",
            )

    new_row = make_row(
        iteration=str(next_iteration),
        commit=args.commit,
        metric=metric,
        delta=metric - current_metric,
        guard=args.guard,
        status=final_status,
        description=final_description,
        labels=normalized_labels,
    )
    append_rows(results_path, [new_row])

    primary_repo_config = config.get("primary_repo")
    if not isinstance(primary_repo_config, str) or not primary_repo_config.strip():
        raise AutoresearchError("State config.primary_repo is required.")
    repo_targets = repo_targets_from_config(Path(primary_repo_config).expanduser().resolve(), config)
    repo_commit_map = repo_commit_map_for_targets(
        repo_targets=repo_targets,
        primary_commit=args.commit,
        repo_commit_specs=args.repo_commit,
        existing=state.get("last_trial_repo_commits") or state.get("last_repo_commits"),
    )

    final_payload = apply_status_transition(
        payload,
        status=final_status,
        metric=metric,
        commit=args.commit,
        direction=direction,
        next_iteration=next_iteration,
        repo_commit_map=repo_commit_map,
        labels=normalized_labels,
        trial_metrics=serialize_metrics(trial_acceptance_state["metrics"]),
        retained_metrics=(
            serialize_metrics(trial_acceptance_state["metrics"])
            if final_status in {"keep", "drift"}
            else serialize_metrics(current_acceptance_state["metrics"])
        ),
        trial_acceptance=bool(trial_acceptance_state["acceptance_satisfied"]),
        retained_acceptance=(
            bool(trial_acceptance_state["acceptance_satisfied"])
            if final_status in {"keep", "drift"}
            else bool(current_acceptance_state["acceptance_satisfied"])
        ),
        trial_required_keep_satisfied=bool(trial_acceptance_state["required_keep_satisfied"]),
        retained_required_keep_satisfied=(
            bool(trial_acceptance_state["required_keep_satisfied"])
            if final_status in {"keep", "drift"}
            else bool(current_acceptance_state["required_keep_satisfied"])
        ),
    )
    write_json_atomic(state_path, final_payload)

    append_iteration_lesson(
        lessons_path=lessons_path_from_results(results_path),
        state_payload=final_payload,
        status=final_status,
        description=new_row["description"],
        iteration=next_iteration,
    )

    print_json(
        {
            "iteration": next_iteration,
            "status": final_status,
            "retained_metric": final_payload["state"]["current_metric"],
            "retained_acceptance": final_payload["state"].get("current_acceptance"),
            "trial_metric": final_payload["state"]["last_trial_metric"],
            "trial_acceptance": final_payload["state"].get("last_trial_acceptance"),
            "trial_labels": final_payload["state"].get("last_trial_labels", []),
            "retained_labels": final_payload["state"].get("current_labels", []),
            "trial_repo_commits": final_payload["state"].get("last_trial_repo_commits", {}),
            "results_path": str(results_path),
            "state_path": str(state_path),
        }
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutoresearchError as exc:
        raise SystemExit(f"error: {exc}")
