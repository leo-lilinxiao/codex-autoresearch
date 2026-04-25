#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from autoresearch_core import print_json
from autoresearch_decision import apply_status_transition
from autoresearch_helpers import (
    AutoresearchError,
    acceptance_state,
    append_description_suffix,
    append_rows,
    evaluate_required_label_gate,
    format_keep_gate_miss_suffix,
    improvement,
    make_row,
    normalize_repo_commit_map,
    normalize_labels,
    parse_decimal,
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
from autoresearch_preflight import evaluate_managed_repos_preflight
from autoresearch_runtime_common import DEFAULT_RESULTS_PATH


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Select the best parallel worker result, append worker/main TSV rows, and update state once."
    )
    parser.add_argument("--results-path", default=DEFAULT_RESULTS_PATH, help=argparse.SUPPRESS)
    parser.add_argument(
        "--state-path",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--batch-file",
        required=True,
        help=(
            "JSON array of worker results. Each item needs worker_id, description, "
            "and optionally commit, repo_commits, labels, metric, guard, status, diff_size."
        ),
    )
    return parser


def load_batch(path: Path) -> list[dict[str, object]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AutoresearchError(f"Missing batch file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise AutoresearchError(f"Invalid batch JSON in {path}: {exc}") from exc
    if not isinstance(data, list) or not data:
        raise AutoresearchError("Batch file must contain a non-empty JSON array.")
    return data


def diff_rank(item: dict[str, object]) -> int:
    diff_size = item.get("diff_size")
    if isinstance(diff_size, int):
        return diff_size
    return 10**9


def acceptance_rank(item: dict[str, object]) -> int:
    acceptance = item.get("acceptance_state")
    if isinstance(acceptance, dict) and acceptance.get("acceptance_satisfied"):
        return 0
    return 1


def metric_sort_value(metric: object, direction: str):
    value = parse_decimal(metric, "metric sort value")
    return value if direction == "lower" else -value


def select_best_candidate(
    candidates: list[dict[str, object]],
    direction: str,
) -> dict[str, object] | None:
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda item: (
            acceptance_rank(item),
            metric_sort_value(item["metric_decimal"], direction),
            diff_rank(item),
            str(item["worker_id"]),
        ),
    )


def select_best_completed_record(
    worker_records: list[dict[str, object]],
    direction: str,
) -> dict[str, object] | None:
    completed_records = [
        record for record in worker_records if str(record["status"]) in {"candidate", "discard"}
    ]
    if not completed_records:
        return None
    return min(
        completed_records,
        key=lambda record: (
            acceptance_rank(record),
            metric_sort_value(record["metric"], direction),
            str(record["guard"]) != "pass",
            diff_rank(record),
            str(record["worker_id"]),
        ),
    )


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
    _, payload, reconstructed, direction = require_consistent_state(
        results_path,
        state_path,
        parsed=parsed,
    )
    config = dict(payload.get("config", {}))
    primary_repo_config = config.get("primary_repo")
    if not isinstance(primary_repo_config, str) or not primary_repo_config.strip():
        raise AutoresearchError("State config.primary_repo is required.")
    repo = Path(primary_repo_config).expanduser().resolve()
    preflight = evaluate_managed_repos_preflight(
        primary_repo=repo,
        workspace_root=Path(str(config.get("workspace_root") or repo)),
        results_path=results_path,
        state_path_arg=args.state_path,
        verify_command=str(config.get("verify", "")),
        verify_cwd=str(config.get("verify_cwd") or "workspace_root"),
        commit_phase="prebatch",
        repo_targets=repo_targets_from_config(repo, config),
        include_health=True,
        rollback_policy=None,
        destructive_approved=False,
    )
    if preflight["decision"] == "block":
        raise AutoresearchError(
            "Parallel batch preflight failed: " + "; ".join(preflight["blockers"])
        )
    batch = load_batch(Path(args.batch_file))

    next_iteration = reconstructed["iteration"] + 1
    current_metric = reconstructed["current_metric"]
    current_acceptance_state = acceptance_state(
        config=config,
        metric=current_metric,
        metrics=payload["state"].get("current_metrics"),
    )
    required_keep_labels = config.get("required_keep_labels", [])
    candidates: list[dict[str, object]] = []
    worker_records: list[dict[str, object]] = []
    repo_targets = repo_targets_from_config(repo, config)

    for item in batch:
        if not isinstance(item, dict):
            raise AutoresearchError("Each batch entry must be an object.")
        if "worker_id" not in item or "description" not in item:
            raise AutoresearchError("Each batch entry needs worker_id and description.")
        worker_id = str(item["worker_id"])
        if not worker_id.isalpha() or not worker_id.islower():
            raise AutoresearchError(f"worker_id must be lowercase letters: {worker_id!r}")
        status = str(item.get("status", "completed"))
        guard = str(item.get("guard", "-"))
        commit = str(item.get("commit", "-"))
        description = str(item["description"])
        labels = normalize_labels(item.get("labels", []))
        metric = current_metric
        row_status = "crash" if status in {"crash", "timeout"} else "discard"

        if status not in {"completed", "crash", "timeout"}:
            raise AutoresearchError(
                f"Worker {worker_id!r} has unsupported status {status!r}; use completed/crash/timeout."
            )

        if status == "completed":
            if "metric" not in item:
                raise AutoresearchError(f"Worker {worker_id!r} is missing metric.")
            metric = parse_decimal(item["metric"], f"worker {worker_id} metric")
            if config.get("verify_format") == "metrics_json":
                if "metrics" not in item:
                    raise AutoresearchError(
                        f"Worker {worker_id!r} is missing metrics for verify_format=metrics_json."
                    )
                if not isinstance(item.get("metrics"), dict):
                    raise AutoresearchError(f"Worker {worker_id!r} metrics must be a JSON object.")
            acceptance = acceptance_state(
                config=config,
                metric=metric,
                metrics=item.get("metrics"),
            )
            improved = guard == "pass" and improvement(metric, current_metric, direction)
            if improved:
                _, labels, missing_keep_labels = evaluate_required_label_gate(
                    required_keep_labels,
                    labels,
                )
                if missing_keep_labels:
                    row_status = "discard"
                    description = append_description_suffix(
                        description,
                        format_keep_gate_miss_suffix(missing_keep_labels),
                    )
                elif not acceptance["required_keep_satisfied"]:
                    row_status = "discard"
                    description = append_description_suffix(
                        description,
                        "[KEEP-CRITERIA miss] " + "; ".join(acceptance["required_keep_failures"]),
                    )
                elif not retention_is_preferred(
                    direction=direction,
                    current_metric=current_metric,
                    current_acceptance=bool(current_acceptance_state["acceptance_satisfied"]),
                    trial_metric=metric,
                    trial_acceptance=bool(acceptance["acceptance_satisfied"]),
                ):
                    row_status = "discard"
                    description = append_description_suffix(
                        description,
                        "[ACCEPTANCE preference] retained result already satisfies final acceptance.",
                    )
                else:
                    row_status = "candidate"
                    item["metric_decimal"] = metric
                    item["normalized_labels"] = labels
                    item["normalized_description"] = description
                    item["acceptance_state"] = acceptance
                    candidates.append(item)
            else:
                row_status = "discard"
        else:
            acceptance = None

        worker_records.append(
            {
                "worker_id": worker_id,
                "commit": commit,
                "repo_commits": normalize_repo_commit_map(item.get("repo_commits")),
                "labels": labels,
                "metric": metric,
                "guard": guard,
                "description": description,
                "status": row_status,
                "diff_size": item.get("diff_size"),
                "acceptance_state": acceptance,
            }
        )

    winner = select_best_candidate(candidates, direction)
    best_completed_record = (
        select_best_completed_record(worker_records, direction) if winner is None else None
    )

    main_status = "discard"
    main_commit = "-"
    main_metric = current_metric
    main_guard = "-"
    main_description = "[PARALLEL batch] no worker improved the retained metric"
    last_trial_commit = "-"
    main_acceptance_state = current_acceptance_state

    if winner is not None:
        winner_metric = parse_decimal(winner["metric_decimal"], "winner metric")
        winner_commit = str(winner.get("commit", "-"))
        if winner_commit == "-":
            raise AutoresearchError(
                f"Worker {winner['worker_id']!r} improved the metric but did not report a commit."
            )
        main_status = "keep"
        main_commit = winner_commit
        main_metric = winner_metric
        main_guard = str(winner.get("guard", "pass"))
        main_description = (
            f"[PARALLEL batch] selected worker-{winner['worker_id']}: "
            f"{winner.get('normalized_description', winner['description'])}"
        )
        main_labels = winner.get("normalized_labels", winner.get("labels", []))
        main_acceptance_state = winner["acceptance_state"]
        last_trial_commit = winner_commit
        last_trial_repo_commits = repo_commit_map_for_targets(
            repo_targets=repo_targets,
            primary_commit=winner_commit,
            repo_commit_specs=[
                f"{path}={commit}"
                for path, commit in normalize_repo_commit_map(winner.get("repo_commits")).items()
            ],
            existing=payload["state"].get("last_trial_repo_commits")
            or payload["state"].get("last_repo_commits"),
        )
    elif best_completed_record is not None:
        main_commit = str(best_completed_record["commit"])
        main_metric = best_completed_record["metric"]
        main_guard = str(best_completed_record["guard"])
        main_description = (
            "[PARALLEL batch] no worker produced a keepable improvement; "
            f"best discarded worker-{best_completed_record['worker_id']}: "
            f"{best_completed_record['description']}"
        )
        main_labels = best_completed_record.get("labels", [])
        if isinstance(best_completed_record.get("acceptance_state"), dict):
            main_acceptance_state = best_completed_record["acceptance_state"]
        last_trial_commit = main_commit
        last_trial_repo_commits = repo_commit_map_for_targets(
            repo_targets=repo_targets,
            primary_commit=last_trial_commit,
            repo_commit_specs=[
                f"{path}={commit}"
                for path, commit in normalize_repo_commit_map(best_completed_record.get("repo_commits")).items()
            ],
            existing=payload["state"].get("last_trial_repo_commits")
            or payload["state"].get("last_repo_commits"),
        )
    else:
        main_labels = []
        last_trial_repo_commits = normalize_repo_commit_map(
            payload["state"].get("last_trial_repo_commits")
            or payload["state"].get("last_repo_commits")
        )

    worker_rows: list[dict[str, str]] = []
    selected_worker_id = None if winner is None else str(winner["worker_id"])
    for record in worker_records:
        row_status = str(record["status"])
        if row_status == "candidate":
            row_status = "keep" if record["worker_id"] == selected_worker_id else "discard"
        worker_rows.append(
            make_row(
                iteration=f"{next_iteration}{record['worker_id']}",
                commit=record["commit"] if row_status == "keep" else "-",
                metric=record["metric"],
                delta=record["metric"] - current_metric,
                guard=str(record["guard"]),
                status=row_status,
                description=f"[PARALLEL worker-{record['worker_id']}] {record['description']}",
                labels=record.get("labels", []),
            )
        )

    main_row = make_row(
        iteration=str(next_iteration),
        commit=main_commit,
        metric=main_metric,
        delta=main_metric - current_metric,
        guard=main_guard,
        status=main_status,
        description=main_description,
        labels=main_labels,
    )
    append_rows(results_path, worker_rows + [main_row])

    trial_commit = main_commit if main_status == "keep" else last_trial_commit
    final_payload = apply_status_transition(
        payload,
        status=main_status,
        metric=main_metric,
        commit=trial_commit,
        direction=direction,
        next_iteration=next_iteration,
        repo_commit_map=last_trial_repo_commits,
        labels=main_labels,
        trial_metrics=serialize_metrics(main_acceptance_state["metrics"]),
        retained_metrics=(
            serialize_metrics(main_acceptance_state["metrics"])
            if main_status in {"keep", "drift"}
            else serialize_metrics(current_acceptance_state["metrics"])
        ),
        trial_acceptance=bool(main_acceptance_state["acceptance_satisfied"]),
        retained_acceptance=(
            bool(main_acceptance_state["acceptance_satisfied"])
            if main_status in {"keep", "drift"}
            else bool(current_acceptance_state["acceptance_satisfied"])
        ),
        trial_required_keep_satisfied=bool(main_acceptance_state["required_keep_satisfied"]),
        retained_required_keep_satisfied=(
            bool(main_acceptance_state["required_keep_satisfied"])
            if main_status in {"keep", "drift"}
            else bool(current_acceptance_state["required_keep_satisfied"])
        ),
    )
    write_json_atomic(state_path, final_payload)
    append_iteration_lesson(
        lessons_path=lessons_path_from_results(results_path),
        state_payload=final_payload,
        status=main_status,
        description=main_row["description"],
        iteration=next_iteration,
    )

    print_json(
        {
            "iteration": next_iteration,
            "selected_worker": None if winner is None else winner["worker_id"],
            "status": main_status,
            "retained_metric": final_payload["state"]["current_metric"],
            "retained_acceptance": final_payload["state"].get("current_acceptance"),
            "retained_labels": final_payload["state"].get("current_labels", []),
            "trial_metric": final_payload["state"]["last_trial_metric"],
            "trial_acceptance": final_payload["state"].get("last_trial_acceptance"),
            "batch_file": str(args.batch_file),
            "message": f"Parallel batch recorded at iteration {next_iteration}.",
        }
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutoresearchError as exc:
        raise SystemExit(f"error: {exc}")
