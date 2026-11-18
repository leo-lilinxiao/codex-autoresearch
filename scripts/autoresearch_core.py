#!/usr/bin/env python3
"""Strict state, command, and Git primitives for codex-autoresearch."""

from __future__ import annotations

import base64
import json
import math
import os
import signal
import subprocess
import time
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = 2
RESULTS_DIR = "autoresearch-results"
RUN_FILE = "run.json"
EVENTS_FILE = "events.jsonl"
RUNTIME_FILE = "runtime.json"
RUNTIME_LOG = "runtime.log"
PROTECTED_PREFIXES = (
    RESULTS_DIR,
    ".git",
    ".agents/skills/codex-autoresearch",
)
TERMINAL_EVENTS = {"blocked", "complete", "error", "stopped"}
MAX_CONSECUTIVE_CRASHES = 3


class AutoresearchError(RuntimeError):
    """A user-actionable contract violation."""


class CommandTimeout(AutoresearchError):
    """A command exceeded its timeout and its process tree was terminated."""


@dataclass(frozen=True)
class Paths:
    repo: Path
    root: Path
    run: Path
    events: Path
    runtime: Path
    runtime_log: Path
    stop_request: Path
    logs: Path


@dataclass(frozen=True)
class RunState:
    status: str
    metric: Decimal
    head: str
    iterations: int
    last_event: dict[str, Any]
    consecutive_crashes: int


@dataclass(frozen=True)
class CommandResult:
    command: str
    returncode: int
    stdout: str
    stderr: str
    duration_seconds: float
    log_path: Path


def utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def paths_for(repo: Path | str) -> Paths:
    resolved = Path(repo).expanduser().resolve()
    root = resolved / RESULTS_DIR
    return Paths(
        repo=resolved,
        root=root,
        run=root / RUN_FILE,
        events=root / EVENTS_FILE,
        runtime=root / RUNTIME_FILE,
        runtime_log=root / RUNTIME_LOG,
        stop_request=root / "stop-request.json",
        logs=root / "logs",
    )


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number {value!r} is not allowed")


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def parse_json(text: str, *, source: str, decimal_numbers: bool = False) -> Any:
    options: dict[str, Any] = {
        "object_pairs_hook": _strict_object,
        "parse_constant": _reject_constant,
    }
    if decimal_numbers:
        options["parse_float"] = Decimal
    try:
        return json.loads(text, **options)
    except (json.JSONDecodeError, ValueError) as exc:
        raise AutoresearchError(f"Invalid JSON in {source}: {exc}") from exc


