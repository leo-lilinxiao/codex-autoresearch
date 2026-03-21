#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from autoresearch_helpers import (
    AutoresearchError,
    read_launch_manifest,
    read_runtime_payload,
    resolve_repo_managed_path,
)
from autoresearch_resume_check import evaluate_resume_state


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
    resume = evaluate_resume_state(
        results_path=results_path,
        state_path_arg=state_path_arg,
        write_repaired_state=False,
    )
    state_path = Path(str(resume["state_path"]))
    results_exists = bool(resume["has_results"])
    state_exists = bool(resume["has_state"])

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

    if runtime_error is not None:
        return {
            "decision": "needs_human",
            "reason": "invalid_runtime_state",
            "resume_strategy": "none",
            "results_path": str(results_path),
            "state_path": str(state_path),
            "launch_path": str(launch_path),
            "runtime_path": str(runtime_path),
            "launch_manifest_present": launch_manifest is not None,
            "runtime_present": True,
            "runtime_running": False,
            "reasons": reasons,
        }

    if resume["decision"] == "fresh_start":
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

    if resume["decision"] == "mini_wizard" and resume["detail"] == "state_without_results":
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

    if resume["decision"] == "full_resume":
        reasons.extend(str(reason) for reason in resume["reasons"])
        if launch_manifest is None:
            reasons.append(
                "Runs that predate autoresearch-launch.json are not resumable under the managed runtime. Start fresh through the interactive launch flow."
            )
            return {
                "decision": "needs_human",
                "reason": "fresh_start_required",
                "resume_strategy": "fresh_start",
                "results_path": str(results_path),
                "state_path": str(state_path),
                "launch_path": str(launch_path),
                "runtime_path": str(runtime_path),
                "launch_manifest_present": False,
                "runtime_present": runtime_payload is not None or runtime_error is not None,
                "runtime_running": False,
                "reasons": reasons,
            }
        reasons.append(
            "Results log and state are available; the runtime can continue from the saved config."
        )
        return {
            "decision": "resumable",
            "reason": "full_resume",
            "resume_strategy": "full_resume",
            "results_path": str(results_path),
            "state_path": str(state_path),
            "launch_path": str(launch_path),
            "runtime_path": str(runtime_path),
            "launch_manifest_present": True,
            "runtime_present": runtime_payload is not None or runtime_error is not None,
            "runtime_running": False,
            "reasons": reasons,
        }

    if resume["decision"] == "tsv_fallback":
        reasons.extend(str(reason) for reason in resume["reasons"])
        if launch_manifest is None:
            reasons.append(
                "TSV reconstruction is available, but a detached runtime still needs a confirmed launch manifest."
            )
            return {
                "decision": "needs_human",
                "reason": "launch_manifest_required",
                "resume_strategy": "mini_resume",
                "results_path": str(results_path),
                "state_path": str(state_path),
                "launch_path": str(launch_path),
                "runtime_path": str(runtime_path),
                "launch_manifest_present": False,
                "runtime_present": runtime_payload is not None or runtime_error is not None,
                "runtime_running": False,
                "reasons": reasons,
            }
        reasons.append("Results log exists without a trustworthy JSON state; runtime can continue from TSV reconstruction.")
        return {
            "decision": "resumable",
            "reason": "results_without_state" if not state_exists else "tsv_fallback",
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

    reasons.extend(str(reason) for reason in resume["reasons"])
    reason_map = {
        "state_tsv_diverged": ("state_tsv_diverged", "none"),
        "invalid_state_json": ("incomplete_state_config", "mini_resume"),
        "state_without_reconstructable_tsv": ("resume_confirmation_required", "mini_resume"),
    }
    reason, resume_strategy = reason_map.get(
        str(resume["detail"]),
        ("resume_confirmation_required", "mini_resume"),
    )
    return {
        "decision": "needs_human",
        "reason": reason,
        "resume_strategy": resume_strategy,
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
    parser.add_argument("--launch-path")
    parser.add_argument("--runtime-path")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    results_path = Path(args.results_path)
    decision = evaluate_launch_context(
        results_path=results_path,
        state_path_arg=args.state_path,
        launch_path=resolve_repo_managed_path(
            args.launch_path,
            results_path=results_path,
            default_name="autoresearch-launch.json",
        ),
        runtime_path=resolve_repo_managed_path(
            args.runtime_path,
            results_path=results_path,
            default_name="autoresearch-runtime.json",
        ),
        ignore_running_runtime=False,
    )
    print(json.dumps(decision, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutoresearchError as exc:
        raise SystemExit(f"error: {exc}")
