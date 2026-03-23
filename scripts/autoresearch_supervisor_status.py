#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from decimal import Decimal
from pathlib import Path
from typing import Any

from autoresearch_helpers import (
    AutoresearchError,
    compare_summary_to_state,
    decimal_to_json_number,
    parse_decimal,
    parse_results_log,
    read_state_payload,
    resolve_repo_path,
    resolve_repo_relative,
    resolve_state_path_for_log,
    utc_now,
    write_json_atomic,
    log_summary,
)


DEFAULT_RESULTS_PATH = "research-results.tsv"
RELAUNCH = "relaunch"
STOP = "stop"
NEEDS_HUMAN = "needs_human"
VALID_DECISIONS = {RELAUNCH, STOP, NEEDS_HUMAN}
NUMBER_PATTERN = r"-?(?:\d+(?:\.\d+)?|\.\d+)"
WORD_NUMBER_MAP = {
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Decide whether an external autoresearch supervisor should relaunch Codex, stop, or ask for human help."
    )
    parser.add_argument(
        "--repo",
        help="Primary repo root. Preferred entrypoint when inspecting supervisor state.",
    )
    parser.add_argument(
        "--results-path",
        help=(
            "Results log path. Overrides the repo-derived default when provided. "
            f"Defaults to {DEFAULT_RESULTS_PATH} in --repo or the current directory."
        ),
    )
    parser.add_argument(
        "--state-path",
        help=(
            "State JSON path. Defaults to autoresearch-state.json, except logs tagged "
            "with '# mode: exec' default to the deterministic exec scratch state."
        ),
    )
    parser.add_argument(
        "--max-stagnation",
        type=int,
        default=3,
        help="Consecutive no-progress exits tolerated before returning needs_human.",
    )
    parser.add_argument(
        "--after-run",
        action="store_true",
        help="Indicates this check is happening after a Codex run finished; increments restart accounting.",
    )
    parser.add_argument(
        "--write-state",
        action="store_true",
        help="Persist the computed supervisor metadata back into autoresearch-state.json.",
    )
    return parser


def as_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return default


def progress_signature(payload: dict[str, Any]) -> str:
    state = payload.get("state", {})
    signature = {
        "iteration": state.get("iteration"),
        "last_status": state.get("last_status"),
        "last_trial_commit": state.get("last_trial_commit"),
        "last_trial_metric": state.get("last_trial_metric"),
    }
    return json.dumps(signature, sort_keys=True, separators=(",", ":"))


def normalized_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def replace_word_numbers(text: str) -> str:
    if not text:
        return text
    pattern = r"\b(" + "|".join(sorted(WORD_NUMBER_MAP, key=len, reverse=True)) + r")\b"
    return re.sub(pattern, lambda match: WORD_NUMBER_MAP[match.group(1)], text)


def compare_metric(current_metric: Decimal, target: Decimal, operator: str) -> bool:
    if operator == "<":
        return current_metric < target
    if operator == "<=":
        return current_metric <= target
    if operator == ">":
        return current_metric > target
    if operator == ">=":
        return current_metric >= target
    if operator == "==":
        return current_metric == target
    raise AutoresearchError(f"Unsupported stop-condition operator: {operator!r}")