def json_text(value: Any, *, pretty: bool = False) -> str:
    kwargs: dict[str, Any] = {
        "ensure_ascii": True,
        "allow_nan": False,
        "sort_keys": True,
    }
    if pretty:
        kwargs["indent"] = 2
    else:
        kwargs["separators"] = (",", ":")
    return json.dumps(value, **kwargs)


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    data = (json_text(payload, pretty=True) + "\n").encode("utf-8")
    try:
        with temporary.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    data = text.encode("utf-8")
    try:
        with temporary.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def append_json_line(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json_text(payload) + "\n").encode("utf-8")
    descriptor = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o644)
    try:
        offset = 0
        while offset < len(data):
            written = os.write(descriptor, data[offset:])
            if written <= 0:
                raise AutoresearchError(f"Failed to append a complete event to {path}")
            offset += written
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def parse_decimal(value: Any, *, field: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise AutoresearchError(f"{field} must be a finite number")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise AutoresearchError(f"{field} must be a finite number, got {value!r}") from exc
    if not parsed.is_finite():
        raise AutoresearchError(f"{field} must be finite, got {value!r}")
    return parsed


def decimal_json(value: Decimal) -> int | float:
    if value == value.to_integral_value():
        return int(value)
    converted = float(value)
    if not math.isfinite(converted):
        raise AutoresearchError(f"Metric {value} cannot be represented as JSON")
    if Decimal(str(converted)) != value:
        raise AutoresearchError(
            f"Metric {value} would lose precision in JSON. Use a representable decimal"
        )
    return converted


def require_exact_keys(
    payload: dict[str, Any],
    *,
    required: set[str],
    optional: set[str] | None = None,
    source: str,
) -> None:
    optional = optional or set()
    missing = sorted(required - payload.keys())
    unknown = sorted(payload.keys() - required - optional)
    if missing or unknown:
        details = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if unknown:
            details.append("unknown " + ", ".join(unknown))
        raise AutoresearchError(f"Invalid schema in {source}: {', '.join(details)}")


RUN_KEYS = {
    "schema_version",
    "run_id",
    "created_at",
    "repo",
    "branch",
    "mode",
    "goal",
    "scope",
    "metric",
    "guard",
    "target",
    "max_iterations",
    "timeout_seconds",
    "background",
}
METRIC_KEYS = {"name", "direction", "command", "json_key"}
BACKGROUND_KEYS = {"execution_policy", "codex_bin", "model"}


def validate_run(payload: Any, *, source: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise AutoresearchError(f"{source} must contain a JSON object")
    require_exact_keys(payload, required=RUN_KEYS, source=source)
    if payload["schema_version"] != SCHEMA_VERSION:
        raise AutoresearchError(
            f"Unsupported run schema {payload['schema_version']!r} in {source}. "
            f"Expected {SCHEMA_VERSION}. Archive the old run and start a new one."
        )
    for key in ("run_id", "created_at", "repo", "branch", "mode", "goal"):
        if not isinstance(payload[key], str) or not payload[key].strip():
            raise AutoresearchError(f"{source}.{key} must be a non-empty string")
    if payload["mode"] not in {"foreground", "background"}:
        raise AutoresearchError(f"{source}.mode must be foreground or background")
    if not isinstance(payload["scope"], list) or not payload["scope"]:
        raise AutoresearchError(f"{source}.scope must be a non-empty string array")
    if any(not isinstance(item, str) or not item for item in payload["scope"]):
        raise AutoresearchError(f"{source}.scope contains an invalid path")
    metric = payload["metric"]
    if not isinstance(metric, dict):
        raise AutoresearchError(f"{source}.metric must be an object")
    require_exact_keys(metric, required=METRIC_KEYS, source=f"{source}.metric")
    if metric["direction"] not in {"lower", "higher"}:
        raise AutoresearchError(f"{source}.metric.direction must be lower or higher")
    for key in ("name", "command"):
        if not isinstance(metric[key], str) or not metric[key].strip():
            raise AutoresearchError(f"{source}.metric.{key} must be a non-empty string")
    if metric["json_key"] is not None and (
        not isinstance(metric["json_key"], str) or not metric["json_key"].strip()
    ):
        raise AutoresearchError(f"{source}.metric.json_key must be null or a non-empty string")
    if payload["guard"] is not None and (
        not isinstance(payload["guard"], str) or not payload["guard"].strip()
    ):
        raise AutoresearchError(f"{source}.guard must be null or a non-empty string")
    parse_decimal(payload["target"], field=f"{source}.target")
    if payload["max_iterations"] is not None and (
        not isinstance(payload["max_iterations"], int)
        or isinstance(payload["max_iterations"], bool)
        or payload["max_iterations"] <= 0
    ):
        raise AutoresearchError(f"{source}.max_iterations must be null or a positive integer")
    if (
        not isinstance(payload["timeout_seconds"], int)
        or isinstance(payload["timeout_seconds"], bool)
        or payload["timeout_seconds"] <= 0
    ):
        raise AutoresearchError(f"{source}.timeout_seconds must be a positive integer")
    background = payload["background"]
    if payload["mode"] == "foreground":
        if background is not None:
            raise AutoresearchError(f"{source}.background must be null for a foreground run")
    else:
        if not isinstance(background, dict):
            raise AutoresearchError(f"{source}.background must be an object for a background run")
        require_exact_keys(background, required=BACKGROUND_KEYS, source=f"{source}.background")
        if background["execution_policy"] not in {"danger-full-access", "workspace-write"}:
            raise AutoresearchError(
                f"{source}.background.execution_policy must be danger-full-access or workspace-write"
            )
        if not isinstance(background["codex_bin"], str) or not background["codex_bin"].strip():
            raise AutoresearchError(f"{source}.background.codex_bin must be a non-empty string")
        if background["model"] is not None and (
            not isinstance(background["model"], str) or not background["model"].strip()
        ):
            raise AutoresearchError(f"{source}.background.model must be null or a non-empty string")
    return payload


EVENT_COMMON = {"schema_version", "run_id", "seq", "time", "event"}
EVENT_FIELDS = {
    "baseline": {"head", "metric", "verify_log", "guard_log"},
    "iteration": {
        "iteration",
        "outcome",
        "description",
        "previous_metric",
        "trial_metric",
        "retained_metric",
        "trial_commit",
        "head",
        "revert_commit",
        "guard",
        "verify_log",
        "guard_log",
    },
    "blocked": {"reason", "head", "metric"},
    "complete": {"reason", "head", "metric"},
    "error": {"reason", "head", "metric", "trial_commit", "revert_commit", "log"},
    "resumed": {"note", "head", "metric"},
    "stopped": {"reason", "head", "metric"},
}


def validate_event(payload: Any, *, run_id: str, expected_seq: int, source: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise AutoresearchError(f"{source} must contain a JSON object")
    event_type = payload.get("event")
    if event_type not in EVENT_FIELDS:
        raise AutoresearchError(f"{source}.event has unsupported value {event_type!r}")
    require_exact_keys(
        payload,
        required=EVENT_COMMON | EVENT_FIELDS[event_type],
        source=source,
    )
    if payload["schema_version"] != SCHEMA_VERSION:
        raise AutoresearchError(f"{source}.schema_version must be {SCHEMA_VERSION}")
    if payload["run_id"] != run_id:
        raise AutoresearchError(f"{source}.run_id does not match run.json")
    if payload["seq"] != expected_seq:
        raise AutoresearchError(f"{source}.seq must be {expected_seq}, got {payload['seq']!r}")
    if not isinstance(payload["time"], str) or not payload["time"]:
        raise AutoresearchError(f"{source}.time must be a non-empty string")
    for key in ("head",):
        if key in payload and (not isinstance(payload[key], str) or not payload[key]):
            raise AutoresearchError(f"{source}.{key} must be a non-empty string")
    for key in ("metric", "previous_metric", "trial_metric", "retained_metric"):
        if key == "trial_metric" and payload.get("outcome") == "crash":
            if payload[key] is not None:
                raise AutoresearchError(f"{source}.trial_metric must be null for a crash")
        elif key in payload:
            parse_decimal(payload[key], field=f"{source}.{key}")
    if event_type == "baseline":
        if not isinstance(payload["verify_log"], str) or not payload["verify_log"]:
            raise AutoresearchError(f"{source}.verify_log must be a non-empty string")
        if payload["guard_log"] is not None and (
            not isinstance(payload["guard_log"], str) or not payload["guard_log"]
        ):
            raise AutoresearchError(f"{source}.guard_log must be null or a non-empty string")
    if event_type == "iteration":
        if payload["outcome"] not in {"keep", "discard", "crash"}:
            raise AutoresearchError(f"{source}.outcome must be keep, discard, or crash")
        if payload["guard"] not in {"pass", "fail", "not_run"}:
            raise AutoresearchError(f"{source}.guard is invalid")
        if not isinstance(payload["iteration"], int) or payload["iteration"] <= 0:
            raise AutoresearchError(f"{source}.iteration must be a positive integer")
        for key in ("description", "trial_commit", "verify_log"):
            if not isinstance(payload[key], str) or not payload[key]:
                raise AutoresearchError(f"{source}.{key} must be a non-empty string")
        for key in ("revert_commit", "guard_log"):
            if payload[key] is not None and (not isinstance(payload[key], str) or not payload[key]):
                raise AutoresearchError(f"{source}.{key} must be null or a non-empty string")
    if event_type in {"blocked", "complete", "error", "stopped"}:
        if not isinstance(payload["reason"], str) or not payload["reason"].strip():
            raise AutoresearchError(f"{source}.reason must be a non-empty string")
    if event_type == "error":
        for key in ("trial_commit", "revert_commit", "log"):
            if payload[key] is not None and (not isinstance(payload[key], str) or not payload[key]):
                raise AutoresearchError(f"{source}.{key} must be null or a non-empty string")
        if payload["trial_commit"] is None and payload["revert_commit"] is not None:
            raise AutoresearchError(f"{source}.revert_commit requires trial_commit")
        if payload["revert_commit"] is not None and payload["head"] != payload["revert_commit"]:
            raise AutoresearchError(f"{source}.head must equal revert_commit after rollback")
    if event_type == "resumed" and (
        not isinstance(payload["note"], str) or not payload["note"].strip()
    ):
        raise AutoresearchError(f"{source}.note must be a non-empty string")
    return payload


def load_run(repo: Path | str) -> tuple[Paths, dict[str, Any]]:
    paths = paths_for(repo)
    if not paths.run.is_file():
        raise AutoresearchError(f"No autoresearch run at {paths.run}")
    try:
        text = paths.run.read_text(encoding="utf-8")
    except OSError as exc:
        raise AutoresearchError(f"Cannot read {paths.run}: {exc}") from exc
    payload = validate_run(parse_json(text, source=str(paths.run)), source=str(paths.run))
    if Path(payload["repo"]).resolve() != paths.repo:
        raise AutoresearchError(
            f"run.json belongs to {payload['repo']}, not requested repo {paths.repo}"
        )
    if normalize_scopes(paths.repo, payload["scope"]) != payload["scope"]:
        raise AutoresearchError(f"{paths.run}.scope is not in canonical repository-relative form")
    return paths, payload


def load_events(paths: Paths, run: dict[str, Any]) -> list[dict[str, Any]]:
    if not paths.events.is_file():
        raise AutoresearchError(f"Missing event source of truth: {paths.events}")
    try:
        text = paths.events.read_text(encoding="utf-8")
    except OSError as exc:
        raise AutoresearchError(f"Cannot read {paths.events}: {exc}") from exc
    if not text:
        raise AutoresearchError(f"Event log is empty: {paths.events}")
    if not text.endswith("\n"):
        raise AutoresearchError(f"Event log has a partial final record: {paths.events}")
    events: list[dict[str, Any]] = []
    for index, line in enumerate(text.splitlines()):
        if not line.strip():
            raise AutoresearchError(f"Blank event record at {paths.events}:{index + 1}")
        payload = parse_json(line, source=f"{paths.events}:{index + 1}")
        events.append(
            validate_event(
                payload,
                run_id=run["run_id"],
                expected_seq=index,
                source=f"{paths.events}:{index + 1}",
            )
        )
    return events


def derive_state(run: dict[str, Any], events: list[dict[str, Any]]) -> RunState:
    if not events or events[0]["event"] != "baseline":
        raise AutoresearchError("events.jsonl must begin with exactly one baseline event")
    metric = parse_decimal(events[0]["metric"], field="baseline.metric")
    head = events[0]["head"]
    if run["guard"] is None and events[0]["guard_log"] is not None:
        raise AutoresearchError("Baseline has a guard log but no configured guard")
    if run["guard"] is not None and events[0]["guard_log"] is None:
        raise AutoresearchError("Baseline is missing its configured guard log")
    iterations = 0
    consecutive_crashes = 0
    status = "active"
    last_terminal: str | None = None
    last_terminal_event: dict[str, Any] | None = None

    for event in events[1:]:
        event_type = event["event"]
        if last_terminal is not None:
            if event_type != "resumed" or last_terminal == "complete":
                raise AutoresearchError(
                    f"Invalid event transition: {event_type} follows terminal event {last_terminal}"
                )
            if (
                last_terminal == "error"
                and last_terminal_event is not None
                and last_terminal_event["trial_commit"] is not None
                and last_terminal_event["revert_commit"] is None
            ):
                raise AutoresearchError("Cannot resume an error with an unreverted trial commit")
            status = "active"
            last_terminal = None
            last_terminal_event = None
        elif event_type == "resumed":
            raise AutoresearchError("resumed event requires a preceding blocked, error, or stopped event")

        if event_type == "iteration":
            iterations += 1
            if event["iteration"] != iterations:
                raise AutoresearchError(
                    f"Iteration number must be {iterations}, got {event['iteration']}"
                )
            previous_metric = parse_decimal(
                event["previous_metric"], field="iteration.previous_metric"
            )
            retained_metric = parse_decimal(
                event["retained_metric"], field="iteration.retained_metric"
            )
            if previous_metric != metric:
                raise AutoresearchError(
                    f"Iteration {iterations} previous_metric does not match retained state"
                )
            if event["outcome"] == "crash":
                if retained_metric != metric or event["guard"] != "not_run" or event["guard_log"] is not None:
                    raise AutoresearchError(
                        f"Iteration {iterations} crash must keep the retained metric and skip the guard"
                    )
                if event["revert_commit"] is None or event["head"] != event["revert_commit"]:
                    raise AutoresearchError(
                        f"Iteration {iterations} crash must point at its revert commit"
                    )
                consecutive_crashes += 1
                head = event["head"]
                continue
            consecutive_crashes = 0
            trial_metric = parse_decimal(event["trial_metric"], field="iteration.trial_metric")
            trial_improved = improved(trial_metric, metric, run["metric"]["direction"])
            if event["outcome"] == "keep":
                if not trial_improved:
                    raise AutoresearchError(
                        f"Iteration {iterations} keeps a metric that did not improve"
                    )
                if retained_metric != trial_metric:
                    raise AutoresearchError(
                        f"Iteration {iterations} keep must retain the trial metric"
                    )
                if event["guard"] != "pass":
                    raise AutoresearchError(f"Iteration {iterations} keep requires a passing guard")
                if event["revert_commit"] is not None or event["head"] != event["trial_commit"]:
                    raise AutoresearchError(
                        f"Iteration {iterations} keep has invalid commit provenance"
                    )
                if run["guard"] is None and event["guard_log"] is not None:
                    raise AutoresearchError(
                        f"Iteration {iterations} has a guard log but no configured guard"
                    )
                if run["guard"] is not None and event["guard_log"] is None:
                    raise AutoresearchError(
                        f"Iteration {iterations} is missing its configured guard log"
                    )
            else:
                if retained_metric != metric:
                    raise AutoresearchError(
                        f"Iteration {iterations} discard changed the retained metric"
                    )
                if event["revert_commit"] is None or event["head"] != event["revert_commit"]:
                    raise AutoresearchError(
                        f"Iteration {iterations} discard must point at its revert commit"
                    )
                if trial_improved:
                    if run["guard"] is None or event["guard"] != "fail" or event["guard_log"] is None:
                        raise AutoresearchError(
                            f"Iteration {iterations} discarded an improvement without a failed guard"
                        )
                elif event["guard"] != "not_run" or event["guard_log"] is not None:
                    raise AutoresearchError(
                        f"Iteration {iterations} ran a guard for a non-improving trial"
                    )
            metric = retained_metric
            head = event["head"]
        elif event_type in TERMINAL_EVENTS:
            event_metric = parse_decimal(event["metric"], field=f"{event_type}.metric")
            if event_metric != metric:
                raise AutoresearchError(
                    f"{event_type} event does not match the last retained metric"
                )
            if event_type != "error" and event["head"] != head:
                raise AutoresearchError(
                    f"{event_type} event does not match the last retained commit"
                )
            if event_type == "complete" and not target_reached(
                event_metric,
                parse_decimal(run["target"], field="run.target"),
                run["metric"]["direction"],
            ):
                raise AutoresearchError("complete event does not satisfy the configured target")
            if event_type == "error":
                if event["trial_commit"] is None and event["head"] != head:
                    raise AutoresearchError(
                        "error without a trial commit changed the retained HEAD"
                    )
                if (
                    event["trial_commit"] is not None
                    and event["revert_commit"] is None
                    and event["head"] != event["trial_commit"]
                ):
                    raise AutoresearchError(
                        "unreverted error HEAD must equal its trial commit"
                    )
            head = event["head"]
            status = event_type
            last_terminal = event_type
            last_terminal_event = event
        elif event_type == "resumed":
            if parse_decimal(event["metric"], field="resumed.metric") != metric or event["head"] != head:
                raise AutoresearchError("resumed event does not match retained state")
            consecutive_crashes = 0

    if status == "active":
        target = parse_decimal(run["target"], field="run.target")
        if target_reached(metric, target, run["metric"]["direction"]):
            raise AutoresearchError("Active event history reached the target but lacks a complete event")
        if run["max_iterations"] is not None and iterations >= run["max_iterations"]:
            raise AutoresearchError(
                "Active event history reached the iteration limit but lacks a stopped event"
            )
        if consecutive_crashes >= MAX_CONSECUTIVE_CRASHES:
            raise AutoresearchError(
                "Active event history reached the crash limit but lacks an error event"
            )

    return RunState(
        status=status,
        metric=metric,
        head=head,
        iterations=iterations,
        last_event=events[-1],
        consecutive_crashes=consecutive_crashes,
    )


def load_context(repo: Path | str) -> tuple[Paths, dict[str, Any], list[dict[str, Any]], RunState]:
    paths, run = load_run(repo)
    events = load_events(paths, run)
    state = derive_state(run, events)
    return paths, run, events, state


def append_event(paths: Paths, run: dict[str, Any], events: list[dict[str, Any]], **fields: Any) -> dict[str, Any]:
    event = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run["run_id"],
        "seq": len(events),
        "time": utc_now(),
        **fields,
    }
    validate_event(
        event,
        run_id=run["run_id"],
        expected_seq=len(events),
        source="new event",
    )
    append_json_line(paths.events, event)
    return event


def run_git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
        check=False,
    )
    if check and completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise AutoresearchError(f"git {' '.join(args)} failed: {detail or 'no output'}")
    return completed


def require_git_repo(repo: Path) -> None:
    if not repo.is_dir():
        raise AutoresearchError(f"Repository directory does not exist: {repo}")
    completed = run_git(repo, "rev-parse", "--show-toplevel", check=False)
    if completed.returncode != 0:
        raise AutoresearchError(f"Autoresearch requires a Git repository: {repo}")
    root = Path(completed.stdout.strip()).resolve()
    if root != repo:
        raise AutoresearchError(f"Use the Git repository root {root}, not {repo}")


def git_head(repo: Path) -> str:
    return run_git(repo, "rev-parse", "HEAD").stdout.strip()


def git_branch(repo: Path) -> str:
    completed = run_git(repo, "symbolic-ref", "--quiet", "--short", "HEAD", check=False)
    if completed.returncode != 0 or not completed.stdout.strip():
        raise AutoresearchError("Autoresearch requires a named Git branch, not detached HEAD")
    return completed.stdout.strip()


def require_git_identity(repo: Path) -> None:
    for identity in ("GIT_AUTHOR_IDENT", "GIT_COMMITTER_IDENT"):
        completed = run_git(repo, "var", identity, check=False)
        if completed.returncode != 0 or not completed.stdout.strip():
            detail = (completed.stderr or completed.stdout).strip()
            raise AutoresearchError(
                f"Git identity {identity} is not configured: {detail or 'no identity returned'}"
            )


def git_status_paths(repo: Path) -> list[str]:
    environment = os.environ.copy()
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    completed = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        capture_output=True,
        env=environment,
        check=False,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="strict").strip()
        raise AutoresearchError(f"git status failed: {stderr or 'no output'}")
    try:
        text = completed.stdout.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise AutoresearchError(f"git status returned non-UTF-8 paths: {exc}") from exc
    tokens = text.split("\0")
    if tokens and tokens[-1] == "":
        tokens.pop()
    paths: list[str] = []
    index = 0
    while index < len(tokens):
        entry = tokens[index]
        if len(entry) < 4 or entry[2] != " ":
            raise AutoresearchError(f"Unexpected git status record: {entry!r}")
        status = entry[:2]
        paths.append(entry[3:])
        index += 1
        if "R" in status or "C" in status:
            if index >= len(tokens):
                raise AutoresearchError("Incomplete rename/copy record from git status")
            paths.append(tokens[index])
            index += 1
    return sorted(set(paths))


