#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from autoresearch_core import print_json
from autoresearch_helpers import (
    AutoresearchError,
    LAUNCH_MANIFEST_NAME,
    read_launch_manifest,
    read_runtime_payload,
    require_context_for_repo,
    resolve_context_workspace_root,
    resolve_repo_path,
    resolve_repo_relative,
    RUNTIME_STATE_NAME,
    STATE_FILE_NAME,
)
from autoresearch_platform import (
    inspect_process_identity as platform_inspect_process_identity,
    process_is_alive,
    process_is_zombie,
)
from autoresearch_resume_check import evaluate_resume_state
from autoresearch_workspace import default_workspace_artifacts, resolve_workspace_root


def pid_is_zombie(pid: int) -> bool:
    return process_is_zombie(pid)


def pid_is_alive(pid: int | None) -> bool:
    return process_is_alive(pid)


def inspect_process_identity(pid: int | None) -> dict[str, object] | None:
    return platform_inspect_process_identity(pid)


def normalize_command_text(value: str | None) -> str:
    return " ".join(str(value or "").split())


def expected_runtime_command_text(runtime_payload: dict[str, Any]) -> str:
    stored = runtime_payload.get("process_command")
    if isinstance(stored, str) and stored.strip():
        return normalize_command_text(stored)
    return ""


def runtime_identity_missing(runtime_payload: dict[str, Any]) -> str | None:
    started_at = runtime_payload.get("process_started_at")
    if not isinstance(started_at, str) or not started_at.strip():
        return "process_started_at"
    command = runtime_payload.get("process_command")
    if not isinstance(command, str) or not command.strip():
        return "process_command"
    return None


def runtime_process_state(runtime_payload: dict[str, Any]) -> dict[str, object]:
    pid = runtime_payload.get("pid")
    if not isinstance(pid, int) or pid <= 0:
        return {
            "alive": False,
            "matches": False,
            "reason": "missing_pid",
            "message": "Runtime state is missing a valid pid.",
        }
    if not pid_is_alive(pid):
        return {
            "alive": False,
            "matches": False,
            "reason": "not_running",
            "message": f"Runtime process {pid} is not running.",
        }

    current = inspect_process_identity(pid)
    if current is None:
        if not pid_is_alive(pid):
            return {
                "alive": False,
                "matches": False,
                "reason": "not_running",
                "message": f"Runtime process {pid} is not running.",
            }
        return {
            "alive": True,
            "matches": False,
            "reason": "inspection_failed",
            "message": f"Could not verify runtime process identity for pid {pid}.",
        }

    missing_identity_field = runtime_identity_missing(runtime_payload)
    if missing_identity_field is not None:
        return {
            "alive": True,
            "matches": False,
            "reason": "runtime_identity_unverifiable",
            "message": (
                f"Runtime pid {pid} is alive, but runtime.json is missing "
                f"{missing_identity_field}; stop it manually or start fresh."
            ),
        }

    expected_started_at = runtime_payload.get("process_started_at")
    if isinstance(expected_started_at, str) and expected_started_at.strip():
        if current["started_at"] != expected_started_at:
            return {
                "alive": True,
                "matches": False,
                "reason": "identity_mismatch",
                "message": (
                    f"Runtime pid {pid} is alive, but start time changed "
                    f"({expected_started_at} != {current['started_at']})."
                ),
            }

    expected_command = expected_runtime_command_text(runtime_payload)
    if expected_command and normalize_command_text(str(current["command"])) != expected_command:
        return {
            "alive": True,
            "matches": False,
            "reason": "identity_mismatch",
            "message": (
                f"Runtime pid {pid} is alive, but command no longer matches "
                "the recorded runtime process."
            ),
        }

    expected_pgid = runtime_payload.get("pgid")
    if isinstance(expected_pgid, int) and expected_pgid > 0 and current["pgid"] != expected_pgid:
        return {
            "alive": True,
            "matches": False,
            "reason": "identity_mismatch",
            "message": (
                f"Runtime pid {pid} is alive, but process group changed "
                f"({expected_pgid} != {current['pgid']})."
            ),
        }

    return {
        "alive": True,
        "matches": True,
        "reason": "running",
        "message": "",
        "current": current,
    }


