#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from autoresearch_core import print_json
from autoresearch_helpers import (
    ARTIFACT_DIR_NAME,
    AutoresearchError,
    LESSONS_FILE_NAME,
    default_lessons_path,
    utc_now,
)


HEADER_RE = re.compile(r"^### L-(\d+):\s*(.+?)\s*$")
FIELD_RE = re.compile(r"^- \*\*(Strategy|Outcome|Insight|Context|Iteration|Timestamp):\*\* (.+)$")
FIELD_NAME_MAP = {
    "Strategy": "strategy",
    "Outcome": "outcome",
    "Insight": "insight",
    "Context": "context",
    "Iteration": "iteration",
    "Timestamp": "timestamp",
}
REQUIRED_FIELDS = ("strategy", "outcome", "insight", "context", "iteration", "timestamp")
LESSON_OUTCOMES = ("keep", "discard", "crash", "pivot", "summary")
LESSONS_CAP_TARGET = 50
LESSON_DECAY_DAYS = 14
LESSON_SUMMARY_AGE_DAYS = 30
LESSON_SUMMARY_MIN_FAMILY_SIZE = 5


def lessons_path_from_results(results_path: Path) -> Path:
    return results_path.parent / LESSONS_FILE_NAME


def format_lesson_context(config: dict[str, Any]) -> str:
    goal = str(config.get("goal", "")).strip() or "-"
    scope = str(config.get("scope", "")).strip() or "-"
    metric = str(config.get("metric", "")).strip() or "-"
    direction = str(config.get("direction", "")).strip() or "-"
    return f"goal={goal}; scope={scope}; metric={metric}; direction={direction}"


def format_iteration_ref(run_tag: str | None, iteration: int | str | None) -> str:
    if iteration in {None, ""}:
        return "-"
    iteration_text = str(iteration)
    if run_tag:
        return f"{run_tag}#{iteration_text}"
    return iteration_text


def lesson_title_from_description(description: str) -> str:
    text = " ".join(description.strip().split())
    if not text:
        return "Autoresearch lesson"
    return text[:120]


def fallback_insight(outcome: str, description: str) -> str:
    if description.strip():
        return description.strip()
    if outcome == "keep":
        return "This strategy improved the retained metric and is worth reusing in similar contexts."
    if outcome == "pivot":
        return "This strategy family should be deprioritized in similar contexts."
    return "Capture the main lesson from this iteration."


def compact_text(value: Any) -> str:
    text = " ".join(str(value).split()).strip()
    return text or "-"


def parse_lesson_timestamp(value: str) -> datetime | None:
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def run_tag_from_iteration_ref(iteration_ref: str) -> str | None:
    text = iteration_ref.strip()
    if "#" not in text:
        return None
    run_tag = text.split("#", 1)[0].strip()
    return run_tag or None


