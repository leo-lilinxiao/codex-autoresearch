#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import subprocess
import tempfile
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

HEADER = [
    "iteration",
    "commit",
    "metric",
    "delta",
    "guard",
    "status",
    "description",
]
EXEC_SCRATCH_ROOT = Path("/tmp/codex-autoresearch-exec")
LAUNCH_MANIFEST_NAME = "autoresearch-launch.json"
RUNTIME_STATE_NAME = "autoresearch-runtime.json"
RUNTIME_LOG_NAME = "autoresearch-runtime.log"
LESSONS_FILE_NAME = "autoresearch-lessons.md"
AUTORESEARCH_OWNED_BASENAMES = {
    "research-results.tsv",
    "autoresearch-state.json",
    "autoresearch-launch.json",
    "autoresearch-runtime.json",
    "autoresearch-runtime.log",
    "autoresearch-lessons.md",
}

MAIN_LABEL_RE = re.compile(r"^(0|[1-9]\d*)$")
WORKER_LABEL_RE = re.compile(r"^(0|[1-9]\d*)([a-z]+)$")
MAIN_STATUSES = {
    "baseline",
    "blocked",
    "crash",
    "discard",
    "drift",
    "keep",
    "no-op",
    "pivot",
    "refine",
    "search",
    "split",
}
REQUIRED_STATE_FIELDS = {
    "iteration",
    "baseline_metric",
    "best_metric",
    "best_iteration",
    "current_metric",
    "last_commit",
    "last_trial_commit",
    "last_trial_metric",
    "keeps",
    "discards",
    "crashes",
    "no_ops",
    "blocked",
    "splits",
    "consecutive_discards",
    "pivot_count",
    "last_status",
}


class AutoresearchError(Exception):
    pass


@dataclass
class LogRow:
    iteration: str
    commit: str
    metric: Decimal
    delta: str
    guard: str
    status: str
    description: str
    line_number: int

    @property
    def main_iteration(self) -> int | None:
        if MAIN_LABEL_RE.fullmatch(self.iteration):
            return int(self.iteration)
        return None

    @property
    def worker_parent_iteration(self) -> int | None:
        match = WORKER_LABEL_RE.fullmatch(self.iteration)
        if match:
            return int(match.group(1))
        return None


@dataclass
class ParsedLog:
    comments: list[str]
    metadata: dict[str, str]
    rows: list[LogRow]

    @property
    def main_rows(self) -> list[LogRow]:
        return [row for row in self.rows if row.main_iteration is not None]

    @property
    def worker_rows(self) -> list[LogRow]:
        return [row for row in self.rows if row.worker_parent_iteration is not None]


def parse_decimal(value: Any, field_name: str = "metric") -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise AutoresearchError(f"Invalid {field_name}: {value!r}") from exc


