#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from autoresearch_helpers import AutoresearchError, is_autoresearch_owned_artifact


def git_lines(repo: Path, *args: str) -> list[str]:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise AutoresearchError(completed.stderr.strip() or f"git {' '.join(args)} failed")
    return [line.rstrip() for line in completed.stdout.splitlines() if line.strip()]


def evaluate_commit_gate(
    *,
    repo: Path,
    phase: str,
    rollback_policy: str | None,
    destructive_approved: bool,
) -> dict[str, Any]:
    status_lines = git_lines(repo, "status", "--porcelain")
    staged_files = git_lines(repo, "diff", "--cached", "--name-only")
    unexpected_worktree = []
    staged_artifacts = []

    for line in status_lines:
        raw_path = line[3:] if len(line) > 3 else line
        if " -> " in raw_path:
            raw_path = raw_path.split(" -> ", 1)[1]
        if not is_autoresearch_owned_artifact(raw_path):
            unexpected_worktree.append(raw_path)

    for path in staged_files:
        if is_autoresearch_owned_artifact(path):
            staged_artifacts.append(path)

    blockers: list[str] = []
    warnings: list[str] = []
    if phase == "prelaunch" and unexpected_worktree:
        blockers.append("unexpected worktree changes before launch: " + ", ".join(sorted(unexpected_worktree)))
    elif unexpected_worktree:
        warnings.append("unexpected worktree changes: " + ", ".join(sorted(unexpected_worktree)))

    if staged_artifacts:
        blockers.append("autoresearch-owned artifacts are staged: " + ", ".join(sorted(staged_artifacts)))

    if rollback_policy == "destructive" and not destructive_approved:
        blockers.append("destructive rollback requested without prior approval")

    decision = "allow"
    if blockers:
        decision = "block"
    elif warnings:
        decision = "warn"
    return {
        "decision": decision,
        "phase": phase,
        "rollback_policy": rollback_policy or "",
        "destructive_approved": destructive_approved,
        "unexpected_worktree": sorted(unexpected_worktree),
        "staged_artifacts": sorted(staged_artifacts),
        "warnings": warnings,
        "blockers": blockers,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate git cleanliness and artifact staging rules for autoresearch."
    )
    parser.add_argument("--repo", default=".")
    parser.add_argument("--phase", choices=["prelaunch", "precommit", "rollback"], default="precommit")
    parser.add_argument("--rollback-policy")
    parser.add_argument("--destructive-approved", action="store_true")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    output = evaluate_commit_gate(
        repo=Path(args.repo).resolve(),
        phase=args.phase,
        rollback_policy=args.rollback_policy,
        destructive_approved=args.destructive_approved,
    )
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutoresearchError as exc:
        raise SystemExit(f"error: {exc}")
