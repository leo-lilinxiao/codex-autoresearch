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
STRUCTURED_LABEL_RE = re.compile(r"^[a-z0-9][a-z0-9._/-]*$")
STRUCTURED_LABEL_PREFIX_RE = re.compile(
    r"^\[labels:\s*([A-Za-z0-9._/-]+(?:\s*,\s*[A-Za-z0-9._/-]+)*)\]\s*",
    re.IGNORECASE,
)
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
    labels: tuple[str, ...] = ()

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


def normalize_labels(values: Any) -> list[str]:
    if values in (None, "", []):
        return []

    if isinstance(values, str):
        raw_values = [values]
    else:
        try:
            raw_values = list(values)
        except TypeError as exc:
            raise AutoresearchError(f"Invalid labels value: {values!r}") from exc

    normalized: list[str] = []
    seen: set[str] = set()
    for raw in raw_values:
        if not isinstance(raw, str):
            raise AutoresearchError(f"Invalid label: {raw!r}")
        for piece in raw.split(","):
            label = piece.strip().lower()
            if not label:
                continue
            if not STRUCTURED_LABEL_RE.fullmatch(label):
                raise AutoresearchError(
                    "Invalid label "
                    f"{raw!r}; labels must match {STRUCTURED_LABEL_RE.pattern!r}."
                )
            if label not in seen:
                seen.add(label)
                normalized.append(label)
    return normalized


def split_labels_from_description(description: str) -> tuple[list[str], str]:
    text = str(description).strip()
    if not text.lower().startswith("[labels:"):
        return [], text
    match = STRUCTURED_LABEL_PREFIX_RE.match(text)
    if match is None:
        raise AutoresearchError(f"Malformed label prefix in description: {description!r}")
    labels = normalize_labels(match.group(1).split(","))
    remainder = text[match.end() :].lstrip()
    if not remainder:
        raise AutoresearchError("A structured label prefix must be followed by a description.")
    return labels, remainder


def format_description_with_labels(description: str, labels: Any) -> str:
    existing_labels, base_description = split_labels_from_description(description)
    normalized = normalize_labels([*existing_labels, *normalize_labels(labels)])
    if not normalized:
        return base_description
    return f"[labels: {', '.join(normalized)}] {base_description}"
