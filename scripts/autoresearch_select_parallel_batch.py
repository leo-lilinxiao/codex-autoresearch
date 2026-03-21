#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from autoresearch_helpers import (
    AutoresearchError,
    append_rows,
    build_state_payload,
    clone_state_payload,
    decimal_to_json_number,
    improvement,
    make_row,
    parse_decimal,
    parse_results_log,
    require_consistent_state,
    resolve_state_path_for_log,
    write_json_atomic,
)


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
        help="JSON array of worker results. Each item needs worker_id, description, and optionally commit, metric, guard, status, diff_size.",
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
    batch = load_batch(Path(args.batch_file))

    next_iteration = reconstructed["iteration"] + 1
    current_metric = reconstructed["current_metric"]
    candidates: list[dict[str, object]] = []
    worker_records: list[dict[str, object]] = []

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
        last_trial_commit = winner_commit
    elif best_completed_record is not None:
        main_metric = best_completed_record["metric"]
        main_guard = str(best_completed_record["guard"])
        main_description = (
            "[PARALLEL batch] no worker produced a keepable improvement; "
            f"best discarded worker-{best_completed_record['worker_id']}: "
            f"{best_completed_record['description']}"
        )
        last_trial_commit = str(best_completed_record["commit"])

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
    )
    append_rows(results_path, worker_rows + [main_row])

    new_payload = clone_state_payload(payload)
    state = new_payload["state"]
    state["iteration"] = next_iteration
    state["last_status"] = main_status
    state["last_trial_commit"] = last_trial_commit
    state["last_trial_metric"] = decimal_to_json_number(main_metric)

    if main_status == "keep":
        state["keeps"] = state.get("keeps", 0) + 1
        state["current_metric"] = decimal_to_json_number(main_metric)
        state["last_commit"] = main_commit
        state["consecutive_discards"] = 0
        state["pivot_count"] = 0
        previous_best = parse_decimal(state["best_metric"], "best_metric")
        if improvement(main_metric, previous_best, direction):
            state["best_metric"] = decimal_to_json_number(main_metric)
            state["best_iteration"] = next_iteration
    else:
        state["discards"] = state.get("discards", 0) + 1
        state["consecutive_discards"] = state.get("consecutive_discards", 0) + 1

    rewritten_summary = {
        "iteration": state["iteration"],
        "baseline_metric": parse_decimal(state["baseline_metric"], "baseline_metric"),
        "best_metric": parse_decimal(state["best_metric"], "best_metric"),
        "best_iteration": state["best_iteration"],
        "current_metric": parse_decimal(state["current_metric"], "current_metric"),
        "last_commit": state["last_commit"],
        "last_trial_commit": state["last_trial_commit"],
        "last_trial_metric": parse_decimal(state["last_trial_metric"], "last_trial_metric"),
        "keeps": state["keeps"],
        "discards": state["discards"],
        "crashes": state["crashes"],
        "no_ops": state.get("no_ops", 0),
        "blocked": state.get("blocked", 0),
        "splits": state.get("splits", 0),
        "consecutive_discards": state["consecutive_discards"],
        "pivot_count": state["pivot_count"],
        "last_status": state["last_status"],
    }
    final_payload = build_state_payload(
        mode=new_payload["mode"],
        run_tag=new_payload.get("run_tag") or None,
        config=new_payload["config"],
        summary=rewritten_summary,
    )
    write_json_atomic(state_path, final_payload)

    print(
        json.dumps(
            {
                "iteration": next_iteration,
                "selected_worker": None if winner is None else winner["worker_id"],
                "status": main_status,
                "retained_metric": state["current_metric"],
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