def format_decimal(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if text == "-0":
        return "0"
    return text


def format_delta(value: Decimal) -> str:
    text = format_decimal(value)
    if value > 0 and not text.startswith("+"):
        return f"+{text}"
    return text


def decimal_to_json_number(value: Decimal) -> int | float:
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def lexical_abspath(path: Path | None = None) -> Path:
    # Preserve the caller's path spelling (for example /var vs /private/var on macOS)
    # while still normalizing relative segments into an absolute path.
    return Path(os.path.abspath(str(path or Path.cwd())))


def find_repo_root(start: Path | None = None) -> Path:
    current = lexical_abspath(start)
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return current


def canonical_repo_root(start: Path | None = None) -> Path:
    return find_repo_root(start).resolve()


def has_git_repo(start: Path | None = None) -> bool:
    return (find_repo_root(start) / ".git").exists()


def default_launch_manifest_path(cwd: Path | None = None) -> Path:
    return find_repo_root(cwd) / LAUNCH_MANIFEST_NAME


def default_runtime_state_path(cwd: Path | None = None) -> Path:
    return find_repo_root(cwd) / RUNTIME_STATE_NAME


def default_runtime_log_path(cwd: Path | None = None) -> Path:
    return find_repo_root(cwd) / RUNTIME_LOG_NAME


def default_lessons_path(cwd: Path | None = None) -> Path:
    return find_repo_root(cwd) / LESSONS_FILE_NAME


def default_state_path(cwd: Path | None = None) -> Path:
    if cwd is None:
        return Path("autoresearch-state.json")
    return find_repo_root(cwd) / "autoresearch-state.json"


def is_autoresearch_owned_artifact(path: str | Path) -> bool:
    candidate = Path(path)
    names = [candidate.name]
    parent_name = candidate.parent.name
    if parent_name and parent_name != ".":
        names.append(parent_name)

    for name in names:
        pending = [name]
        seen = set()
        while pending:
            current = pending.pop()
            if current in seen:
                continue
            seen.add(current)
            if current in AUTORESEARCH_OWNED_BASENAMES:
                return True
            for base in AUTORESEARCH_OWNED_BASENAMES:
                if current.startswith(f"{base}.") or current.endswith(f".{base}"):
                    return True

            path_name = Path(current)
            suffix = path_name.suffix
            if suffix:
                stem = path_name.stem
                for marker in (".prev", ".bak", ".tmp"):
                    if stem.endswith(marker):
                        pending.append(f"{stem[: -len(marker)]}{suffix}")
            for marker in (".prev", ".bak", ".tmp"):
                if current.endswith(marker):
                    pending.append(current[: -len(marker)])
    return False


def default_exec_state_path(cwd: Path | None = None) -> Path:
    # Exec scratch identity should stay stable even if the same repo is accessed
    # through multiple lexical aliases, so keep the hash canonicalized.
    repo_root = canonical_repo_root(cwd)
    digest = hashlib.sha256(str(repo_root).encode("utf-8")).hexdigest()[:12]
    return EXEC_SCRATCH_ROOT / digest / "autoresearch-state.exec.json"


def prev_archive_path(path: Path) -> Path:
    if path.suffix:
        return path.with_name(f"{path.stem}.prev{path.suffix}")
    return path.with_name(f"{path.name}.prev")


def archive_path_to_prev(path: Path) -> Path | None:
    if not path.exists():
        return None
    archive_path = prev_archive_path(path)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    path.replace(archive_path)
    return archive_path


def resolve_state_path(
    requested_path: str | None,
    *,
    mode: str | None = None,
    cwd: Path | None = None,
    allow_exec_scratch_fallback: bool = False,
) -> Path:
    if requested_path:
        candidate = Path(requested_path)
        if candidate.is_absolute() or cwd is None:
            return candidate
        return lexical_abspath(find_repo_root(cwd) / candidate)

    repo_state_path = default_state_path(cwd)
    if mode == "exec":
        return default_exec_state_path(cwd)
    if repo_state_path.exists():
        return repo_state_path

    if allow_exec_scratch_fallback:
        scratch_state_path = default_exec_state_path(cwd)
        if scratch_state_path.exists():
            return scratch_state_path
    return repo_state_path


def resolve_state_path_for_log(
    requested_path: str | None,
    parsed: ParsedLog | dict[str, str] | None,
    *,
    cwd: Path | None = None,
) -> Path:
    if isinstance(parsed, ParsedLog):
        metadata = parsed.metadata
    elif isinstance(parsed, dict):
        metadata = parsed
    else:
        metadata = {}
    mode = metadata.get("mode")
    exec_mode = mode == "exec"
    return resolve_state_path(
        requested_path,
        mode="exec" if exec_mode else None,
        cwd=cwd,
        allow_exec_scratch_fallback=exec_mode,
    )


def cleanup_exec_state(cwd: Path | None = None) -> tuple[Path, bool]:
    state_path = default_exec_state_path(cwd)
    removed = False
    if state_path.exists():
        state_path.unlink()
        removed = True

    scratch_root = EXEC_SCRATCH_ROOT.resolve()
    parent = state_path.parent
    while parent.exists() and parent != scratch_root:
        try:
            parent.rmdir()
        except OSError:
            break
        parent = parent.parent

    return state_path, removed


def git_status_paths(repo: Path) -> list[str]:
    completed = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "-z",
        ],
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        raise AutoresearchError(stderr or "git status failed")

    entries = [entry for entry in completed.stdout.decode("utf-8", errors="replace").split("\0") if entry]
    paths: list[str] = []
    index = 0
    while index < len(entries):
        entry = entries[index]
        path = entry[3:] if len(entry) > 3 else entry
        status = entry[:2]
        paths.append(path)
        if "R" in status or "C" in status:
            if index + 1 < len(entries):
                paths.append(entries[index + 1])
            index += 1
        index += 1
    return paths


