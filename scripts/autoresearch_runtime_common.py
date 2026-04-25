#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from autoresearch_helpers import (
    ARTIFACT_DIR_NAME,
    AutoresearchError,
    RESULTS_FILE_NAME,
    build_repo_targets,
    default_state_path,
    normalize_criteria_config,
    normalize_labels,
    read_state_payload,
    read_runtime_payload,
    resolve_repo_path,
    resolve_repo_relative,
    resolve_state_path,
    serialize_repo_targets,
    utc_now,
    workspace_artifact_root,
    write_json_atomic,
)
from autoresearch_workspace import resolve_workspace_root
from autoresearch_launch_gate import runtime_process_state
from autoresearch_lessons import append_summary_lesson_if_needed, lessons_path_from_results


DEFAULT_RESULTS_PATH = f"{ARTIFACT_DIR_NAME}/{RESULTS_FILE_NAME}"
DEFAULT_EXECUTION_POLICY = "danger_full_access"
EXECUTION_POLICY_CHOICES = ("workspace_write", "danger_full_access")
DEFAULT_VERIFY_CWD = "workspace_root"
VERIFY_CWD_CHOICES = ("workspace_root", "primary_repo")
VERIFY_FORMAT_CHOICES = ("scalar", "metrics_json")
DEFAULT_HEALTH_MIN_FREE_MB = 500


def parse_key_value_pairs(values: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise AutoresearchError(f"Expected KEY=VALUE, got: {value!r}")
        key, raw_value = value.split("=", 1)
        key = key.strip()
        if not key:
            raise AutoresearchError(f"Invalid empty key in: {value!r}")
        parsed[key] = raw_value.strip()
    return parsed


def parse_optional_json_argument(raw: str | None, *, field_name: str) -> Any:
    if raw in (None, ""):
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AutoresearchError(f"Invalid JSON for {field_name}: {exc}") from exc


def load_runtime_if_exists(runtime_path: Path) -> dict[str, Any] | None:
    if not runtime_path.exists():
        return None
    return read_runtime_payload(runtime_path)


def load_runtime_with_error(runtime_path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not runtime_path.exists():
        return None, None
    try:
        return read_runtime_payload(runtime_path), None
    except AutoresearchError as exc:
        return None, str(exc)


def ensure_runtime_not_running(runtime_path: Path) -> None:
    existing, runtime_error = load_runtime_with_error(runtime_path)
    if runtime_error is not None:
        raise AutoresearchError(runtime_error)
    if existing is None:
        return
    runtime_state = runtime_process_state(existing)
    if bool(runtime_state["alive"]) and bool(runtime_state["matches"]):
        raise AutoresearchError("An autoresearch runtime is already running for this repo.")
    if bool(runtime_state["alive"]) and not bool(runtime_state["matches"]):
        raise AutoresearchError(str(runtime_state["message"]))


def persist_runtime(runtime_path: Path, payload: dict[str, Any]) -> None:
    payload = dict(payload)
    payload["updated_at"] = utc_now()
    write_json_atomic(runtime_path, payload)


def append_completion_summary_if_possible(
    *,
    results_path: Path,
    state_path: Path,
) -> None:
    if not results_path.exists() or not state_path.exists():
        return
    try:
        state_payload = read_state_payload(state_path)
        append_summary_lesson_if_needed(
            lessons_path=lessons_path_from_results(results_path),
            state_payload=state_payload,
            current_iteration=int(state_payload.get("state", {}).get("iteration", 0)),
        )
    except (AutoresearchError, OSError, ValueError, TypeError):
        return


def manifest_config_from_args(args: argparse.Namespace) -> dict[str, Any]:
    primary_repo = resolve_repo_path(args.repo)
    workspace_root = resolve_workspace_root(primary_repo, getattr(args, "workspace_root", None))
    repo_targets = build_repo_targets(
        primary_repo=primary_repo,
        primary_scope=args.scope,
        companion_repo_scopes=getattr(args, "companion_repo_scope", []),
    )
    verify_format = getattr(args, "verify_format", "scalar")
    primary_metric_key = getattr(args, "primary_metric_key", None) or args.metric_name
    config = {
        "session_mode": "background",
        "workspace_root": str(workspace_root),
        "artifact_root": str(workspace_artifact_root(workspace_root)),
        "primary_repo": str(primary_repo),
        "goal": args.goal,
        "scope": repo_targets[0].scope,
        "repos": serialize_repo_targets(repo_targets),
        "execution_policy": getattr(args, "execution_policy", DEFAULT_EXECUTION_POLICY),
        "metric": args.metric_name,
        "direction": args.direction,
        "verify": args.verify,
        "verify_cwd": getattr(args, "verify_cwd", DEFAULT_VERIFY_CWD),
        "verify_format": verify_format,
        "primary_metric_key": primary_metric_key,
        "guard": args.guard,
        "iterations": args.iterations,
        "run_tag": args.run_tag,
        "stop_condition": args.stop_condition,
        "rollback_policy": args.rollback_policy,
        "parallel_mode": args.parallel_mode,
        "web_search": args.web_search,
    }
    acceptance_criteria = normalize_criteria_config(
        parse_optional_json_argument(
            getattr(args, "acceptance_criteria", None),
            field_name="acceptance_criteria",
        ),
        field_name="acceptance_criteria",
    )
    if acceptance_criteria:
        config["acceptance_criteria"] = acceptance_criteria
    required_keep_criteria = normalize_criteria_config(
        parse_optional_json_argument(
            getattr(args, "required_keep_criteria", None),
            field_name="required_keep_criteria",
        ),
        field_name="required_keep_criteria",
    )
    if required_keep_criteria:
        config["required_keep_criteria"] = required_keep_criteria
    required_stop_labels = normalize_labels(getattr(args, "required_stop_label", []))
    if required_stop_labels:
        config["required_stop_labels"] = required_stop_labels
    required_keep_labels = normalize_labels(getattr(args, "required_keep_label", []))
    if required_keep_labels:
        config["required_keep_labels"] = required_keep_labels
    return config


def codex_args_for_execution_policy(
    execution_policy: str | None,
    *,
    extra_args: list[str] | None = None,
) -> list[str]:
    policy = execution_policy or DEFAULT_EXECUTION_POLICY
    if policy not in EXECUTION_POLICY_CHOICES:
        raise AutoresearchError(
            f"Unsupported execution policy: {policy!r}. "
            f"Expected one of: {', '.join(EXECUTION_POLICY_CHOICES)}"
        )

    extras = list(extra_args or [])
    conflicting_flags = {
        "--full-auto",
        "--dangerously-bypass-approvals-and-sandbox",
        "--yolo",
    }
    for value in extras:
        if value in conflicting_flags:
            raise AutoresearchError(
                "Execution policy is configured separately; do not pass sandbox-selection "
                f"flags through --codex-arg ({value!r})."
            )

    if policy == "workspace_write":
        return ["--full-auto", *extras]
    return ["--dangerously-bypass-approvals-and-sandbox", *extras]


def destructive_rollback_approved(launch_manifest: dict[str, Any]) -> bool:
    approvals = launch_manifest.get("approvals", {})
    if not isinstance(approvals, dict):
        return False
    for key in ("destructive_rollback", "rollback", "destructive"):
        value = approvals.get(key)
        if value in {True, "true", "yes", "approved", "allow"}:
            return True
    return False