def is_protected(path: str) -> bool:
    normalized = path.replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return any(normalized == prefix or normalized.startswith(prefix + "/") for prefix in PROTECTED_PREFIXES)


def is_owned_artifact(path: str) -> bool:
    normalized = path.replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized == RESULTS_DIR or normalized.startswith(RESULTS_DIR + "/")


def working_paths(repo: Path) -> list[str]:
    return [path for path in git_status_paths(repo) if not is_owned_artifact(path)]


def staged_paths(repo: Path) -> list[str]:
    environment = os.environ.copy()
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    completed = subprocess.run(
        ["git", "-C", str(repo), "diff", "--cached", "--name-only", "-z"],
        capture_output=True,
        env=environment,
        check=False,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="strict").strip()
        raise AutoresearchError(f"git diff --cached failed: {stderr or 'no output'}")
    try:
        text = completed.stdout.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise AutoresearchError(f"git diff --cached returned non-UTF-8 paths: {exc}") from exc
    return sorted(path for path in text.split("\0") if path)


def require_no_staged_artifacts(repo: Path) -> None:
    staged = [path for path in staged_paths(repo) if is_owned_artifact(path)]
    if staged:
        raise AutoresearchError(
            "Autoresearch artifacts must never be staged: " + ", ".join(staged)
        )