def evaluate_launch_context(
    *,
    results_path: Path,
    state_path_arg: str | None,
    launch_path: Path,
    runtime_path: Path,
    default_state_path: Path | None = None,
    ignore_running_runtime: bool = False,
) -> dict[str, Any]:
    reasons: list[str] = []
    resume = evaluate_resume_state(
        results_path=results_path,
        state_path_arg=state_path_arg,
        default_state_path=default_state_path,
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

    runtime_state = runtime_process_state(runtime_payload) if runtime_payload is not None else None
    if (
        runtime_payload is not None
        and runtime_state is not None
        and bool(runtime_state["alive"])
        and not bool(runtime_state["matches"])
    ):
        reasons.append(str(runtime_state["message"]))
        return {
            "decision": "needs_human",
            "reason": "runtime_identity_mismatch",
            "resume_strategy": "none",
            "results_path": str(results_path),
            "state_path": str(state_path),
            "launch_path": str(launch_path),
            "runtime_path": str(runtime_path),
            "launch_manifest_present": launch_manifest is not None,
            "runtime_present": True,
            "runtime_running": True,
            "reasons": reasons,
        }

    if (
        not ignore_running_runtime
        and runtime_payload is not None
        and runtime_state is not None
        and bool(runtime_state["alive"])
        and bool(runtime_state["matches"])
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
                "Runs that predate launch.json are not resumable under the managed runtime. Start fresh through the interactive launch flow."
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
    parser.add_argument(
        "--repo",
        required=True,
        help="Primary repo root. Run context is resolved from this repo's git-local pointer.",
    )
    parser.add_argument("--workspace-root")
    parser.add_argument(
        "--results-path",
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--state-path", help=argparse.SUPPRESS)
    parser.add_argument("--launch-path", help=argparse.SUPPRESS)
    parser.add_argument("--runtime-path", help=argparse.SUPPRESS)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    repo = resolve_repo_path(args.repo)
    if args.results_path is not None:
        workspace_root = (
            resolve_workspace_root(repo, args.workspace_root)
            if args.workspace_root is not None
            else Path.cwd().resolve()
        )
        results_path = resolve_repo_relative(workspace_root, args.results_path, Path(args.results_path))
        artifact_root = results_path.parent
        state_default = artifact_root / STATE_FILE_NAME
        launch_path = resolve_repo_relative(
            workspace_root,
            args.launch_path,
            artifact_root / LAUNCH_MANIFEST_NAME,
        )
        runtime_path = resolve_repo_relative(
            workspace_root,
            args.runtime_path,
            artifact_root / RUNTIME_STATE_NAME,
        )
    else:
        context = require_context_for_repo(repo)
        workspace_root = resolve_context_workspace_root(
            repo=repo,
            context=context,
            raw_workspace_root=args.workspace_root,
        )
        defaults = default_workspace_artifacts(context.workspace_root)
        state_default = context.state_path
        launch_path = resolve_repo_relative(
            workspace_root,
            args.launch_path,
            context.launch_path or defaults.launch_path,
        )
        runtime_path = resolve_repo_relative(
            workspace_root,
            args.runtime_path,
            context.runtime_path or defaults.runtime_path,
        )
        results_path = context.results_path
    decision = evaluate_launch_context(
        results_path=results_path,
        state_path_arg=args.state_path,
        default_state_path=state_default,
        launch_path=launch_path,
        runtime_path=runtime_path,
        ignore_running_runtime=False,
    )
    print_json(decision)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutoresearchError as exc:
        raise SystemExit(f"error: {exc}")