def improvement(metric: Decimal, reference: Decimal, direction: str) -> bool:
    if direction == "lower":
        return metric < reference
    if direction == "higher":
        return metric > reference
    raise AutoresearchError(f"Unsupported direction: {direction}")


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
        raise AutoresearchError(
            f"Invalid launch manifest in {path}: missing original_goal"
        )
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
    """Read only the comment-line metadata from a results log.

    Unlike parse_results_log this never raises on corrupt data rows --
    it is safe to call when full parsing has already failed.
    """
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
        metric = parse_decimal(columns[2], "metric")
        row = LogRow(
            iteration=columns[0],
            commit=columns[1],
            metric=metric,
            delta=columns[3],
            guard=columns[4],
            status=columns[5],
            description=columns[6],
            line_number=line_number,
        )
        rows.append(row)

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
        "keeps": 0,
        "discards": 0,
        "crashes": 0,
        "no_ops": 0,
        "blocked": 0,
        "splits": 0,
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

        if row.status == "keep":
            summary["keeps"] += 1
            summary["current_metric"] = row.metric
            summary["last_commit"] = row.commit
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
        elif row.status == "blocked":
            summary["blocked"] += 1
        elif row.status == "drift":
            summary["current_metric"] = row.metric
            if row.commit != "-":
                summary["last_commit"] = row.commit
            summary["consecutive_discards"] = 0
            if improvement(row.metric, summary["best_metric"], direction):
                summary["best_metric"] = row.metric
                summary["best_iteration"] = main_iteration
        elif row.status == "refine":
            pass
        elif row.status == "pivot":
            summary["pivot_count"] += 1
        elif row.status == "search":
            pass
        elif row.status == "split":
            summary["splits"] += 1
        else:
            raise AutoresearchError(
                f"Unsupported status {row.status!r} in results log line {row.line_number}"
            )

    return summary


def compare_summary_to_state(
    reconstructed: dict[str, Any],
    state_payload: dict[str, Any],
    *,
    tolerance: Decimal = Decimal("0.001"),
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
    compare_scalar_field("splits")
    compare_scalar_field("consecutive_discards")
    compare_scalar_field("pivot_count")
    compare_scalar_field("last_status")
    return mismatches


def build_state_payload(
    *,
    mode: str,
    run_tag: str | None,
    config: dict[str, Any],
    summary: dict[str, Any],
    supervisor: dict[str, Any] | None = None,
) -> dict[str, Any]:
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
            "keeps": summary["keeps"],
            "discards": summary["discards"],
            "crashes": summary["crashes"],
            "no_ops": summary["no_ops"],
            "blocked": summary["blocked"],
            "splits": summary["splits"],
            "consecutive_discards": summary["consecutive_discards"],
            "pivot_count": summary["pivot_count"],
            "last_status": summary["last_status"],
        },
        "updated_at": utc_now(),
    }
    if supervisor is not None:
        payload["supervisor"] = deepcopy(supervisor)
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
    requested_stop_at: str | None = None,
    last_decision: str | None = None,
    last_reason: str | None = None,
    last_seen_iteration: int | None = None,
    last_seen_status: str | None = None,
) -> dict[str, Any]:
    now = utc_now()
    payload = {
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
        "requested_stop_at": requested_stop_at,
        "last_decision": last_decision or "",
        "last_reason": last_reason or "",
        "last_seen_iteration": last_seen_iteration,
        "last_seen_status": last_seen_status or "",
        "created_at": now,
        "updated_at": now,
    }
    return payload


def require_consistent_state(
    results_path: Path,
    state_path: Path,
    *,
    parsed: ParsedLog | None = None,
) -> tuple[ParsedLog, dict[str, Any], dict[str, Any], str]:
    parsed = parsed or parse_results_log(results_path)
    state_payload = read_state_payload(state_path)
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
    metric: Decimal,
    delta: Decimal,
    guard: str,
    status: str,
    description: str,
) -> dict[str, str]:
    if status not in MAIN_STATUSES and WORKER_LABEL_RE.fullmatch(iteration) is None:
        raise AutoresearchError(f"Unsupported status: {status}")
    return {
        "iteration": iteration,
        "commit": commit,
        "metric": format_decimal(metric),
        "delta": format_delta(delta),
        "guard": guard,
        "status": status,
        "description": description,
    }


def clone_state_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return deepcopy(payload)