def parse_stop_condition_rule(
    stop_condition: str, direction: str
) -> tuple[str, Decimal, str] | None:
    text = replace_word_numbers(normalized_text(stop_condition))
    if not text:
        return None

    threshold_operator = "<=" if direction == "lower" else ">="
    threshold_description = (
        "current metric <= {target}"
        if threshold_operator == "<="
        else "current metric >= {target}"
    )
    patterns: list[tuple[str, str, str]] = [
        (rf"(?:<=|=<)\s*({NUMBER_PATTERN})", "<=", "current metric <= {target}"),
        (rf"(?:>=|=>)\s*({NUMBER_PATTERN})", ">=", "current metric >= {target}"),
        (rf"(?<![<>])<\s*({NUMBER_PATTERN})", "<", "current metric < {target}"),
        (rf"(?<![<>])>\s*({NUMBER_PATTERN})", ">", "current metric > {target}"),
        (
            rf"(?:at most|no more than|up to)\s*({NUMBER_PATTERN})",
            "<=",
            "current metric <= {target}",
        ),
        (
            rf"(?:at least|no less than)\s*({NUMBER_PATTERN})",
            ">=",
            "current metric >= {target}",
        ),
        (
            rf"(?:below|under|less than)\s*({NUMBER_PATTERN})",
            "<",
            "current metric < {target}",
        ),
        (
            rf"(?:above|over|greater than|more than)\s*({NUMBER_PATTERN})",
            ">",
            "current metric > {target}",
        ),
        (
            rf"(?:equals?|exactly|is)\s*({NUMBER_PATTERN})",
            "==",
            "current metric == {target}",
        ),
        (
            rf"(?:reaches?|hits?|gets?\s+to|down to)\s*({NUMBER_PATTERN})",
            threshold_operator,
            threshold_description,
        ),
    ]

    for pattern, operator, description in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        target = parse_decimal(match.group(1), field_name="stop_condition target")
        return operator, target, description.format(target=match.group(1))
    return None


def goal_reached_reason(payload: dict[str, Any], current_metric: Decimal) -> str | None:
    config = payload.get("config", {})
    direction = config.get("direction")
    if payload.get("mode") == "fix":
        if direction == "lower" and current_metric == 0:
            return "Fix mode reached zero remaining errors."

    stop_condition = config.get("stop_condition")
    if not stop_condition:
        return None

    rule = parse_stop_condition_rule(str(stop_condition), direction)
    if rule is None:
        return None

    operator, target, description = rule
    if compare_metric(current_metric, target, operator):
        return f"Configured stop condition is satisfied ({description})."
    return None


def determine_base_decision(
    payload: dict[str, Any], current_metric: object
) -> tuple[str, str, str, list[str]]:
    reasons: list[str] = []
    mode = payload.get("mode")
    config = payload.get("config", {})
    state = payload.get("state", {})
    last_status = state.get("last_status")
    iteration = as_int(state.get("iteration"))
    iterations_cap = config.get("iterations")

    if mode == "exec":
        reasons.append("Exec mode is one-shot and should not be relaunched automatically.")
        return STOP, "exec_mode_completed", "exec_complete", reasons

    goal_reason = goal_reached_reason(payload, current_metric)
    if goal_reason is not None:
        reasons.append(goal_reason)
        return STOP, "goal_reached", "terminal", reasons

    if last_status == "blocked":
        reasons.append("Last recorded status is blocked; unattended relaunch would likely spin without progress.")
        return NEEDS_HUMAN, "blocked", "terminal", reasons

    if isinstance(iterations_cap, int) and iterations_cap >= 0 and iteration >= iterations_cap:
        reasons.append(
            f"Configured iteration cap reached ({iteration} >= {iterations_cap})."
        )
        return STOP, "iteration_cap_reached", "terminal", reasons

    reasons.append(
        f"Last recorded status is {last_status!r}; the loop remains resumable and should continue in a fresh Codex session."
    )
    return RELAUNCH, "none", "turn_complete", reasons


