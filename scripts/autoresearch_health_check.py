#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Any

from autoresearch_core import print_json
from autoresearch_helpers import (
    AutoresearchError,
    RepoTarget,
    build_repo_targets,
    format_repo_target_label,
    git_status_paths,
    has_git_repo,
    is_autoresearch_owned_artifact,
    lexical_abspath,
    parse_scope_patterns,
    path_is_in_scope,
    require_context_for_repo,
    resolve_context_workspace_root,
    resolve_repo_path,
    resolve_repo_relative,
    STATE_FILE_NAME,
)
from autoresearch_platform import command_is_executable
from autoresearch_resume_check import evaluate_resume_state
from autoresearch_workspace import resolve_workspace_root


def run_health_check(
    *,
    repo: Path,
    workspace_root: Path | None,
    results_path: Path,
    state_path_arg: str | None,
    verify_command: str,
    verify_cwd: str,
    scope_text: str | None,
    min_free_mb: int,
    default_state_path: Path | None = None,
    companion_targets: list[RepoTarget] | None = None,
) -> dict[str, Any]:
    warnings: list[str] = []
    blockers: list[str] = []

    free_mb = shutil.disk_usage(repo).free // (1024 * 1024)
    if free_mb < min_free_mb:
        blockers.append(f"disk free space below threshold: {free_mb}MB < {min_free_mb}MB")
    elif free_mb < max(min_free_mb * 2, 1000):
        warnings.append(f"disk free space is getting low: {free_mb}MB")

    resume = evaluate_resume_state(
        results_path=results_path,
        state_path_arg=state_path_arg,
        default_state_path=default_state_path,
        write_repaired_state=False,
    )
    state_path = Path(str(resume["state_path"]))

    if not bool(resume["has_results"]) and bool(resume["has_state"]):
        blockers.append("results log missing while state JSON exists; cannot track progress")
    elif str(resume["detail"]) == "state_without_reconstructable_tsv":
        blockers.append("results log is corrupt or unreconstructable; resume helper requires manual confirmation")
    elif str(resume["detail"]) == "unrecoverable_artifacts":
        blockers.extend(str(reason) for reason in resume["reasons"])
    elif str(resume["detail"]) == "state_tsv_diverged":
        warnings.append("state JSON diverges from the reconstructed TSV state; repair or mini-resume required")
    elif str(resume["detail"]) == "invalid_state_json":
        warnings.append("state JSON needs confirmation or repair, but TSV reconstruction is available")
    elif resume["decision"] == "tsv_fallback":
        warnings.append("results log exists without a trustworthy JSON state; resume would use TSV fallback")

    repo_worktree_checks: list[dict[str, Any]] = []
    primary_repo = lexical_abspath(repo)
    for target in [
        RepoTarget(path=primary_repo, scope=",".join(parse_scope_patterns(scope_text)), role="primary"),
        *list(companion_targets or []),
    ]:
        unexpected: list[str] = []
        if has_git_repo(target.path):
            dirty_lines = git_status_paths(target.path)
            scope_patterns = parse_scope_patterns(target.scope)
            for path in dirty_lines:
                if not is_autoresearch_owned_artifact(path) and not path_is_in_scope(path, scope_patterns):
                    unexpected.append(path)
            if unexpected:
                label = format_repo_target_label(target, primary_repo)
                warnings.append(
                    f"[{label}] unexpected worktree changes: " + ", ".join(sorted(unexpected))
                )
        repo_worktree_checks.append(
            {
                "repo": str(target.path),
                "role": target.role,
                "scope_patterns": parse_scope_patterns(target.scope),
                "unexpected_worktree": sorted(unexpected),
            }
        )

    if not command_is_executable(verify_command):
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
        "verify_cwd": verify_cwd,
        "verify_root": str((workspace_root or repo).resolve() if verify_cwd == "workspace_root" else repo.resolve()),
        "results_path": str(results_path),
        "state_path": str(state_path),
        "has_results": bool(resume["has_results"]),
        "has_state": bool(resume["has_state"]),
        "main_rows": (
            int(resume["tsv_summary"]["main_rows"])
            if isinstance(resume.get("tsv_summary"), dict)
            else 0
        ),
        "resume_decision": resume["decision"],
        "resume_detail": resume["detail"],
        "repo_worktree_checks": repo_worktree_checks,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the executable health checks for an autoresearch repo."
    )
    parser.add_argument("--repo", required=True)
    parser.add_argument(
        "--results-path",
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--state-path", help=argparse.SUPPRESS)
    parser.add_argument("--verify-cmd", required=True)
    parser.add_argument("--verify-cwd", choices=["workspace_root", "primary_repo"], default="workspace_root")
    parser.add_argument("--workspace-root")
    parser.add_argument("--scope")
    parser.add_argument(
        "--companion-repo-scope",
        action="append",
        default=[],
        help="Allow edits in a companion repo using PATH=SCOPE. May be repeated.",
    )
    parser.add_argument("--min-free-mb", type=int, default=500)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    repo = resolve_repo_path(args.repo)
    if args.results_path is not None:
        workspace_root = (
            resolve_workspace_root(repo, args.workspace_root)
            if args.workspace_root is not None
            else Path.cwd().resolve()
        )
        results_path = resolve_repo_relative(workspace_root, args.results_path, Path(args.results_path))
        state_default = results_path.parent / STATE_FILE_NAME
    else:
        context = require_context_for_repo(repo)
        workspace_root = resolve_context_workspace_root(
            repo=repo,
            context=context,
            raw_workspace_root=args.workspace_root,
        )
        results_path = context.results_path
        state_default = context.state_path
    if args.companion_repo_scope:
        if not str(args.scope or "").strip():
            raise AutoresearchError("A primary --scope is required when using --companion-repo-scope.")
        repo_targets = build_repo_targets(
            primary_repo=repo,
            primary_scope=args.scope,
            companion_repo_scopes=args.companion_repo_scope,
        )
        primary_scope = repo_targets[0].scope
        companion_targets = [target for target in repo_targets if target.role != "primary"]
    else:
        primary_scope = args.scope
        companion_targets = []
    output = run_health_check(
        repo=repo,
        workspace_root=workspace_root,
        results_path=results_path,
        state_path_arg=args.state_path,
        default_state_path=state_default,
        verify_command=args.verify_cmd,
        verify_cwd=args.verify_cwd,
        scope_text=primary_scope,
        min_free_mb=args.min_free_mb,
        companion_targets=companion_targets,
    )
    print_json(output)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutoresearchError as exc:
        raise SystemExit(f"error: {exc}")
