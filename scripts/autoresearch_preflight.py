#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Any

from autoresearch_commit_gate import evaluate_commit_gate, evaluate_multi_repo_commit_gate
from autoresearch_health_check import run_health_check
from autoresearch_helpers import RepoTarget, has_git_repo


def skipped_health_check(*, results_path: Path, state_path_arg: str | None) -> dict[str, Any]:
    return {
        "decision": "skipped",
        "warnings": [],
        "blockers": [],
        "free_mb": None,
        "results_path": str(results_path),
        "state_path": state_path_arg or "",
        "has_results": False,
        "has_state": False,
        "main_rows": 0,
        "resume_decision": "skipped",
        "resume_detail": "skipped",
    }


def skipped_commit_gate(
    *,
    phase: str,
    rollback_policy: str | None,
    destructive_approved: bool,
) -> dict[str, Any]:
    return {
        "decision": "skipped",
        "phase": phase,
        "rollback_policy": rollback_policy or "",
        "destructive_approved": destructive_approved,
        "scope_patterns": [],
        "unexpected_worktree": [],
        "staged_artifacts": [],
        "warnings": [],
        "blockers": [],
    }


def evaluate_repo_preflight(
    *,
    repo: Path,
    workspace_root: Path | None,
    results_path: Path,
    state_path_arg: str | None,
    verify_command: str,
    verify_cwd: str,
    scope_text: str | None,
    commit_phase: str,
    min_free_mb: int = 500,
    include_health: bool = True,
    rollback_policy: str | None = None,
    destructive_approved: bool = False,
) -> dict[str, Any]:
    health = (
        run_health_check(
            repo=repo,
            workspace_root=workspace_root,
            results_path=results_path,
            state_path_arg=state_path_arg,
            verify_command=verify_command,
            verify_cwd=verify_cwd,
            scope_text=scope_text,
            min_free_mb=min_free_mb,
        )
        if include_health
        else skipped_health_check(results_path=results_path, state_path_arg=state_path_arg)
    )
    commit_gate = (
        evaluate_commit_gate(
            repo=repo,
            phase=commit_phase,
            rollback_policy=rollback_policy,
            destructive_approved=destructive_approved,
            scope_text=scope_text,
        )
        if has_git_repo(repo)
        else skipped_commit_gate(
            phase=commit_phase,
            rollback_policy=rollback_policy,
            destructive_approved=destructive_approved,
        )
    )

    blockers = list(commit_gate.get("blockers", [])) + list(health.get("blockers", []))
    warnings = list(commit_gate.get("warnings", [])) + list(health.get("warnings", []))
    decision = "allow"
    reason = "preflight_ok"
    if blockers:
        decision = "block"
        reason = "preflight_blocked"
    elif warnings:
        decision = "warn"
        reason = "preflight_warn"
    return {
        "decision": decision,
        "reason": reason,
        "warnings": warnings,
        "blockers": blockers,
        "health_check": health,
        "commit_gate": commit_gate,
    }


def evaluate_managed_repos_preflight(
    *,
    primary_repo: Path,
    workspace_root: Path | None,
    results_path: Path,
    state_path_arg: str | None,
    verify_command: str,
    verify_cwd: str,
    commit_phase: str,
    repo_targets: list[RepoTarget],
    min_free_mb: int = 500,
    include_health: bool = True,
    rollback_policy: str | None = None,
    destructive_approved: bool = False,
) -> dict[str, Any]:
    if not repo_targets:
        raise ValueError("repo_targets may not be empty")

    primary_targets = [target for target in repo_targets if target.role == "primary"]
    if len(primary_targets) != 1:
        raise ValueError("repo_targets must contain exactly one primary repo")
    primary_target = primary_targets[0]

    health = (
        run_health_check(
            repo=primary_repo,
            workspace_root=workspace_root,
            results_path=results_path,
            state_path_arg=state_path_arg,
            verify_command=verify_command,
            verify_cwd=verify_cwd,
            scope_text=primary_target.scope,
            min_free_mb=min_free_mb,
            companion_targets=[target for target in repo_targets if target.role != "primary"],
        )
        if include_health
        else skipped_health_check(results_path=results_path, state_path_arg=state_path_arg)
    )

    commit_gate = evaluate_multi_repo_commit_gate(
        primary_repo=primary_repo,
        primary_scope_text=primary_target.scope,
        repo_targets=repo_targets,
        phase=commit_phase,
        rollback_policy=rollback_policy,
        destructive_approved=destructive_approved,
    )

    blockers = list(commit_gate.get("blockers", [])) + list(health.get("blockers", []))
    warnings = list(commit_gate.get("warnings", [])) + list(health.get("warnings", []))
    decision = "allow"
    reason = "preflight_ok"
    if blockers:
        decision = "block"
        reason = "preflight_blocked"
    elif warnings:
        decision = "warn"
        reason = "preflight_warn"
    return {
        "decision": decision,
        "reason": reason,
        "warnings": warnings,
        "blockers": blockers,
        "health_check": health,
        "commit_gate": commit_gate,
        "repo_targets": [
            {"path": str(target.path), "scope": target.scope, "role": target.role}
            for target in repo_targets
        ],
    }