def evaluate_supervisor_status(
    *,
    results_path: Path,
    state_path_arg: str | None,
    max_stagnation: int,
    after_run: bool,
    write_state: bool,
) -> dict[str, Any]:
    repo_hint = results_path.parent if results_path.is_absolute() else None
    fallback_state_path = resolve_state_path_for_log(state_path_arg, None, cwd=repo_hint)
    try:
        parsed = parse_results_log(results_path)
        state_path = resolve_state_path_for_log(state_path_arg, parsed, cwd=repo_hint)
        payload = read_state_payload(state_path)
    except AutoresearchError as exc:
        message = str(exc)
        missing_artifacts = message.startswith("Missing results log:") or message.startswith(
            "Missing JSON file:"
        )
        if after_run and missing_artifacts:
            return {
                "decision": RELAUNCH,
                "reason": "missing_artifacts",
                "reasons": [
                    "Codex exited before initializing research-results.tsv / autoresearch-state.json."
                ],
                "results_path": str(results_path),
                "state_path": str(fallback_state_path),
                "mode": None,
                "iteration": None,
                "last_status": None,
                "restart_count": 1,
                "stagnation_count": 0,
                "supervisor_state_written": False,
            }
        raise

    direction = payload.get("config", {}).get("direction")
    if direction not in {"lower", "higher"}:
        raise AutoresearchError("State config.direction must be 'lower' or 'higher'.")

    reconstructed = log_summary(parsed, direction)
    mismatches = compare_summary_to_state(reconstructed, payload)

    observed_at = utc_now()
    previous_supervisor = payload.get("supervisor", {})
    if not isinstance(previous_supervisor, dict):
        previous_supervisor = {}

    signature = progress_signature(payload)
    previous_signature = previous_supervisor.get("last_observed_signature")
    same_signature = previous_signature == signature

    restart_count = as_int(previous_supervisor.get("restart_count"))
    if after_run:
        restart_count += 1

    previous_stagnation = as_int(previous_supervisor.get("stagnation_count"))
    if after_run and same_signature:
        stagnation_count = previous_stagnation + 1
    elif same_signature:
        stagnation_count = previous_stagnation
    else:
        stagnation_count = 0

    if mismatches:
        decision = NEEDS_HUMAN
        reason = "state_inconsistent"
        exit_kind = "state_inconsistent"
        reasons = [
            "Results log and JSON state diverged; unattended relaunch is unsafe.",
            *mismatches,
        ]
    else:
        decision, reason, exit_kind, reasons = determine_base_decision(
            payload, reconstructed["current_metric"]
        )

    if decision == RELAUNCH and stagnation_count >= max_stagnation:
        decision = NEEDS_HUMAN
        reason = "stagnated"
        exit_kind = "stagnated"
        reasons.append(
            f"No progress signature change across {stagnation_count} consecutive supervised exits."
        )

    if decision not in VALID_DECISIONS:
        raise AutoresearchError(f"Internal error: unsupported supervisor decision {decision!r}")

    supervisor = {
        "recommended_action": decision,
        "should_continue": decision == RELAUNCH,
        "terminal_reason": "none" if decision == RELAUNCH else reason,
        "last_exit_kind": exit_kind,
        "last_turn_finished_at": observed_at,
        "last_observed_signature": signature,
        "last_observed_iteration": payload["state"]["iteration"],
        "last_observed_status": payload["state"]["last_status"],
        "last_observed_updated_at": payload.get("updated_at"),
        "last_observed_metric": decimal_to_json_number(reconstructed["current_metric"]),
        "restart_count": restart_count,
        "stagnation_count": stagnation_count,
        "last_reason": reasons[0] if reasons else "",
    }

    if write_state:
        new_payload = dict(payload)
        new_payload["supervisor"] = supervisor
        write_json_atomic(state_path, new_payload)

    return {
        "decision": decision,
        "reason": reason,
        "reasons": reasons,
        "results_path": str(results_path),
        "state_path": str(state_path),
        "mode": payload.get("mode"),
        "iteration": payload["state"]["iteration"],
        "last_status": payload["state"]["last_status"],
        "restart_count": restart_count,
        "stagnation_count": stagnation_count,
        "supervisor_state_written": write_state,
    }


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.max_stagnation < 1:
        raise SystemExit("error: --max-stagnation must be at least 1")

    if args.repo is not None:
        repo = resolve_repo_path(args.repo)
        results_path = resolve_repo_relative(repo, args.results_path, repo / DEFAULT_RESULTS_PATH)
    else:
        results_path = Path(args.results_path or DEFAULT_RESULTS_PATH)

    output = evaluate_supervisor_status(
        results_path=results_path,
        state_path_arg=args.state_path,
        max_stagnation=args.max_stagnation,
        after_run=args.after_run,
        write_state=args.write_state,
    )
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutoresearchError as exc:
        raise SystemExit(f"error: {exc}")
