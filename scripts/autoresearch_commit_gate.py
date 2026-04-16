#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from autoresearch_core import print_json
from autoresearch_helpers import (
    AutoresearchError,
    RepoTarget,
    build_repo_targets,
    format_repo_target_label,
    git_status_entries,
    has_git_repo,
    is_autoresearch_owned_artifact,
    parse_scope_patterns,
    path_is_in_scope,
)


def evaluate_commit_gate(
    *,
    repo: Path,
    phase: str,
    rollback_policy: str | None,
    destructive_approved: bool,
    scope_text: str | None = None,
) -> dict[str, Any]:
    scope_patterns = parse_scope_patterns(scope_text)
    if not has_git_repo(repo):
        return {
            "decision": "skipped",
            "phase": phase,
            "rollback_policy": rollback_policy or "",
            "destructive_approved": destructive_approved,
            "scope_patterns": scope_patterns,
            "unexpected_worktree": [],
            "staged_artifacts": [],
            "warnings": [],
            "blockers": [],
        }

    status_entries = git_status_entries(repo)
    unexpected_worktree = []
    staged_artifacts = []
    phase_labels = {
        "prelaunch": "before launch",
        "precommit": "before commit",
        "prebatch": "before parallel batch",
    }

    for entry in status_entries:
        for raw_path in entry.touched_paths:
            if not is_autoresearch_owned_artifact(raw_path) and not path_is_in_scope(raw_path, scope_patterns):
                unexpected_worktree.append(raw_path)
            if entry.has_staged_change and is_autoresearch_owned_artifact(raw_path):
                staged_artifacts.append(raw_path)

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


def evaluate_multi_repo_commit_gate(
    *,
    primary_repo: Path,
    primary_scope_text: str | None,
    repo_targets: list[RepoTarget] | None = None,
    companion_repo_scopes: list[str] | None = None,
    phase: str,
    rollback_policy: str | None,
    destructive_approved: bool,
) -> dict[str, Any]:
    if repo_targets is not None:
        targets = repo_targets
    elif companion_repo_scopes:
        if not str(primary_scope_text or "").strip():
            raise AutoresearchError("A primary --scope is required when using --companion-repo-scope.")
        targets = build_repo_targets(
            primary_repo=primary_repo,
            primary_scope=str(primary_scope_text or ""),
            companion_repo_scopes=list(companion_repo_scopes or []),
        )
    else:
        targets = [RepoTarget(path=Path(primary_repo).resolve(), scope=str(primary_scope_text or ""), role="primary")]
    primary_repo = Path(primary_repo).resolve()
    repo_gates: list[dict[str, Any]] = []
    blockers: list[str] = []
    warnings: list[str] = []
    primary_gate: dict[str, Any] | None = None

    for target in targets:
        gate = evaluate_commit_gate(
            repo=target.path,
            phase=phase,
            rollback_policy=rollback_policy,
            destructive_approved=destructive_approved,
            scope_text=target.scope,
        )
        repo_gate = dict(gate)
        repo_gate["repo"] = str(target.path)
        repo_gate["role"] = target.role
        repo_gates.append(repo_gate)
        label = format_repo_target_label(target, primary_repo)
        blockers.extend(f"[{label}] {message}" for message in gate["blockers"])
        warnings.extend(f"[{label}] {message}" for message in gate["warnings"])
        if target.role == "primary":
            primary_gate = gate

    if primary_gate is None:
        raise AutoresearchError("Multi-repo commit gate requires one primary repo target.")

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
        "scope_patterns": primary_gate["scope_patterns"],
        "unexpected_worktree": primary_gate["unexpected_worktree"],
        "staged_artifacts": primary_gate["staged_artifacts"],
        "warnings": warnings,
        "blockers": blockers,
        "repo_gates": repo_gates,
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
    parser.add_argument(
        "--companion-repo-scope",
        action="append",
        default=[],
        help="Allow edits in a companion repo using PATH=SCOPE. May be repeated.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    output = evaluate_multi_repo_commit_gate(
        primary_repo=repo,
        primary_scope_text=args.scope,
        companion_repo_scopes=args.companion_repo_scope,
        phase=args.phase,
        rollback_policy=args.rollback_policy,
        destructive_approved=args.destructive_approved,
    )
    print_json(output)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutoresearchError as exc:
        raise SystemExit(f"error: {exc}")