def require_artifacts_untracked(repo: Path) -> None:
    completed = run_git(repo, "ls-files", "-z", "--", RESULTS_DIR)
    tracked = [path for path in completed.stdout.split("\0") if path]
    if tracked:
        raise AutoresearchError(
            f"{RESULTS_DIR}/ must remain untracked, but Git tracks: " + ", ".join(tracked)
        )


def require_clean_repo(repo: Path, *, expected_head: str | None = None, expected_branch: str | None = None) -> None:
    dirty = working_paths(repo)
    if dirty:
        raise AutoresearchError(
            "Repository has uncommitted changes: " + ", ".join(dirty) + ". Commit or stash them first."
        )
    if expected_head is not None and git_head(repo) != expected_head:
        raise AutoresearchError(
            f"Git HEAD changed outside autoresearch: expected {expected_head}, got {git_head(repo)}"
        )
    if expected_branch is not None and git_branch(repo) != expected_branch:
        raise AutoresearchError(
            f"Git branch changed outside autoresearch: expected {expected_branch}, got {git_branch(repo)}"
        )


def normalize_scopes(repo: Path, scopes: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    for raw in scopes:
        value = raw.strip().replace("\\", "/")
        if not value:
            raise AutoresearchError("Scope paths cannot be empty")
        if any(character in value for character in "*?[]"):
            raise AutoresearchError(
                f"Scope {raw!r} uses a glob. Use repository-relative files or directories instead."
            )
        candidate = Path(value)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise AutoresearchError(f"Scope must stay inside the repository: {raw!r}")
        value = value.removeprefix("./").rstrip("/") or "."
        resolved = (repo / value).resolve()
        try:
            resolved.relative_to(repo)
        except ValueError as exc:
            raise AutoresearchError(f"Scope escapes the repository: {raw!r}") from exc
        if is_protected(value):
            raise AutoresearchError(f"Scope cannot target autoresearch or Git internals: {raw!r}")
        if value not in normalized:
            normalized.append(value)
    if not normalized:
        raise AutoresearchError("At least one scope path is required")
    return normalized


def path_in_scope(path: str, scopes: list[str]) -> bool:
    normalized = path.replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    for scope in scopes:
        if scope == "." or normalized == scope or normalized.startswith(scope + "/"):
            return True
    return False


def require_paths_in_scope(paths: list[str], scopes: list[str]) -> None:
    protected = [path for path in paths if is_protected(path)]
    if protected:
        raise AutoresearchError("Protected paths were modified: " + ", ".join(protected))
    outside = [path for path in paths if not path_in_scope(path, scopes)]
    if outside:
        raise AutoresearchError("Out-of-scope paths were modified: " + ", ".join(outside))


def _record_command_output(
    *,
    command: str,
    cwd: Path,
    duration_seconds: float,
    returncode: int | None,
    stdout_bytes: bytes,
    stderr_bytes: bytes,
    timed_out: bool,
    log_path: Path,
    termination_error: str | None = None,
) -> tuple[str | None, str | None, list[str]]:
    payload: dict[str, Any] = {
        "command": command,
        "cwd": str(cwd),
        "duration_seconds": round(duration_seconds, 6),
        "returncode": returncode,
        "timed_out": timed_out,
    }
    decoded: dict[str, str | None] = {}
    encoding_errors: list[str] = []
    for stream, data in (("stdout", stdout_bytes), ("stderr", stderr_bytes)):
        try:
            decoded[stream] = data.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            decoded[stream] = None
            payload[f"{stream}_base64"] = base64.b64encode(data).decode("ascii")
            encoding_errors.append(f"{stream}: {exc}")
    payload.update(decoded)
    if encoding_errors:
        payload["encoding_errors"] = encoding_errors
    if termination_error is not None:
        payload["termination_error"] = termination_error
    write_json_atomic(log_path, payload)
    return decoded["stdout"], decoded["stderr"], encoding_errors


def run_command(
    *,
    command: str,
    cwd: Path,
    timeout_seconds: int,
    log_path: Path,
) -> CommandResult:
    started = time.monotonic()
    popen_kwargs: dict[str, Any] = {
        "cwd": cwd,
        "shell": True,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_kwargs["start_new_session"] = True
    process = subprocess.Popen(command, **popen_kwargs)
    try:
        stdout_bytes, stderr_bytes = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired as timeout_error:
        termination_error: str | None = None
        try:
            terminate_process_tree(process)
        except AutoresearchError as exc:
            termination_error = str(exc)
            stdout_bytes = timeout_error.output or b""
            stderr_bytes = timeout_error.stderr or b""
        else:
            stdout_bytes, stderr_bytes = process.communicate()
        duration = time.monotonic() - started
        _, _, encoding_errors = _record_command_output(
            command=command,
            cwd=cwd,
            duration_seconds=duration,
            returncode=process.returncode,
            stdout_bytes=stdout_bytes,
            stderr_bytes=stderr_bytes,
            timed_out=True,
            log_path=log_path,
            termination_error=termination_error,
        )
        details = []
        if encoding_errors:
            details.append("output was not valid UTF-8")
        if termination_error is not None:
            details.append(f"process-tree termination failed: {termination_error}")
        suffix = f". {', '.join(details)}" if details else ""
        error_type = CommandTimeout if termination_error is None and not encoding_errors else AutoresearchError
        raise error_type(
            f"Command timed out after {timeout_seconds}s: {command}{suffix}. "
            f"Full output: {log_path}"
        )
    duration = time.monotonic() - started
    stdout, stderr, encoding_errors = _record_command_output(
        command=command,
        cwd=cwd,
        duration_seconds=duration,
        returncode=process.returncode,
        stdout_bytes=stdout_bytes,
        stderr_bytes=stderr_bytes,
        timed_out=False,
        log_path=log_path,
    )
    if encoding_errors:
        raise AutoresearchError(
            f"Command produced non-UTF-8 output ({', '.join(encoding_errors)}): {command}. "
            f"Raw output is base64-encoded in {log_path}"
        )
    if stdout is None or stderr is None:
        raise AutoresearchError(f"Command output decoder returned an invalid state: {log_path}")
    return CommandResult(
        command=command,
        returncode=process.returncode,
        stdout=stdout,
        stderr=stderr,
        duration_seconds=duration,
        log_path=log_path,
    )


def parse_metric_output(result: CommandResult, *, json_key: str | None) -> Decimal:
    if result.returncode != 0:
        raise AutoresearchError(
            f"Metric command exited {result.returncode}: {result.command}. Full output: {result.log_path}"
        )
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    if not lines:
        raise AutoresearchError(
            f"Metric command produced no non-empty stdout line. Full output: {result.log_path}"
        )
    final_line = lines[-1].strip()
    if json_key is None:
        return parse_decimal(final_line, field="metric command final stdout line")
    payload = parse_json(
        final_line,
        source=f"final stdout line from {result.command!r}",
        decimal_numbers=True,
    )
    if not isinstance(payload, dict):
        raise AutoresearchError("Metric JSON output must be an object")
    if json_key not in payload:
        raise AutoresearchError(f"Metric JSON output is missing key {json_key!r}")
    return parse_decimal(payload[json_key], field=f"metric JSON key {json_key!r}")


def improved(candidate: Decimal, retained: Decimal, direction: str) -> bool:
    return candidate < retained if direction == "lower" else candidate > retained


def target_reached(metric: Decimal, target: Decimal, direction: str) -> bool:
    return metric <= target if direction == "lower" else metric >= target


def relative_log_path(paths: Paths, path: Path | None) -> str | None:
    if path is None:
        return None
    return str(path.relative_to(paths.root))


def next_command_log(paths: Paths, iteration: int, kind: str) -> Path:
    return paths.logs / f"{iteration:04d}-{kind}.json"


def commit_trial(repo: Path, *, paths: list[str], description: str) -> str:
    title = " ".join(description.split())
    if not title:
        raise AutoresearchError("Iteration description cannot be empty")
    title = title[:64].rstrip()
    literal_paths = [f":(literal){path}" for path in paths]
    run_git(repo, "add", "-A", "--", *literal_paths)
    run_git(repo, "commit", "-m", f"autoresearch: {title}")
    remaining = working_paths(repo)
    if remaining:
        raise AutoresearchError(
            "Working tree changed while creating the trial commit: " + ", ".join(remaining)
        )
    return git_head(repo)


def revert_trial(repo: Path, trial_commit: str) -> str:
    run_git(repo, "revert", "--no-edit", trial_commit)
    remaining = working_paths(repo)
    if remaining:
        raise AutoresearchError("Rollback left uncommitted paths: " + ", ".join(remaining))
    return git_head(repo)


def process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def process_group_alive(process_group_id: int) -> bool:
    try:
        os.killpg(process_group_id, 0)
    except ProcessLookupError:
        return False
    return True


def terminate_process_tree(
    process: subprocess.Popen[Any],
    *,
    grace_seconds: float = 5.0,
) -> None:
    if os.name == "nt":
        if process.poll() is not None:
            return
        completed = subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="strict",
            check=False,
        )
        if completed.returncode != 0 and process.poll() is None:
            detail = (completed.stderr or completed.stdout).strip()
            raise AutoresearchError(
                f"Failed to terminate process tree {process.pid}: {detail or 'no output'}"
            )
        try:
            process.wait(timeout=grace_seconds)
            return
        except subprocess.TimeoutExpired:
            process.kill()
            try:
                process.wait(timeout=grace_seconds)
            except subprocess.TimeoutExpired as final_exc:
                raise AutoresearchError(
                    f"Process tree {process.pid} did not exit after forced termination"
                ) from final_exc
            return

    # Commands and workers start in their own session, so their process group is their tree.
    for stop_signal in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(process.pid, stop_signal)
        except ProcessLookupError:
            break
        deadline = time.monotonic() + grace_seconds
        while process_group_alive(process.pid) and time.monotonic() < deadline:
            process.poll()
            time.sleep(0.05)
        if not process_group_alive(process.pid):
            break
    try:
        process.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired as exc:
        raise AutoresearchError(f"Process {process.pid} did not exit after TERM and KILL") from exc


def load_runtime(paths: Paths, *, run_id: str | None = None) -> dict[str, Any] | None:
    if not paths.runtime.exists():
        return None
    try:
        text = paths.runtime.read_text(encoding="utf-8")
    except OSError as exc:
        raise AutoresearchError(f"Cannot read {paths.runtime}: {exc}") from exc
    payload = parse_json(text, source=str(paths.runtime))
    if not isinstance(payload, dict):
        raise AutoresearchError(f"{paths.runtime} must contain an object")
    require_exact_keys(
        payload,
        required={"run_id", "controller_pid", "child_pid", "state", "started_at", "updated_at"},
        source=str(paths.runtime),
    )
    if not isinstance(payload["run_id"], str) or not payload["run_id"]:
        raise AutoresearchError(f"{paths.runtime}.run_id must be a non-empty string")
    if run_id is not None and payload["run_id"] != run_id:
        raise AutoresearchError(
            f"{paths.runtime}.run_id does not match the active run: "
            f"{payload['run_id']} != {run_id}"
        )
    if payload["state"] not in {"starting", "running", "stopping", "stopped", "error"}:
        raise AutoresearchError(f"{paths.runtime}.state is invalid")
    for key in ("controller_pid", "child_pid"):
        if payload[key] is not None and (
            not isinstance(payload[key], int) or isinstance(payload[key], bool) or payload[key] <= 0
        ):
            raise AutoresearchError(f"{paths.runtime}.{key} must be null or a positive integer")
    return payload


def write_runtime(
    paths: Paths,
    run: dict[str, Any],
    *,
    controller_pid: int,
    child_pid: int | None,
    state: str,
    started_at: str,
) -> None:
    write_json_atomic(
        paths.runtime,
        {
            "run_id": run["run_id"],
            "controller_pid": controller_pid,
            "child_pid": child_pid,
            "state": state,
            "started_at": started_at,
            "updated_at": utc_now(),
        },
    )


def runtime_snapshot(paths: Paths, run: dict[str, Any], state: RunState) -> dict[str, Any]:
    runtime = load_runtime(paths, run_id=run["run_id"])
    if run["mode"] != "background":
        return {
            "state": "not_applicable",
            "controller_pid": None,
            "controller_alive": False,
            "child_pid": None,
            "child_alive": False,
        }
    if runtime is None:
        return {
            "state": "orphaned" if state.status == "active" else "not_started",
            "controller_pid": None,
            "controller_alive": False,
            "child_pid": None,
            "child_alive": False,
        }
    controller_pid = runtime["controller_pid"]
    child_pid = runtime["child_pid"]
    controller_alive = process_alive(controller_pid or 0)
    child_alive = process_alive(child_pid or 0)
    if state.status == "active" and not controller_alive:
        return {
            "state": "orphaned",
            "controller_pid": controller_pid,
            "controller_alive": False,
            "child_pid": child_pid,
            "child_alive": child_alive,
        }
    return {
        "state": runtime["state"],
        "controller_pid": controller_pid,
        "controller_alive": controller_alive,
        "child_pid": child_pid,
        "child_alive": child_alive,
    }


def status_payload(
    paths: Paths,
    run: dict[str, Any],
    events: list[dict[str, Any]],
    state: RunState,
) -> dict[str, Any]:
    return {
        "run_id": run["run_id"],
        "mode": run["mode"],
        "status": state.status,
        "goal": run["goal"],
        "repo": run["repo"],
        "branch": run["branch"],
        "scope": run["scope"],
        "metric": {
            "name": run["metric"]["name"],
            "direction": run["metric"]["direction"],
            "current": decimal_json(state.metric),
            "target": run["target"],
        },
        "iterations": state.iterations,
        "head": state.head,
        "last_event": state.last_event,
        "runtime": runtime_snapshot(paths, run, state),
        "events_path": str(paths.events),
        "runtime_log": str(paths.runtime_log) if run["mode"] == "background" else None,
        "event_count": len(events),
    }