def plain_iteration_number(iteration_ref: str) -> int | None:
    text = iteration_ref.strip()
    if not text or text == "-" or "#" in text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def strategy_family_key(strategy: str) -> str:
    text = compact_text(strategy)
    if text == "-":
        return ""
    text = re.sub(r"^\[[^\]]+\]\s*", "", text.lower())
    text = re.sub(r"\b[0-9a-f]{7,40}\b", "<commit>", text)
    text = re.sub(r"\b\d+\b", "<n>", text)
    text = text.replace("_", " ")
    text = re.sub(r"[^a-z0-9<>/ .-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" .-")
    if not text or text == "runtime completion summary":
        return ""
    words = text.split()
    return " ".join(words[:8])[:80]


def strategy_family_title(strategy: str) -> str:
    text = compact_text(strategy)
    text = re.sub(r"^\[[^\]]+\]\s*", "", text).strip(" .-")
    if not text or text == "-":
        return "Historical strategy family"
    words = text.split()
    return " ".join(words[:8])[:80]


def outcome_counts(entries: list[dict[str, str]]) -> dict[str, int]:
    counts = {outcome: 0 for outcome in LESSON_OUTCOMES}
    for entry in entries:
        outcome = entry.get("outcome", "")
        if outcome in counts:
            counts[outcome] += 1
    return counts


def keep_ratio_text(counts: dict[str, int]) -> str:
    denominator = counts["keep"] + counts["discard"] + counts["crash"]
    if denominator == 0:
        return "n/a"
    ratio = counts["keep"] / denominator
    return f"{counts['keep']}/{denominator} ({ratio:.0%})"


def renumber_entries(entries: list[dict[str, str]]) -> list[dict[str, str]]:
    renumbered: list[dict[str, str]] = []
    for index, entry in enumerate(entries, start=1):
        updated = dict(entry)
        updated["id"] = f"L-{index}"
        updated["number"] = str(index)
        renumbered.append(updated)
    return renumbered


def write_entries(lessons_path: Path, entries: list[dict[str, str]]) -> list[dict[str, str]]:
    numbered = renumber_entries(entries)
    if not numbered:
        if lessons_path.exists():
            lessons_path.unlink()
        return []
    lines: list[str] = []
    for entry in numbered:
        lines.extend(
            [
                f"### {entry['id']}: {compact_text(entry['title'])}",
                f"- **Strategy:** {compact_text(entry['strategy'])}",
                f"- **Outcome:** {entry['outcome']}",
                f"- **Insight:** {compact_text(entry['insight'])}",
                f"- **Context:** {compact_text(entry['context'])}",
                f"- **Iteration:** {compact_text(entry['iteration'])}",
                f"- **Timestamp:** {compact_text(entry['timestamp'])}",
                "",
            ]
        )
    lessons_path.write_text("\n".join(lines), encoding="utf-8")
    return numbered


def build_family_summary_entry(entries: list[dict[str, str]], *, timestamp: str) -> dict[str, str]:
    latest = entries[-1]
    counts = outcome_counts(entries)
    family_title = strategy_family_title(latest.get("strategy", ""))
    return {
        "title": lesson_title_from_description(f"Family summary: {family_title}"),
        "strategy": f"Consolidated strategy family: {family_title}",
        "outcome": "summary",
        "insight": (
            f"Compacted {len(entries)} historical lessons; keep_ratio={keep_ratio_text(counts)}; "
            f"keep={counts['keep']}, discard={counts['discard']}, crash={counts['crash']}, "
            f"pivot={counts['pivot']}. Latest signal: {compact_text(latest.get('insight', '-'))}"
        ),
        "context": (
            f"historical_compaction; latest_context={compact_text(latest.get('context', '-'))}; "
            f"weight=reduce_after_{LESSON_DECAY_DAYS}d"
        ),
        "iteration": "-",
        "timestamp": timestamp,
    }


def build_rollup_summary_entry(entries: list[dict[str, str]], *, timestamp: str) -> dict[str, str]:
    counts = outcome_counts(entries)
    families = {
        strategy_family_key(entry.get("strategy", ""))
        for entry in entries
        if strategy_family_key(entry.get("strategy", ""))
    }
    return {
        "title": lesson_title_from_description(f"Historical summary: {len(entries)} archived lessons"),
        "strategy": "Historical lesson rollup",
        "outcome": "summary",
        "insight": (
            f"Compacted {len(entries)} older lessons across {max(1, len(families))} strategy families; "
            f"keep_ratio={keep_ratio_text(counts)}. Older signals should be weighted lower after "
            f"{LESSON_DECAY_DAYS} days."
        ),
        "context": "historical_compaction; archived_entries=rolled_up",
        "iteration": "-",
        "timestamp": timestamp,
    }


def compact_historical_families(
    historical_entries: list[dict[str, str]],
    *,
    reference_time: datetime,
    timestamp: str,
) -> list[dict[str, str]]:
    grouped_indices: dict[str, list[int]] = {}
    for index, entry in enumerate(historical_entries):
        if entry.get("outcome") == "summary":
            continue
        entry_timestamp = parse_lesson_timestamp(entry.get("timestamp", ""))
        if entry_timestamp is None:
            continue
        if reference_time - entry_timestamp < timedelta(days=LESSON_SUMMARY_AGE_DAYS):
            continue
        family = strategy_family_key(entry.get("strategy", ""))
        if not family:
            continue
        grouped_indices.setdefault(family, []).append(index)

    removable: set[int] = set()
    summary_entries: list[dict[str, str]] = []
    for indices in sorted(grouped_indices.values(), key=lambda values: values[0]):
        if len(indices) < LESSON_SUMMARY_MIN_FAMILY_SIZE:
            continue
        removable.update(indices)
        summary_entries.append(
            build_family_summary_entry(
                [historical_entries[index] for index in indices],
                timestamp=timestamp,
            )
        )

    if not removable:
        return historical_entries
    kept = [entry for index, entry in enumerate(historical_entries) if index not in removable]
    return kept + summary_entries


def cap_historical_entries(
    historical_entries: list[dict[str, str]],
    *,
    timestamp: str,
) -> list[dict[str, str]]:
    if len(historical_entries) <= LESSONS_CAP_TARGET:
        return historical_entries
    overflow = len(historical_entries) - LESSONS_CAP_TARGET + 1
    oldest_entries = historical_entries[:overflow]
    return [build_rollup_summary_entry(oldest_entries, timestamp=timestamp)] + historical_entries[overflow:]


def split_current_run_entries(entries: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    if not entries:
        return [], []

    last_iteration = compact_text(entries[-1].get("iteration", ""))
    current_run_tag = run_tag_from_iteration_ref(last_iteration)
    if current_run_tag is not None:
        start = len(entries) - 1
        while start > 0:
            previous_iteration = compact_text(entries[start - 1].get("iteration", ""))
            if run_tag_from_iteration_ref(previous_iteration) != current_run_tag:
                break
            start -= 1
        return entries[:start], entries[start:]

    current_iteration = plain_iteration_number(last_iteration)
    if current_iteration is None:
        return entries, []

    start = len(entries) - 1
    current_outcome = str(entries[-1].get("outcome", "")).strip()
    while start > 0:
        previous = entries[start - 1]
        previous_iteration = compact_text(previous.get("iteration", ""))
        if run_tag_from_iteration_ref(previous_iteration) is not None:
            break
        previous_number = plain_iteration_number(previous_iteration)
        if previous_number is None:
            break
        same_iteration_summary = previous_number == current_iteration and (
            previous.get("outcome") == "summary" or current_outcome == "summary"
        )
        if previous_number < current_iteration or same_iteration_summary:
            start -= 1
            current_iteration = previous_number
            current_outcome = str(previous.get("outcome", "")).strip()
            continue
        break
    return entries[:start], entries[start:]


def compact_entries(entries: list[dict[str, str]], *, timestamp: str) -> list[dict[str, str]]:
    if len(entries) <= LESSONS_CAP_TARGET:
        return renumber_entries(entries)
    historical_entries, current_run_entries = split_current_run_entries(entries)
    historical_entries = [dict(entry) for entry in historical_entries]
    current_run_entries = [dict(entry) for entry in current_run_entries]

    reference_time = parse_lesson_timestamp(timestamp) or datetime.now(timezone.utc)
    historical_entries = compact_historical_families(
        historical_entries,
        reference_time=reference_time,
        timestamp=timestamp,
    )
    historical_entries = cap_historical_entries(historical_entries, timestamp=timestamp)
    return renumber_entries(historical_entries + current_run_entries)


def find_entry(entries: list[dict[str, str]], probe: dict[str, str]) -> dict[str, str]:
    for entry in reversed(entries):
        if all(entry.get(field) == probe[field] for field in REQUIRED_FIELDS):
            if entry.get("title") == probe["title"] and entry.get("outcome") == probe["outcome"]:
                return entry
    raise AutoresearchError("Newly appended lesson was lost during compaction.")


def parse_lesson_entries(lessons_path: Path) -> list[dict[str, str]]:
    if not lessons_path.exists():
        return []

    entries: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw_line in lessons_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line:
            continue
        header = HEADER_RE.match(line)
        if header is not None:
            if current is not None:
                missing = [field for field in REQUIRED_FIELDS if field not in current]
                if missing:
                    raise AutoresearchError(
                        f"Lesson {current['id']} is missing required fields: {', '.join(missing)}"
                    )
                entries.append(current)
            current = {
                "id": f"L-{header.group(1)}",
                "number": header.group(1),
                "title": header.group(2).strip(),
            }
            continue
        if current is None:
            raise AutoresearchError("Lessons file contains content before the first lesson header.")
        field = FIELD_RE.match(line)
        if field is None:
            raise AutoresearchError(f"Unparseable lesson line: {line!r}")
        current[FIELD_NAME_MAP[field.group(1)]] = field.group(2).strip()

    if current is not None:
        missing = [field for field in REQUIRED_FIELDS if field not in current]
        if missing:
            raise AutoresearchError(
                f"Lesson {current['id']} is missing required fields: {', '.join(missing)}"
            )
        entries.append(current)
    return entries


def backup_corrupt_lessons_file(lessons_path: Path) -> Path:
    backup_path = lessons_path.with_name(f"{lessons_path.name}.{utc_now().replace(':', '-')}.bak")
    lessons_path.rename(backup_path)
    return backup_path


def load_entries_for_append(lessons_path: Path) -> list[dict[str, str]]:
    if not lessons_path.exists():
        return []
    try:
        return parse_lesson_entries(lessons_path)
    except AutoresearchError:
        backup_corrupt_lessons_file(lessons_path)
        return []


def list_entries_with_recovery(lessons_path: Path) -> list[dict[str, str]]:
    return load_entries_for_append(lessons_path)


def append_lesson(
    *,
    lessons_path: Path,
    title: str,
    strategy: str,
    outcome: str,
    insight: str,
    context: str,
    iteration: str,
    timestamp: str | None = None,
) -> dict[str, Any]:
    if outcome not in LESSON_OUTCOMES:
        raise AutoresearchError(f"Unsupported lesson outcome: {outcome}")

    lessons_path.parent.mkdir(parents=True, exist_ok=True)
    entries = load_entries_for_append(lessons_path)
    entry_timestamp = compact_text(timestamp or utc_now())
    new_entry = {
        "title": compact_text(title),
        "strategy": compact_text(strategy),
        "outcome": outcome,
        "insight": compact_text(insight),
        "context": compact_text(context),
        "iteration": compact_text(iteration.strip() or "-"),
        "timestamp": entry_timestamp,
    }
    written_entries = write_entries(
        lessons_path,
        compact_entries(entries + [new_entry], timestamp=entry_timestamp),
    )
    written_entry = find_entry(written_entries, new_entry)
    return {
        "lessons_path": str(lessons_path),
        "id": written_entry["id"],
        "title": new_entry["title"],
        "outcome": outcome,
        "iteration": new_entry["iteration"],
    }


def append_iteration_lesson(
    *,
    lessons_path: Path,
    state_payload: dict[str, Any],
    status: str,
    description: str,
    iteration: int,
) -> dict[str, Any] | None:
    if state_payload.get("mode") == "exec" or status not in {"keep", "pivot"}:
        return None
    config = state_payload.get("config", {})
    return append_lesson(
        lessons_path=lessons_path,
        title=lesson_title_from_description(description),
        strategy=description.strip() or f"{status} iteration {iteration}",
        outcome=status,
        insight=fallback_insight(status, description),
        context=format_lesson_context(config),
        iteration=format_iteration_ref(state_payload.get("run_tag"), iteration),
    )


def parse_iteration_number(iteration_ref: str, run_tag: str | None) -> int | None:
    if not iteration_ref or iteration_ref == "-":
        return None
    if run_tag and iteration_ref.startswith(f"{run_tag}#"):
        suffix = iteration_ref.split("#", 1)[1]
    elif "#" in iteration_ref:
        return None
    else:
        suffix = iteration_ref
    try:
        return int(suffix)
    except ValueError:
        return None


def append_summary_lesson_if_needed(
    *,
    lessons_path: Path,
    state_payload: dict[str, Any],
    current_iteration: int,
) -> dict[str, Any] | None:
    if state_payload.get("mode") == "exec":
        return None

    run_tag = str(state_payload.get("run_tag") or "").strip() or None
    entries = load_entries_for_append(lessons_path)
    if run_tag is None:
        for entry in reversed(entries):
            if entry.get("outcome") == "summary" and entry.get("iteration") == str(current_iteration):
                return None
        entries = []
    for entry in reversed(entries):
        iteration_number = parse_iteration_number(entry.get("iteration", ""), run_tag)
        if iteration_number is None:
            continue
        if current_iteration - iteration_number <= 5:
            return None
        break

    config = state_payload.get("config", {})
    state = state_payload.get("state", {})
    best_metric = state.get("best_metric", state.get("current_metric", "-"))
    best_iteration = state.get("best_iteration", state.get("iteration", current_iteration))
    last_status = state.get("last_status", "-")
    return append_lesson(
        lessons_path=lessons_path,
        title=f"Run summary: {str(config.get('goal', 'Autoresearch run')).strip() or 'Autoresearch run'}",
        strategy="Runtime completion summary",
        outcome="summary",
        insight=(
            f"Best retained metric {best_metric} at iteration {best_iteration}; "
            f"the run ended with status {last_status}."
        ),
        context=format_lesson_context(config),
        iteration=format_iteration_ref(run_tag, current_iteration),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Append or inspect protocol-aligned autoresearch lessons."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    append = subparsers.add_parser("append")
    append.add_argument("--lessons-path", default=str(default_lessons_path()), help=argparse.SUPPRESS)
    append.add_argument("--title", required=True)
    append.add_argument("--strategy", required=True)
    append.add_argument("--outcome", required=True, choices=LESSON_OUTCOMES)
    append.add_argument("--insight", required=True)
    append.add_argument("--context", required=True)
    append.add_argument("--iteration", required=True)
    append.add_argument("--timestamp")

    show = subparsers.add_parser("list")
    show.add_argument("--lessons-path", default=str(default_lessons_path()), help=argparse.SUPPRESS)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "append":
        print_json(
            append_lesson(
                lessons_path=Path(args.lessons_path),
                title=args.title,
                strategy=args.strategy,
                outcome=args.outcome,
                insight=args.insight,
                context=args.context,
                iteration=args.iteration,
                timestamp=args.timestamp,
            )
        )
        return 0
    if args.command == "list":
        print_json(list_entries_with_recovery(Path(args.lessons_path)))
        return 0
    raise AutoresearchError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutoresearchError as exc:
        raise SystemExit(f"error: {exc}")
