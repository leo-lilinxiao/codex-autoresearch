#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import os
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any

from autoresearch_acceptance import normalize_criteria_config
from autoresearch_core import (
    HEADER,
    MAIN_STATUSES,
    WORKER_LABEL_RE,
    AutoresearchError,
    LogRow,
    ParsedLog,
    decimal_to_json_number,
    format_description_with_labels,
    format_decimal,
    format_delta,
    improvement,
    normalize_labels,
    parse_decimal,
    split_labels_from_description,
    utc_now,
    REQUIRED_STATE_FIELDS,
)


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AutoresearchError(f"Missing JSON file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise AutoresearchError(f"Invalid JSON in {path}: {exc}") from exc


def read_state_payload(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    if not isinstance(payload, dict):
        raise AutoresearchError(f"Invalid state JSON in {path}: expected an object")
    if "version" not in payload:
        raise AutoresearchError(f"Invalid state JSON in {path}: missing version")

    config = payload.get("config")
    if not isinstance(config, dict):
        raise AutoresearchError(f"Invalid state JSON in {path}: config must be an object")

    state = payload.get("state")
    if not isinstance(state, dict):
        raise AutoresearchError(f"Invalid state JSON in {path}: state must be an object")

    missing_fields = sorted(REQUIRED_STATE_FIELDS - state.keys())
    if missing_fields:
        raise AutoresearchError(
            f"Invalid state JSON in {path}: missing state fields: {', '.join(missing_fields)}"
        )
    return payload


def read_launch_manifest(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    if not isinstance(payload, dict):
        raise AutoresearchError(f"Invalid launch manifest in {path}: expected an object")
    if payload.get("version") != 1:
        raise AutoresearchError(f"Invalid launch manifest in {path}: unsupported version")
    if not isinstance(payload.get("original_goal"), str) or not payload["original_goal"].strip():
        raise AutoresearchError(f"Invalid launch manifest in {path}: missing original_goal")
    if not isinstance(payload.get("config"), dict):
        raise AutoresearchError(f"Invalid launch manifest in {path}: config must be an object")
    return payload


def read_runtime_payload(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    if not isinstance(payload, dict):
        raise AutoresearchError(f"Invalid runtime state in {path}: expected an object")
    if payload.get("version") != 1:
        raise AutoresearchError(f"Invalid runtime state in {path}: unsupported version")
    return payload


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f"{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, sort_keys=True)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, str(path))
    except BaseException:
        os.unlink(tmp_name)
        raise


def parse_metadata_comment(line: str) -> tuple[str, str] | None:
    if not line.startswith("#"):
        return None
    content = line[1:].strip()
    if ":" not in content:
        return None
    key, value = content.split(":", 1)
    key = key.strip()
    if not key:
        return None
    return key, value.strip()


def parse_log_metadata(path: Path) -> dict[str, str]:
    metadata: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return metadata
    for line in text.splitlines():
        if not line.startswith("#"):
            continue
        parsed = parse_metadata_comment(line)
        if parsed is not None:
            metadata[parsed[0]] = parsed[1]
    return metadata


def parse_results_log(path: Path) -> ParsedLog:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as exc:
        raise AutoresearchError(f"Missing results log: {path}") from exc

    comments: list[str] = []
    metadata: dict[str, str] = {}
    data_lines: list[tuple[int, str]] = []

    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        if line.startswith("#"):
            comments.append(line)
            parsed = parse_metadata_comment(line)
            if parsed is not None:
                key, value = parsed
                metadata[key] = value
            continue
        data_lines.append((line_number, line))

    if not data_lines:
        raise AutoresearchError(f"Results log has no header: {path}")

    header_line_number, header_line = data_lines[0]
    header = next(csv.reader([header_line], delimiter="\t"))
    if header != HEADER:
        raise AutoresearchError(
            f"Unexpected TSV header in {path}:{header_line_number}: {header!r}"
        )

    rows: list[LogRow] = []
    for line_number, line in data_lines[1:]:
        columns = next(csv.reader([line], delimiter="\t"))
        if len(columns) != len(HEADER):
            raise AutoresearchError(
                f"Unexpected column count in {path}:{line_number}: expected {len(HEADER)}, got {len(columns)}"
            )
        rows.append(
            LogRow(
                iteration=columns[0],
                commit=columns[1],
                metric=parse_decimal(columns[2], "metric"),
                delta=columns[3],
                guard=columns[4],
                status=columns[5],
                description=columns[6],
                line_number=line_number,
                labels=tuple(split_labels_from_description(columns[6])[0]),
            )
        )

    if not rows:
        raise AutoresearchError(f"Results log has no data rows: {path}")
    return ParsedLog(comments=comments, metadata=metadata, rows=rows)


def write_results_log(path: Path, comments: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    parts: list[str] = []
    parts.extend(comment.rstrip("\n") for comment in comments)
    parts.append("\t".join(HEADER))
    for row in rows:
        parts.append(
            "\t".join(
                [
                    row["iteration"],
                    row["commit"],
                    row["metric"],
                    row["delta"],
                    row["guard"],
                    row["status"],
                    row["description"],
                ]
            )
        )
    content = "\n".join(parts) + "\n"
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f"{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, str(path))
    except BaseException:
        os.unlink(tmp_name)
        raise


def append_rows(path: Path, new_rows: list[dict[str, str]]) -> ParsedLog:
    parsed = parse_results_log(path)
    existing_rows = [row_to_dict(row) for row in parsed.rows]
    write_results_log(path, parsed.comments, existing_rows + new_rows)
    return parse_results_log(path)


def row_to_dict(row: LogRow) -> dict[str, str]:
    return {
        "iteration": row.iteration,
        "commit": row.commit,
        "metric": format_decimal(row.metric),
        "delta": row.delta,
        "guard": row.guard,
        "status": row.status,
        "description": row.description,
    }


def log_summary(parsed: ParsedLog, direction: str) -> dict[str, Any]:
    main_rows = parsed.main_rows
    if not main_rows:
        raise AutoresearchError("Results log has no main iteration rows.")

    baseline = main_rows[0]
    if baseline.main_iteration != 0 or baseline.status != "baseline":
        raise AutoresearchError("Results log must begin with baseline row 0.")

    summary = {
        "iteration": 0,
        "baseline_metric": baseline.metric,
        "best_metric": baseline.metric,
        "best_iteration": 0,
        "current_metric": baseline.metric,
        "last_commit": baseline.commit,
        "last_trial_commit": baseline.commit,
        "last_trial_metric": baseline.metric,
        "current_labels": list(baseline.labels),
        "last_trial_labels": list(baseline.labels),
        "keeps": 0,
        "discards": 0,
        "crashes": 0,
        "no_ops": 0,
        "blocked": 0,
        "consecutive_discards": 0,
        "pivot_count": 0,
        "last_status": "baseline",
        "worker_rows": 0,
        "main_rows": 1,
    }
    for row in parsed.rows[1:]:
        if row.worker_parent_iteration is not None:
            summary["worker_rows"] += 1
            continue

        main_iteration = row.main_iteration
        if main_iteration is None:
            continue
        expected_iteration = summary["iteration"] + 1
        if main_iteration != expected_iteration:
            raise AutoresearchError(
                f"Missing or out-of-order main iteration row before line {row.line_number}: "
                f"expected {expected_iteration}, got {main_iteration}"
            )
        summary["iteration"] = main_iteration
        summary["main_rows"] += 1
        summary["last_status"] = row.status
        summary["last_trial_commit"] = row.commit
        summary["last_trial_metric"] = row.metric
        summary["last_trial_labels"] = list(row.labels)

        if row.status == "keep":
            summary["keeps"] += 1
            summary["current_metric"] = row.metric
            summary["last_commit"] = row.commit
            summary["current_labels"] = list(row.labels)
            summary["consecutive_discards"] = 0
            summary["pivot_count"] = 0
            if improvement(row.metric, summary["best_metric"], direction):
                summary["best_metric"] = row.metric
                summary["best_iteration"] = main_iteration
        elif row.status == "discard":
            summary["discards"] += 1
            summary["consecutive_discards"] += 1
        elif row.status == "crash":
            summary["crashes"] += 1
            summary["consecutive_discards"] += 1
        elif row.status == "no-op":
            summary["no_ops"] += 1
            summary["consecutive_discards"] += 1
        elif row.status == "refine":
            summary["consecutive_discards"] += 1
        elif row.status == "blocked":
            summary["blocked"] += 1
        elif row.status == "drift":
            summary["current_metric"] = row.metric
            if row.commit != "-":
                summary["last_commit"] = row.commit
            summary["consecutive_discards"] = 0
            if row.labels:
                summary["current_labels"] = list(row.labels)
            if improvement(row.metric, summary["best_metric"], direction):
                summary["best_metric"] = row.metric
                summary["best_iteration"] = main_iteration
        elif row.status == "pivot":
            summary["pivot_count"] += 1
        elif row.status == "search":
            pass
        else:
            raise AutoresearchError(
                f"Unsupported status {row.status!r} in results log line {row.line_number}"
            )

    return summary


def compare_summary_to_state(
    reconstructed: dict[str, Any],
    state_payload: dict[str, Any],
    *,
    tolerance: Any = parse_decimal("0.001", "tolerance"),
) -> list[str]:
    state = state_payload.get("state", {})
    mismatches: list[str] = []

    def compare_decimal_field(field_name: str) -> None:
        if field_name not in state:
            return
        expected = reconstructed[field_name]
        actual = parse_decimal(state[field_name], field_name)
        if abs(expected - actual) > tolerance:
            mismatches.append(
                f"{field_name}: state={format_decimal(actual)} tsv={format_decimal(expected)}"
            )

    def compare_scalar_field(field_name: str) -> None:
        if field_name not in state:
            return
        if state[field_name] != reconstructed[field_name]:
            mismatches.append(
                f"{field_name}: state={state[field_name]!r} tsv={reconstructed[field_name]!r}"
            )

    compare_scalar_field("iteration")
    compare_decimal_field("baseline_metric")
    compare_decimal_field("best_metric")
    compare_scalar_field("best_iteration")
    compare_decimal_field("current_metric")
    compare_scalar_field("last_commit")
    compare_scalar_field("last_trial_commit")
    compare_decimal_field("last_trial_metric")
    compare_scalar_field("keeps")
    compare_scalar_field("discards")
    compare_scalar_field("crashes")
    compare_scalar_field("no_ops")
    compare_scalar_field("blocked")
    compare_scalar_field("consecutive_discards")
    compare_scalar_field("pivot_count")
    compare_scalar_field("last_status")
    if "current_labels" in state:
        if normalize_labels(state["current_labels"]) != reconstructed.get("current_labels", []):
            mismatches.append(
                f"current_labels: state={normalize_labels(state['current_labels'])!r} "
                f"tsv={reconstructed.get('current_labels', [])!r}"
            )
    if "last_trial_labels" in state:
        if normalize_labels(state["last_trial_labels"]) != reconstructed.get("last_trial_labels", []):
            mismatches.append(
                f"last_trial_labels: state={normalize_labels(state['last_trial_labels'])!r} "
                f"tsv={reconstructed.get('last_trial_labels', [])!r}"
            )
    return mismatches


def config_from_results_metadata(metadata: dict[str, str]) -> dict[str, Any]:
    config: dict[str, Any] = {}

    direction = metadata.get("metric_direction")
    if direction in {"lower", "higher"}:
        config["direction"] = direction

    field_map = {
        "workspace_root": "workspace_root",
        "artifact_root": "artifact_root",
        "primary_repo": "primary_repo",
        "goal": "goal",
        "scope": "scope",
        "metric": "metric",
        "verify": "verify",
        "verify_cwd": "verify_cwd",
        "verify_format": "verify_format",
        "primary_metric_key": "primary_metric_key",
        "guard": "guard",
        "parallel": "parallel_mode",
        "web_search": "web_search",
        "stop_condition": "stop_condition",
        "rollback_policy": "rollback_policy",
        "execution_policy": "execution_policy",
    }
    for metadata_key, config_key in field_map.items():
        value = metadata.get(metadata_key)
        if value is not None and value != "":
            config[config_key] = value

    repos_json = metadata.get("repos_json")
    if repos_json is not None:
        config["repos"] = parse_results_metadata_repos(
            repos_json,
            metadata_key="repos_json",
        )

    iterations_text = metadata.get("iterations")
    if iterations_text is not None and iterations_text.strip():
        try:
            config["iterations"] = int(iterations_text.strip())
        except ValueError:
            pass

    required_stop_labels = normalize_labels(metadata.get("required_stop_labels"))
    if required_stop_labels:
        config["required_stop_labels"] = required_stop_labels

    required_keep_labels = normalize_labels(metadata.get("required_keep_labels"))
    if required_keep_labels:
        config["required_keep_labels"] = required_keep_labels

    acceptance_json = metadata.get("acceptance_criteria_json")
    if acceptance_json:
        config["acceptance_criteria"] = parse_results_metadata_criteria(
            acceptance_json,
            metadata_key="acceptance_criteria_json",
            field_name="acceptance_criteria",
        )

    required_keep_json = metadata.get("required_keep_criteria_json")
    if required_keep_json:
        config["required_keep_criteria"] = parse_results_metadata_criteria(
            required_keep_json,
            metadata_key="required_keep_criteria_json",
            field_name="required_keep_criteria",
        )

    return config


def parse_results_metadata_criteria(
    raw: str,
    *,
    metadata_key: str,
    field_name: str,
) -> list[dict[str, Any]]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AutoresearchError(f"Malformed {metadata_key} in results metadata: {exc}") from exc
    try:
        return normalize_criteria_config(parsed, field_name=field_name)
    except AutoresearchError as exc:
        raise AutoresearchError(f"Malformed {metadata_key} in results metadata: {exc}") from exc


def parse_results_metadata_repos(
    raw: str,
    *,
    metadata_key: str,
) -> list[dict[str, str]]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AutoresearchError(f"Malformed {metadata_key} in results metadata: {exc}") from exc
    if not isinstance(parsed, list) or not parsed:
        raise AutoresearchError(
            f"Malformed {metadata_key} in results metadata: expected a non-empty JSON list."
        )

    normalized: list[dict[str, str]] = []
    primary_count = 0
    for index, entry in enumerate(parsed):
        if not isinstance(entry, dict):
            raise AutoresearchError(
                f"Malformed {metadata_key} in results metadata: entry {index} must be an object."
            )
        path = entry.get("path")
        scope = entry.get("scope")
        role = entry.get("role")
        if not isinstance(path, str) or not path.strip():
            raise AutoresearchError(
                f"Malformed {metadata_key} in results metadata: entry {index}.path must be a non-empty string."
            )
        if not isinstance(scope, str) or not scope.strip():
            raise AutoresearchError(
                f"Malformed {metadata_key} in results metadata: entry {index}.scope must be a non-empty string."
            )
        if role not in {"primary", "companion"}:
            raise AutoresearchError(
                "Malformed "
                f"{metadata_key} in results metadata: entry {index}.role must be 'primary' or 'companion'."
            )
        if role == "primary":
            primary_count += 1
        normalized.append(
            {
                "path": path.strip(),
                "scope": scope.strip(),
                "role": role,
            }
        )

    if primary_count != 1:
        raise AutoresearchError(
            f"Malformed {metadata_key} in results metadata: expected exactly one primary repo."
        )
    return normalized


def build_state_payload(
    *,
    mode: str,
    run_tag: str | None,
    config: dict[str, Any],
    summary: dict[str, Any],
    supervisor: dict[str, Any] | None = None,
) -> dict[str, Any]:
    session_mode = config.get("session_mode")
    payload = {
        "version": 1,
        "run_tag": run_tag or "",
        "mode": mode,
        "config": config,
        "state": {
            "iteration": summary["iteration"],
            "baseline_metric": decimal_to_json_number(summary["baseline_metric"]),
            "best_metric": decimal_to_json_number(summary["best_metric"]),
            "best_iteration": summary["best_iteration"],
            "current_metric": decimal_to_json_number(summary["current_metric"]),
            "last_commit": summary["last_commit"],
            "last_trial_commit": summary["last_trial_commit"],
            "last_trial_metric": decimal_to_json_number(summary["last_trial_metric"]),
            "current_labels": list(summary.get("current_labels", [])),
            "last_trial_labels": list(summary.get("last_trial_labels", [])),
            "keeps": summary["keeps"],
            "discards": summary["discards"],
            "crashes": summary["crashes"],
            "no_ops": summary["no_ops"],
            "blocked": summary["blocked"],
            "consecutive_discards": summary["consecutive_discards"],
            "pivot_count": summary["pivot_count"],
            "last_status": summary["last_status"],
        },
        "updated_at": utc_now(),
    }
    current_metrics = summary.get("current_metrics")
    if isinstance(current_metrics, dict) and current_metrics:
        payload["state"]["current_metrics"] = deepcopy(current_metrics)
    last_trial_metrics = summary.get("last_trial_metrics")
    if isinstance(last_trial_metrics, dict) and last_trial_metrics:
        payload["state"]["last_trial_metrics"] = deepcopy(last_trial_metrics)
    for field_name in (
        "current_acceptance",
        "last_trial_acceptance",
        "current_required_keep_satisfied",
        "last_trial_required_keep_satisfied",
    ):
        if field_name in summary:
            payload["state"][field_name] = bool(summary[field_name])
    last_repo_commits = summary.get("last_repo_commits")
    if isinstance(last_repo_commits, dict) and last_repo_commits:
        payload["state"]["last_repo_commits"] = deepcopy(last_repo_commits)
    last_trial_repo_commits = summary.get("last_trial_repo_commits")
    if isinstance(last_trial_repo_commits, dict) and last_trial_repo_commits:
        payload["state"]["last_trial_repo_commits"] = deepcopy(last_trial_repo_commits)
    if supervisor is not None:
        payload["supervisor"] = deepcopy(supervisor)
    return payload


def rebuild_exec_state_payload_from_results(
    *,
    results_path: Path,
    state_path: Path,
    parsed: ParsedLog | None = None,
) -> dict[str, Any]:
    parsed = parsed or parse_results_log(results_path)
    if parsed.metadata.get("mode") != "exec":
        raise AutoresearchError(
            "Cannot rebuild scratch state from a non-exec results log."
        )

    config = config_from_results_metadata(parsed.metadata)
    direction = config.get("direction")
    if direction not in {"lower", "higher"}:
        raise AutoresearchError(
            "Exec results log is missing metric_direction metadata needed to rebuild scratch state."
        )

    summary = log_summary(parsed, direction)
    payload = build_state_payload(
        mode="exec",
        run_tag=parsed.metadata.get("run_tag") or "",
        config=config,
        summary=summary,
    )
    write_json_atomic(state_path, payload)
    return payload


def build_launch_manifest(
    *,
    original_goal: str,
    config: dict[str, Any],
    mode: str = "loop",
    approvals: dict[str, Any] | None = None,
    defaults: dict[str, Any] | None = None,
    resume_seed: dict[str, Any] | None = None,
    prompt_text: str | None = None,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "version": 1,
        "mode": mode,
        "original_goal": original_goal,
        "prompt_text": prompt_text or "",
        "config": deepcopy(config),
        "approvals": deepcopy(approvals or {}),
        "defaults": deepcopy(defaults or {}),
        "resume_seed": deepcopy(resume_seed or {}),
        "notes": list(notes or []),
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }


def build_runtime_payload(
    *,
    repo: Path,
    launch_path: Path,
    results_path: Path,
    state_path: Path,
    log_path: Path,
    status: str,
    pid: int | None = None,
    pgid: int | None = None,
    terminal_reason: str = "none",
    command: list[str] | None = None,
    process_started_at: str | None = None,
    process_command: str | None = None,
    requested_stop_at: str | None = None,
    last_decision: str | None = None,
    last_reason: str | None = None,
    last_seen_iteration: int | None = None,
    last_seen_status: str | None = None,
) -> dict[str, Any]:
    now = utc_now()
    return {
        "version": 1,
        "repo": str(repo),
        "launch_path": str(launch_path),
        "results_path": str(results_path),
        "state_path": str(state_path),
        "log_path": str(log_path),
        "status": status,
        "terminal_reason": terminal_reason,
        "pid": pid,
        "pgid": pgid,
        "command": list(command or []),
        "process_started_at": process_started_at,
        "process_command": process_command or "",
        "requested_stop_at": requested_stop_at,
        "last_decision": last_decision or "",
        "last_reason": last_reason or "",
        "last_seen_iteration": last_seen_iteration,
        "last_seen_status": last_seen_status or "",
        "created_at": now,
        "updated_at": now,
    }


def require_consistent_state(
    results_path: Path,
    state_path: Path,
    *,
    parsed: ParsedLog | None = None,
) -> tuple[ParsedLog, dict[str, Any], dict[str, Any], str]:
    parsed = parsed or parse_results_log(results_path)
    try:
        state_payload = read_state_payload(state_path)
    except AutoresearchError as exc:
        if not str(exc).startswith("Missing JSON file:") or parsed.metadata.get("mode") != "exec":
            raise
        state_payload = rebuild_exec_state_payload_from_results(
            results_path=results_path,
            state_path=state_path,
            parsed=parsed,
        )
    direction = state_payload.get("config", {}).get("direction")
    if direction not in {"lower", "higher"}:
        raise AutoresearchError("State config.direction must be 'lower' or 'higher'.")
    reconstructed = log_summary(parsed, direction)
    mismatches = compare_summary_to_state(reconstructed, state_payload)
    if mismatches:
        raise AutoresearchError(
            "Results log and JSON state diverged. Run autoresearch_resume_check.py first. "
            + "; ".join(mismatches)
        )
    return parsed, state_payload, reconstructed, direction


def make_row(
    *,
    iteration: str,
    commit: str,
    metric: Any,
    delta: Any,
    guard: str,
    status: str,
    description: str,
    labels: Any = None,
) -> dict[str, str]:
    metric_decimal = parse_decimal(metric, "metric")
    delta_decimal = parse_decimal(delta, "delta")
    if status not in MAIN_STATUSES and WORKER_LABEL_RE.fullmatch(iteration) is None:
        raise AutoresearchError(f"Unsupported status: {status}")
    return {
        "iteration": iteration,
        "commit": commit,
        "metric": format_decimal(metric_decimal),
        "delta": format_delta(delta_decimal),
        "guard": guard,
        "status": status,
        "description": format_description_with_labels(description, labels),
    }


def clone_state_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return deepcopy(payload)


def sync_state_payload_session_mode(
    payload: dict[str, Any],
    *,
    session_mode: str,
    execution_policy: str | None = None,
) -> dict[str, Any]:
    cloned = clone_state_payload(payload)
    config = cloned.get("config")
    if not isinstance(config, dict):
        raise AutoresearchError("State config must be an object.")

    config["session_mode"] = session_mode
    if session_mode == "foreground":
        config.pop("execution_policy", None)
    elif execution_policy is not None:
        config["execution_policy"] = execution_policy
    cloned["updated_at"] = utc_now()
    return cloned


def sync_state_session_mode(
    path: Path,
    *,
    session_mode: str,
    execution_policy: str | None = None,
) -> dict[str, Any]:
    payload = read_state_payload(path)
    updated = sync_state_payload_session_mode(
        payload,
        session_mode=session_mode,
        execution_policy=execution_policy,
    )
    write_json_atomic(path, updated)
    return updated
