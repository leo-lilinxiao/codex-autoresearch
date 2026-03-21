#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any

from autoresearch_helpers import (
    AutoresearchError,
    is_autoresearch_owned_artifact,
    parse_log_metadata,
    parse_results_log,
    read_state_payload,
    resolve_state_path,
)


def git_status(repo: Path) -> list[str]:
    completed = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise AutoresearchError(completed.stderr.strip() or "git status failed")
    return [line.rstrip() for line in completed.stdout.splitlines() if line.strip()]


def verify_command_exists(command: str) -> bool:
    if not command.strip():
        return False
    try:
        parts = shlex.split(command)
    except ValueError:
        return False
    if not parts:
        return False
    executable = parts[0]
    if executable in {"bash", "sh", "python", "python3"}:
        return True
    return shutil.which(executable) is not None


def run_health_check(
    *,
    repo: Path,
    results_path: Path,
    state_path_arg: str | None,
    verify_command: str,
    min_free_mb: int,
) -> dict[str, Any]:
    warnings: list[str] = []
    blockers: list[str] = []

    free_mb = shutil.disk_usage(repo).free // (1024 * 1024)
    if free_mb < min_free_mb:
        blockers.append(f"disk free space below threshold: {free_mb}MB < {min_free_mb}MB")
    elif free_mb < max(min_free_mb * 2, 1000):
        warnings.append(f"disk free space is getting low: {free_mb}MB")

    if results_path.exists():
        try:
            parsed = parse_results_log(results_path)
            metadata = parsed.metadata
        except AutoresearchError as exc:
            parsed = None
            metadata = parse_log_metadata(results_path)
            blockers.append(f"results log is corrupt: {exc}")
    else:
        parsed = None
        metadata = {}

    log_mode = metadata.get("mode")
    exec_mode = log_mode == "exec"
    state_path = resolve_state_path(
        state_path_arg,
        mode="exec" if exec_mode else None,
        cwd=repo,
        allow_exec_scratch_fallback=exec_mode,
    )

    if not results_path.exists() and state_path.exists():
        blockers.append("results log missing while state JSON exists; cannot track progress")
    elif state_path.exists():
        try:
            read_state_payload(state_path)
        except AutoresearchError as exc:
            blockers.append(f"state JSON is corrupt: {exc}")
    elif results_path.exists():
        warnings.append("results log exists without state JSON; resume would need TSV fallback")

    dirty_lines = git_status(repo)
    unexpected = []
    for line in dirty_lines:
        path = line[3:] if len(line) > 3 else line
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if not is_autoresearch_owned_artifact(path):
            unexpected.append(path)
    if unexpected:
        warnings.append("unexpected worktree changes: " + ", ".join(sorted(unexpected)))

    if not verify_command_exists(verify_command):
        blockers.append(f"verify command is not executable: {verify_command}")

    decision = "ok"
    if blockers:
        decision = "block"
    elif warnings:
        decision = "warn"

    return {
        "decision": decision,
        "warnings": warnings,
        "blockers": blockers,
        "free_mb": free_mb,
        "results_path": str(results_path),
        "state_path": str(state_path),
        "has_results": results_path.exists(),
        "has_state": state_path.exists(),
        "main_rows": len(parsed.main_rows) if parsed is not None else 0,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the executable health checks for an autoresearch repo."
    )
    parser.add_argument("--repo", default=".")
    parser.add_argument("--results-path", default="research-results.tsv")
    parser.add_argument("--state-path")
    parser.add_argument("--verify-cmd", required=True)
    parser.add_argument("--min-free-mb", type=int, default=500)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    results_path = Path(args.results_path)
    if not results_path.is_absolute():
        results_path = repo / results_path
    output = run_health_check(
        repo=repo,
        results_path=results_path.resolve(),
        state_path_arg=args.state_path,
        verify_command=args.verify_cmd,
        min_free_mb=args.min_free_mb,
    )
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutoresearchError as exc:
        raise SystemExit(f"error: {exc}")
