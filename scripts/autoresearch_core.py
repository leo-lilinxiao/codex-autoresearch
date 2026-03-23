#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import shlex
import shutil
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
SESSION_MODE_CHOICES = ("foreground", "background")
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
    "consecutive_discards",
    "pivot_count",
    "last_status",
}
ENV_ASSIGNMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=.*$")


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


def improvement(metric: Decimal, reference: Decimal, direction: str) -> bool:
    if direction == "lower":
        return metric < reference
    if direction == "higher":
        return metric > reference
    raise AutoresearchError(f"Unsupported direction: {direction}")


def command_is_executable(command: str) -> bool:
    if not command.strip():
        return False
    try:
        parts = shlex.split(command)
    except ValueError:
        return False
    if not parts:
        return False

    executable = ""
    for part in parts:
        if ENV_ASSIGNMENT_RE.fullmatch(part):
            continue
        executable = part
        break
    if not executable:
        return False

    candidate = Path(executable)
    if candidate.is_absolute() or "/" in executable or "\\" in executable:
        return candidate.is_file() and os.access(candidate, os.X_OK)
    return shutil.which(executable) is not None
