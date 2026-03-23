#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from typing import Any

from autoresearch_helpers import (
    AutoresearchError,
    build_state_payload,
    clone_state_payload,
    decimal_to_json_number,
    improvement,
    normalize_repo_commit_map,
    parse_decimal,
)


STATUSES = ["keep", "discard", "crash", "no-op", "blocked", "drift", "refine", "pivot", "search"]
TRIAL_COMMIT_STATUSES = {"keep", "discard", "crash"}


def requires_trial_commit(status: str, metric_provided: bool, guard: str) -> bool:
    return status in TRIAL_COMMIT_STATUSES or (
        status == "refine" and (metric_provided or guard != "-")
    )


def derive_trial_status(
    *,
    direction: str,
    current_metric: Any,
    trial_metric: Any,
    guard: str = "-",
    crashed: bool = False,
) -> dict[str, Any]:
    current = parse_decimal(current_metric, "current metric")
    trial = parse_decimal(trial_metric, "trial metric")
    if crashed:
        return {
            "status": "crash",
            "trial_metric": decimal_to_json_number(current),
            "retained_metric": decimal_to_json_number(current),
            "improved": False,
            "guard": guard,
        }
    if guard not in {"-", "pass"}:
        status = "discard"
    else:
        status = "keep" if improvement(trial, current, direction) else "discard"
    retained = trial if status == "keep" else current
    return {
        "status": status,
        "trial_metric": decimal_to_json_number(trial),
        "retained_metric": decimal_to_json_number(retained),
        "improved": status == "keep",
        "guard": guard,
    }


def apply_status_transition(
    payload: dict[str, Any],
    *,
    status: str,
    metric: Any,
    commit: str,
    direction: str,
    next_iteration: int,
    repo_commit_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    new_payload = clone_state_payload(payload)
    state = new_payload["state"]
    metric_decimal = parse_decimal(metric, "metric")
    existing_retained_repo_commits = normalize_repo_commit_map(state.get("last_repo_commits"))
    existing_trial_repo_commits = normalize_repo_commit_map(state.get("last_trial_repo_commits"))
    incoming_repo_commits = normalize_repo_commit_map(repo_commit_map or {})
    trial_repo_commits = incoming_repo_commits or existing_trial_repo_commits or existing_retained_repo_commits

    state["iteration"] = next_iteration
    state["last_status"] = status
    state["last_trial_commit"] = commit
    state["last_trial_metric"] = decimal_to_json_number(metric_decimal)
    if trial_repo_commits:
        state["last_trial_repo_commits"] = dict(trial_repo_commits)
    else:
        state.pop("last_trial_repo_commits", None)

    if status == "keep":
        state["keeps"] = state.get("keeps", 0) + 1
        state["current_metric"] = decimal_to_json_number(metric_decimal)
        state["last_commit"] = commit
        if trial_repo_commits:
            state["last_repo_commits"] = dict(trial_repo_commits)
        else:
            state.pop("last_repo_commits", None)
        state["consecutive_discards"] = 0
        state["pivot_count"] = 0
        previous_best = parse_decimal(state["best_metric"], "best_metric")
        if improvement(metric_decimal, previous_best, direction):
            state["best_metric"] = decimal_to_json_number(metric_decimal)
            state["best_iteration"] = next_iteration
    elif status == "discard":
        state["discards"] = state.get("discards", 0) + 1
        state["consecutive_discards"] = state.get("consecutive_discards", 0) + 1
    elif status == "crash":
        state["crashes"] = state.get("crashes", 0) + 1
        state["consecutive_discards"] = state.get("consecutive_discards", 0) + 1
    elif status == "no-op":
        state["no_ops"] = state.get("no_ops", 0) + 1
        state["consecutive_discards"] = state.get("consecutive_discards", 0) + 1
    elif status == "blocked":
        state["blocked"] = state.get("blocked", 0) + 1
    elif status == "drift":
        state["current_metric"] = decimal_to_json_number(metric_decimal)
        if commit != "-":
            state["last_commit"] = commit
            if trial_repo_commits:
                state["last_repo_commits"] = dict(trial_repo_commits)
            else:
                state.pop("last_repo_commits", None)
        state["consecutive_discards"] = 0
        previous_best = parse_decimal(state["best_metric"], "best_metric")
        if improvement(metric_decimal, previous_best, direction):
            state["best_metric"] = decimal_to_json_number(metric_decimal)
            state["best_iteration"] = next_iteration
    elif status == "pivot":
        state["pivot_count"] = state.get("pivot_count", 0) + 1
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
        "consecutive_discards": state["consecutive_discards"],
        "pivot_count": state["pivot_count"],
        "last_status": state["last_status"],
    }
    if "last_repo_commits" in state:
        rewritten_summary["last_repo_commits"] = dict(state["last_repo_commits"])
    if "last_trial_repo_commits" in state:
        rewritten_summary["last_trial_repo_commits"] = dict(state["last_trial_repo_commits"])
    return build_state_payload(
        mode=new_payload["mode"],
        run_tag=new_payload.get("run_tag") or None,
        config=new_payload["config"],
        summary=rewritten_summary,
        supervisor=new_payload.get("supervisor"),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate mechanical keep/discard/crash decisions for autoresearch."
    )
    parser.add_argument("--direction", required=True, choices=["lower", "higher"])
    parser.add_argument("--current-metric", required=True)
    parser.add_argument("--trial-metric", required=True)
    parser.add_argument("--guard", default="-")
    parser.add_argument("--crashed", action="store_true")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    print(
        json.dumps(
            derive_trial_status(
                direction=args.direction,
                current_metric=args.current_metric,
                trial_metric=args.trial_metric,
                guard=args.guard,
                crashed=args.crashed,
            ),
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
