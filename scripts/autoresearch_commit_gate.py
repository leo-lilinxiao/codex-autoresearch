#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any

from autoresearch_helpers import (
    AutoresearchError,
    git_status_paths,
    is_autoresearch_owned_artifact,
)


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


def parse_scope_patterns(scope_text: str | None) -> list[str]:
    if not scope_text:
        return []
    return [token for token in re.split(r"[\s,]+", scope_text.strip()) if token]


def path_is_in_scope(path: str, patterns: list[str]) -> bool:
    if not patterns:
        return False
    normalized = path.replace("\\", "/")
    candidate = PurePosixPath(normalized)
    for pattern in patterns:
        pattern = pattern.strip()
        if not pattern:
            continue
        variants = {pattern.replace("\\", "/").lstrip("./")}
        while True:
            expanded = {variant.replace("**/", "") for variant in variants if "**/" in variant}
            expanded -= variants
            if not expanded:
                break
            variants |= expanded
        if any(candidate.match(variant) for variant in variants):
            return True
    return False


def evaluate_commit_gate(
    *,
    repo: Path,
    phase: str,
    rollback_policy: str | None,
    destructive_approved: bool,
    scope_text: str | None = None,
) -> dict[str, Any]:
    status_lines = git_status_paths(repo)
    staged_files = git_lines(repo, "diff", "--cached", "--name-only")
    unexpected_worktree = []
    staged_artifacts = []
    scope_patterns = parse_scope_patterns(scope_text)
    phase_labels = {
        "prelaunch": "before launch",
        "precommit": "before commit",
        "prebatch": "before parallel batch",
    }

    for raw_path in status_lines:
        if not is_autoresearch_owned_artifact(raw_path) and not path_is_in_scope(raw_path, scope_patterns):
            unexpected_worktree.append(raw_path)

    for path in staged_files:
        if is_autoresearch_owned_artifact(path):
            staged_artifacts.append(path)

    blockers: list[str] = []
    warnings: list[str] = []
    if phase in phase_labels and unexpected_worktree:
        label = phase_labels[phase]
        blockers.append(
            f"unexpected worktree changes {label}: " + ", ".join(sorted(unexpected_worktree))
        )
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
        "scope_patterns": scope_patterns,
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
    parser.add_argument(
        "--phase",
        choices=["prelaunch", "precommit", "prebatch", "rollback"],
        default="precommit",
    )
    parser.add_argument("--rollback-policy")
    parser.add_argument("--destructive-approved", action="store_true")
    parser.add_argument("--scope")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    output = evaluate_commit_gate(
        repo=Path(args.repo).resolve(),
        phase=args.phase,
        rollback_policy=args.rollback_policy,
        destructive_approved=args.destructive_approved,
        scope_text=args.scope,
    )
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutoresearchError as exc:
        raise SystemExit(f"error: {exc}")
