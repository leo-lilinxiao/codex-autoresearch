#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from autoresearch_helpers import (
    AutoresearchError,
    compare_summary_to_state,
    default_launch_manifest_path,
    default_runtime_state_path,
    log_summary,
    parse_results_log,
    read_launch_manifest,
    read_runtime_payload,
    read_state_payload,
    resolve_state_path_for_log,
)
from autoresearch_resume_check import missing_resume_config_fields


def pid_is_alive(pid: int | None) -> bool:
    if pid is None or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True
    except ProcessLookupError:
        return False
    return True


def evaluate_launch_context(
    *,
    results_path: Path,
    state_path_arg: str | None,
    launch_path: Path,
    runtime_path: Path,
    ignore_running_runtime: bool = False,
) -> dict[str, Any]:
    reasons: list[str] = []
    results_exists = results_path.exists()
    parsed = None
    repo_hint = results_path.parent
    if results_exists:
        parsed = parse_results_log(results_path)

    state_path = resolve_state_path_for_log(state_path_arg, parsed, cwd=repo_hint)
    state_exists = state_path.exists()

    launch_manifest = None
    launch_error = None
    if launch_path.exists():
        try:
            launch_manifest = read_launch_manifest(launch_path)
        except AutoresearchError as exc:
            launch_error = str(exc)
            reasons.append(launch_error)

    runtime_payload = None
    runtime_error = None
    if runtime_path.exists():
        try:
            runtime_payload = read_runtime_payload(runtime_path)
        except AutoresearchError as exc:
            runtime_error = str(exc)
            reasons.append(runtime_error)

    if (
        not ignore_running_runtime
        and runtime_payload is not None
        and pid_is_alive(runtime_payload.get("pid"))
    ):
        reasons.append("An autoresearch runtime is already active for this repo.")
        return {
            "decision": "blocked_start",
            "reason": "already_running",
            "resume_strategy": "runtime_active",
            "results_path": str(results_path),
            "state_path": str(state_path),
            "launch_path": str(launch_path),
            "runtime_path": str(runtime_path),
            "launch_manifest_present": launch_manifest is not None,
            "runtime_present": True,
            "runtime_running": True,
            "reasons": reasons,
        }

    if launch_error is not None:
        return {
            "decision": "needs_human",
            "reason": "invalid_launch_manifest",
            "resume_strategy": "none",
            "results_path": str(results_path),
            "state_path": str(state_path),
            "launch_path": str(launch_path),
            "runtime_path": str(runtime_path),
            "launch_manifest_present": False,
            "runtime_present": runtime_payload is not None or runtime_error is not None,
            "runtime_running": False,
            "reasons": reasons,
        }

    if not results_exists and not state_exists:
        strategy = "launch_manifest_ready" if launch_manifest is not None else "cold_start"
        reason = (
            "confirmed_launch_without_artifacts"
            if launch_manifest is not None
            else "fresh_start"
        )
        reasons.append(
            "Launch manifest is already confirmed; a fresh runtime can initialize artifacts."
            if launch_manifest is not None
            else "No prior run artifacts detected; a fresh interactive launch is required."
        )
        return {
            "decision": "fresh",
            "reason": reason,
            "resume_strategy": strategy,
            "results_path": str(results_path),
            "state_path": str(state_path),
            "launch_path": str(launch_path),
            "runtime_path": str(runtime_path),
            "launch_manifest_present": launch_manifest is not None,
            "runtime_present": runtime_payload is not None or runtime_error is not None,
            "runtime_running": False,
            "reasons": reasons,
        }

    if not results_exists and state_exists:
        reasons.append("State exists without a results log; a human should inspect or repair the run.")
        return {
            "decision": "needs_human",
            "reason": "state_without_results",
            "resume_strategy": "none",
            "results_path": str(results_path),
            "state_path": str(state_path),
            "launch_path": str(launch_path),
            "runtime_path": str(runtime_path),
            "launch_manifest_present": launch_manifest is not None,
            "runtime_present": runtime_payload is not None or runtime_error is not None,
            "runtime_running": False,
            "reasons": reasons,
        }

    if results_exists and not state_exists:
        reasons.append("Results log exists without state; runtime can still continue from TSV reconstruction.")
        return {
            "decision": "resumable",
            "reason": "results_without_state",
            "resume_strategy": "tsv_fallback",
            "results_path": str(results_path),
            "state_path": str(state_path),
            "launch_path": str(launch_path),
            "runtime_path": str(runtime_path),
            "launch_manifest_present": launch_manifest is not None,
            "runtime_present": runtime_payload is not None or runtime_error is not None,
            "runtime_running": False,
            "reasons": reasons,
        }

    payload = read_state_payload(state_path)
    config_missing = missing_resume_config_fields(payload.get("config"))
    if config_missing:
        reasons.append(
            "State config is missing required resume fields: " + ", ".join(config_missing)
        )
        return {
            "decision": "needs_human",
            "reason": "incomplete_state_config",
            "resume_strategy": "mini_resume",
            "results_path": str(results_path),
            "state_path": str(state_path),
            "launch_path": str(launch_path),
            "runtime_path": str(runtime_path),
            "launch_manifest_present": launch_manifest is not None,
            "runtime_present": runtime_payload is not None or runtime_error is not None,
            "runtime_running": False,
            "reasons": reasons,
        }

    direction = payload.get("config", {}).get("direction")
    if direction in {"lower", "higher"}:
        reconstructed = log_summary(parsed, direction)
        mismatches = compare_summary_to_state(reconstructed, payload)
        if mismatches:
            reasons.append(
                "JSON state and TSV results log are inconsistent: " + "; ".join(mismatches)
            )
            return {
                "decision": "needs_human",
                "reason": "state_tsv_diverged",
                "resume_strategy": "none",
                "results_path": str(results_path),
                "state_path": str(state_path),
                "launch_path": str(launch_path),
                "runtime_path": str(runtime_path),
                "launch_manifest_present": launch_manifest is not None,
                "runtime_present": runtime_payload is not None or runtime_error is not None,
                "runtime_running": False,
                "reasons": reasons,
            }

    reasons.append(
        "Results log and state are available; the runtime can continue from the saved config."
        if launch_manifest is not None
        else "Legacy results/state are resumable even without a launch manifest."
    )
    return {
        "decision": "resumable",
        "reason": "full_resume" if launch_manifest is not None else "legacy_resume",
        "resume_strategy": "full_resume" if launch_manifest is not None else "legacy_resume",
        "results_path": str(results_path),
        "state_path": str(state_path),
        "launch_path": str(launch_path),
        "runtime_path": str(runtime_path),
        "launch_manifest_present": launch_manifest is not None,
        "runtime_present": runtime_payload is not None or runtime_error is not None,
        "runtime_running": False,
        "reasons": reasons,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Decide whether autoresearch should fresh-start, resume, or escalate to a human."
    )
    parser.add_argument("--results-path", default="research-results.tsv")
    parser.add_argument("--state-path")
    parser.add_argument("--launch-path", default=str(default_launch_manifest_path()))
    parser.add_argument("--runtime-path", default=str(default_runtime_state_path()))
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    decision = evaluate_launch_context(
        results_path=Path(args.results_path),
        state_path_arg=args.state_path,
        launch_path=Path(args.launch_path),
        runtime_path=Path(args.runtime_path),
        ignore_running_runtime=False,
    )
    print(json.dumps(decision, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutoresearchError as exc:
        raise SystemExit(f"error: {exc}")
