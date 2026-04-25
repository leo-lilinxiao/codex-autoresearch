#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from autoresearch_workspace import (
    CanonicalContext,
    RepoPointer,
    UNSET,
    canonical_context_path,
    load_context_for_repo,
    load_repo_pointer,
    persist_run_context,
    update_run_context,
    workspace_artifact_root,
)

HOOK_CONTEXT_VERSION = 2
HOOK_CONTEXT_NAME = "context.json"
SESSION_MODE_CHOICES = ("foreground", "background")


@dataclass(frozen=True)
class HookContextPointer:
    version: int
    active: bool
    session_mode: str | None
    results_path: Path | None
    state_path: Path | None
    launch_path: Path | None
    runtime_path: Path | None
    updated_at: str | None
    workspace_root: Path
    artifact_root: Path
    primary_repo: Path


class HookContextError(Exception):
    pass


def _pointer_from_context(context: CanonicalContext | None) -> HookContextPointer | None:
    if context is None:
        return None
    return HookContextPointer(
        version=HOOK_CONTEXT_VERSION,
        active=context.active,
        session_mode=context.session_mode,
        results_path=context.results_path,
        state_path=context.state_path,
        launch_path=context.launch_path,
        runtime_path=context.runtime_path,
        updated_at=context.updated_at,
        workspace_root=context.workspace_root,
        artifact_root=context.artifact_root,
        primary_repo=context.primary_repo,
    )


def write_hook_context_pointer(
    *,
    repo: Path,
    active: bool,
    session_mode: str | None,
    results_path: Path | None,
    state_path: Path | None,
    launch_path: Path | None,
    runtime_path: Path | None,
    workspace_root: Path,
    primary_repo: Path,
    repo_targets,
    verify_cwd: str | None = None,
    log_path: Path | None = None,
) -> Path:
    if results_path is None or state_path is None:
        raise HookContextError("results_path and state_path are required for canonical hook context.")
    return persist_run_context(
        workspace_root=workspace_root,
        primary_repo=primary_repo,
        repo_targets=repo_targets,
        verify_cwd=verify_cwd,
        active=active,
        session_mode=session_mode,
        results_path=results_path,
        state_path=state_path,
        launch_path=launch_path,
        runtime_path=runtime_path,
        log_path=log_path,
    )


def load_hook_context_pointer(repo: Path | None) -> HookContextPointer | None:
    return _pointer_from_context(load_context_for_repo(repo))


def update_hook_context_pointer(
    *,
    repo: Path,
    active: bool | object = UNSET,
    session_mode: str | None | object = UNSET,
    results_path: Path | None | object = UNSET,
    state_path: Path | None | object = UNSET,
    launch_path: Path | None | object = UNSET,
    runtime_path: Path | None | object = UNSET,
    log_path: Path | None | object = UNSET,
    verify_cwd: str | None | object = UNSET,
    workspace_root: Path | None | object = UNSET,
    primary_repo: Path | None | object = UNSET,
    repo_targets: object = UNSET,
) -> Path:
    return update_run_context(
        repo=repo,
        active=active,
        session_mode=session_mode,
        results_path=results_path,
        state_path=state_path,
        launch_path=launch_path,
        runtime_path=runtime_path,
        log_path=log_path,
        verify_cwd=verify_cwd,
        workspace_root=workspace_root,
        primary_repo=primary_repo,
        repo_targets=repo_targets,
    )


__all__ = [
    "CanonicalContext",
    "HOOK_CONTEXT_NAME",
    "HOOK_CONTEXT_VERSION",
    "HookContextError",
    "HookContextPointer",
    "RepoPointer",
    "SESSION_MODE_CHOICES",
    "UNSET",
    "canonical_context_path",
    "load_context_for_repo",
    "load_hook_context_pointer",
    "load_repo_pointer",
    "update_hook_context_pointer",
    "workspace_artifact_root",
    "write_hook_context_pointer",
]
