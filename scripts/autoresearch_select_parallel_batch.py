#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from autoresearch_decision import apply_status_transition
from autoresearch_helpers import (
    AutoresearchError,
    append_rows,
    improvement,
    make_row,
    normalize_repo_commit_map,
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
from autoresearch_preflight import evaluate_managed_repos_preflight


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Select the best parallel worker result, append worker/main TSV rows, and update state once."
    )
    parser.add_argument("--results-path", default="research-results.tsv")
    parser.add_argument(
        "--state-path",
        help=(
            "State JSON path. Defaults to autoresearch-state.json, except logs tagged "
            "with '# mode: exec' default to the deterministic exec scratch state."
        ),
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


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    results_path = Path(args.results_path)
    repo_hint = results_path.parent if results_path.is_absolute() else None
    parsed = parse_results_log(results_path)
    state_path = resolve_state_path_for_log(args.state_path, parsed, cwd=repo_hint)
    _, payload, reconstructed, direction = require_consistent_state(
        results_path,
        state_path,
        parsed=parsed,
    )
    config = dict(payload.get("config", {}))
    repo = results_repo_root(results_path)
    preflight = evaluate_managed_repos_preflight(
        primary_repo=repo,
        results_path=results_path,
        state_path_arg=args.state_path,
        verify_command=str(config.get("verify", "")),
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
            improved = guard == "pass" and improvement(metric, current_metric, direction)
            if improved:
                row_status = "candidate"
                item["metric_decimal"] = metric
                candidates.append(item)
            else:
                row_status = "discard"

        worker_records.append(
            {
                "worker_id": worker_id,
                "commit": commit,
                "repo_commits": normalize_repo_commit_map(item.get("repo_commits")),
                "labels": item.get("labels", []),
                "metric": metric,
                "guard": guard,
                "description": description,
                "status": row_status,
            }
        )

    winner = None
    if candidates:
        if direction == "lower":
            winner = sorted(
                candidates,
                key=lambda item: (
                    item["metric_decimal"],
                    diff_rank(item),
                    str(item["worker_id"]),
                ),
            )[0]
        else:
            winner = sorted(
                candidates,
                key=lambda item: (
                    -item["metric_decimal"],
                    diff_rank(item),
                    str(item["worker_id"]),
                ),
            )[0]

    best_completed_record = None
    if winner is None:
        completed_records = [
            record for record in worker_records if str(record["status"]) in {"candidate", "discard"}
        ]
        if completed_records:
            if direction == "lower":
                best_completed_record = sorted(
                    completed_records,
                    key=lambda record: (
                        record["metric"],
                        str(record["guard"]) != "pass",
                        diff_rank(record),
                        str(record["worker_id"]),
                    ),
                )[0]
            else:
                best_completed_record = sorted(
                    completed_records,
                    key=lambda record: (
                        -record["metric"],
                        str(record["guard"]) != "pass",
                        diff_rank(record),
                        str(record["worker_id"]),
                    ),
                )[0]

    main_status = "discard"
    main_commit = "-"
    main_metric = current_metric
    main_guard = "-"
    main_description = "[PARALLEL batch] no worker improved the retained metric"
    last_trial_commit = "-"

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
            f"[PARALLEL batch] selected worker-{winner['worker_id']}: {winner['description']}"
        )
        main_labels = winner.get("labels", [])
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
        main_metric = best_completed_record["metric"]
        main_guard = str(best_completed_record["guard"])
        main_description = (
            "[PARALLEL batch] no worker produced a keepable improvement; "
            f"best discarded worker-{best_completed_record['worker_id']}: "
            f"{best_completed_record['description']}"
        )
        main_labels = best_completed_record.get("labels", [])
        last_trial_commit = str(best_completed_record["commit"])
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
    )
    write_json_atomic(state_path, final_payload)
    append_iteration_lesson(
        lessons_path=lessons_path_from_results(results_path),
        state_payload=final_payload,
        status=main_status,
        description=main_row["description"],
        iteration=next_iteration,
    )

    print(
        json.dumps(
            {
                "iteration": next_iteration,
                "selected_worker": None if winner is None else winner["worker_id"],
                "status": main_status,
                "retained_metric": final_payload["state"]["current_metric"],
                "retained_labels": final_payload["state"].get("current_labels", []),
                "batch_file": str(args.batch_file),
                "message": f"Parallel batch recorded at iteration {next_iteration}.",
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
