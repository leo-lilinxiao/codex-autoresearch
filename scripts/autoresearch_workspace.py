#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from autoresearch_core import (
    ARTIFACT_DIR_NAME,
    HOOK_CONTEXT_NAME,
    LAUNCH_MANIFEST_NAME,
    LEGACY_AUTORESEARCH_OWNED_BASENAMES,
    LESSONS_FILE_NAME,
    POINTER_DIR_NAME,
    POINTER_FILE_NAME,
    RESULTS_FILE_NAME,
    RUNTIME_LOG_NAME,
    RUNTIME_STATE_NAME,
    STATE_FILE_NAME,
    AutoresearchError,
    utc_now,
)

CONTEXT_VERSION = 2
POINTER_VERSION = 2


@dataclass(frozen=True)
class WorkspaceArtifacts:
    workspace_root: Path
    artifact_root: Path
    results_path: Path
    state_path: Path
    launch_path: Path
    runtime_path: Path
    log_path: Path
    lessons_path: Path
    context_path: Path


@dataclass(frozen=True)
class RepoPointer:
    version: int
    active: bool
    workspace_root: Path
    artifact_root: Path
    primary_repo: Path
    updated_at: str | None


@dataclass(frozen=True)
class CanonicalContext:
    version: int
    active: bool
    session_mode: str | None
    workspace_root: Path
    artifact_root: Path
    primary_repo: Path
    repo_targets: list[dict[str, str]]
    verify_cwd: str | None
    results_path: Path
    state_path: Path
    launch_path: Path | None
    runtime_path: Path | None
    log_path: Path | None
    updated_at: str | None


UNSET = object()


def lexical_abspath(path: Path | None = None) -> Path:
    return Path(os.path.abspath(str(path or Path.cwd())))


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temp_path = Path(handle.name)
    temp_path.replace(path)


def workspace_artifact_root(workspace_root: Path) -> Path:
    return workspace_root.resolve() / ARTIFACT_DIR_NAME


def resolve_workspace_root(repo: Path, raw: str | None) -> Path:
    if raw is None or not str(raw).strip():
        raise AutoresearchError("--workspace-root is required for workspace-owned autoresearch runs.")
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = repo / candidate
    return candidate.resolve()


def default_workspace_artifacts(workspace_root: Path) -> WorkspaceArtifacts:
    workspace_root = workspace_root.resolve()
    artifact_root = workspace_artifact_root(workspace_root)
    return WorkspaceArtifacts(
        workspace_root=workspace_root,
        artifact_root=artifact_root,
        results_path=artifact_root / RESULTS_FILE_NAME,
        state_path=artifact_root / STATE_FILE_NAME,
        launch_path=artifact_root / LAUNCH_MANIFEST_NAME,
        runtime_path=artifact_root / RUNTIME_STATE_NAME,
        log_path=artifact_root / RUNTIME_LOG_NAME,
        lessons_path=artifact_root / LESSONS_FILE_NAME,
        context_path=artifact_root / HOOK_CONTEXT_NAME,
    )


def resolve_git_repo(start: Path | None = None) -> Path | None:
    current = lexical_abspath(start)
    try:
        completed = subprocess.run(
            ["git", "-C", str(current), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if completed.returncode != 0:
        return None
    repo = Path(completed.stdout.strip()).expanduser()
    return repo.resolve() if str(repo).strip() else None


def require_git_repo(start: Path | None = None) -> Path:
    repo = resolve_git_repo(start)
    if repo is None:
        raise AutoresearchError(
            "Managed repos must be git repositories so codex-autoresearch can store git-local pointers."
        )
    return repo


def git_path(repo: Path, relative_path: str) -> Path:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--git-path", relative_path],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise AutoresearchError(f"Could not resolve git path {relative_path!r} for {repo}: {exc}") from exc
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        raise AutoresearchError(stderr or f"Could not resolve git path {relative_path!r} for {repo}")
    value = completed.stdout.strip()
    if not value:
        raise AutoresearchError(f"git rev-parse returned an empty git path for {relative_path!r}")
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = repo / candidate
    return candidate.resolve()


def repo_pointer_path(repo: Path) -> Path:
    return git_path(repo, f"{POINTER_DIR_NAME}/{POINTER_FILE_NAME}")


def artifact_root_from_start(start: Path | None = None) -> Path:
    resolved = lexical_abspath(start)
    if resolved.name == ARTIFACT_DIR_NAME:
        return resolved
    repo = resolve_git_repo(resolved)
    if repo is not None:
        pointer = load_repo_pointer(repo)
        if pointer is not None:
            return pointer.artifact_root
        raise AutoresearchError(
            f"No codex-autoresearch pointer is available for repo {repo}. "
            "Start a new workspace-owned run or pass an explicit artifact root."
        )
    raise AutoresearchError(
        f"Cannot resolve autoresearch artifact root from {resolved}; expected a managed git repo pointer."
    )


def load_json_object(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def canonical_context_path(artifact_root: Path | WorkspaceArtifacts) -> Path:
    if isinstance(artifact_root, WorkspaceArtifacts):
        return artifact_root.context_path
    return artifact_root.resolve() / HOOK_CONTEXT_NAME


def serialize_repo_targets(repo_targets: Any) -> list[dict[str, str]]:
    serialized: list[dict[str, str]] = []
    for item in list(repo_targets or []):
        if isinstance(item, dict):
            path = item.get("path")
            scope = item.get("scope")
            role = item.get("role")
        else:
            path = getattr(item, "path", None)
            scope = getattr(item, "scope", None)
            role = getattr(item, "role", None)
        if not isinstance(path, (str, Path)):
            continue
        if not isinstance(scope, str) or not scope.strip():
            continue
        role_text = str(role or "companion").strip() or "companion"
        serialized.append(
            {
                "path": str(Path(path).resolve()),
                "scope": scope.strip(),
                "role": role_text,
            }
        )
    return serialized


def pointer_payload(
    *,
    workspace_root: Path,
    artifact_root: Path,
    primary_repo: Path,
    active: bool,
    updated_at: str | None = None,
) -> dict[str, Any]:
    return {
        "version": POINTER_VERSION,
        "active": bool(active),
        "workspace_root": str(workspace_root.resolve()),
        "artifact_root": str(artifact_root.resolve()),
        "primary_repo": str(primary_repo.resolve()),
        "updated_at": updated_at or utc_now(),
    }


def write_repo_pointer(
    *,
    repo: Path,
    workspace_root: Path,
    artifact_root: Path,
    primary_repo: Path,
    active: bool,
    updated_at: str | None = None,
) -> Path:
    path = repo_pointer_path(require_git_repo(repo))
    write_json_atomic(
        path,
        pointer_payload(
            workspace_root=workspace_root,
            artifact_root=artifact_root,
            primary_repo=primary_repo,
            active=active,
            updated_at=updated_at,
        ),
    )
    return path


def load_repo_pointer(repo: Path | None) -> RepoPointer | None:
    if repo is None:
        return None
    resolved_repo = resolve_git_repo(repo)
    if resolved_repo is None:
        return None
    try:
        path = repo_pointer_path(resolved_repo)
    except AutoresearchError:
        return None
    payload = load_json_object(path)
    if payload is None or payload.get("version") != POINTER_VERSION:
        return None
    try:
        active = bool(payload["active"])
        workspace_root = Path(str(payload["workspace_root"])).expanduser().resolve()
        artifact_root = Path(str(payload["artifact_root"])).expanduser().resolve()
        primary_repo = Path(str(payload["primary_repo"])).expanduser().resolve()
    except (KeyError, TypeError, ValueError):
        return None
    updated_at = payload.get("updated_at")
    return RepoPointer(
        version=POINTER_VERSION,
        active=active,
        workspace_root=workspace_root,
        artifact_root=artifact_root,
        primary_repo=primary_repo,
        updated_at=updated_at if isinstance(updated_at, str) else None,
    )


def context_payload(
    *,
    workspace_root: Path,
    artifact_root: Path,
    primary_repo: Path,
    repo_targets: Any,
    verify_cwd: str | None,
    active: bool,
    session_mode: str | None,
    results_path: Path,
    state_path: Path,
    launch_path: Path | None,
    runtime_path: Path | None,
    log_path: Path | None,
    updated_at: str | None = None,
) -> dict[str, Any]:
    if verify_cwd not in {None, "workspace_root", "primary_repo"}:
        raise AutoresearchError(
            f"Unsupported verify_cwd {verify_cwd!r}; expected 'workspace_root' or 'primary_repo'."
        )
    return {
        "version": CONTEXT_VERSION,
        "active": bool(active),
        "session_mode": session_mode,
        "workspace_root": str(workspace_root.resolve()),
        "artifact_root": str(artifact_root.resolve()),
        "primary_repo": str(primary_repo.resolve()),
        "repo_targets": serialize_repo_targets(repo_targets),
        "verify_cwd": verify_cwd,
        "results_path": str(results_path.resolve()),
        "state_path": str(state_path.resolve()),
        "launch_path": str(launch_path.resolve()) if launch_path is not None else None,
        "runtime_path": str(runtime_path.resolve()) if runtime_path is not None else None,
        "log_path": str(log_path.resolve()) if log_path is not None else None,
        "updated_at": updated_at or utc_now(),
    }


def write_canonical_context(
    *,
    workspace_root: Path,
    primary_repo: Path,
    repo_targets: Any,
    verify_cwd: str | None,
    active: bool,
    session_mode: str | None,
    results_path: Path,
    state_path: Path,
    launch_path: Path | None,
    runtime_path: Path | None,
    log_path: Path | None,
    updated_at: str | None = None,
) -> Path:
    artifacts = default_workspace_artifacts(workspace_root)
    write_json_atomic(
        artifacts.context_path,
        context_payload(
            workspace_root=artifacts.workspace_root,
            artifact_root=artifacts.artifact_root,
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
            updated_at=updated_at,
        ),
    )
    return artifacts.context_path


def load_canonical_context(path_or_artifact_root: Path) -> CanonicalContext | None:
    path = path_or_artifact_root
    if path.name != HOOK_CONTEXT_NAME:
        path = canonical_context_path(path)
    payload = load_json_object(path)
    if payload is None or payload.get("version") != CONTEXT_VERSION:
        return None
    try:
        repo_targets = payload.get("repo_targets")
        if not isinstance(repo_targets, list):
            repo_targets = []
        return CanonicalContext(
            version=CONTEXT_VERSION,
            active=bool(payload["active"]),
            session_mode=(
                payload.get("session_mode")
                if isinstance(payload.get("session_mode"), str) or payload.get("session_mode") is None
                else None
            ),
            workspace_root=Path(str(payload["workspace_root"])).expanduser().resolve(),
            artifact_root=Path(str(payload["artifact_root"])).expanduser().resolve(),
            primary_repo=Path(str(payload["primary_repo"])).expanduser().resolve(),
            repo_targets=[
                {
                    "path": str(Path(str(entry["path"])).expanduser().resolve()),
                    "scope": str(entry["scope"]),
                    "role": str(entry.get("role") or "companion"),
                }
                for entry in repo_targets
                if isinstance(entry, dict)
                and isinstance(entry.get("path"), str)
                and isinstance(entry.get("scope"), str)
            ],
            verify_cwd=(
                payload.get("verify_cwd")
                if payload.get("verify_cwd") in {"workspace_root", "primary_repo", None}
                else None
            ),
            results_path=Path(str(payload["results_path"])).expanduser().resolve(),
            state_path=Path(str(payload["state_path"])).expanduser().resolve(),
            launch_path=(
                Path(str(payload["launch_path"])).expanduser().resolve()
                if isinstance(payload.get("launch_path"), str) and payload.get("launch_path")
                else None
            ),
            runtime_path=(
                Path(str(payload["runtime_path"])).expanduser().resolve()
                if isinstance(payload.get("runtime_path"), str) and payload.get("runtime_path")
                else None
            ),
            log_path=(
                Path(str(payload["log_path"])).expanduser().resolve()
                if isinstance(payload.get("log_path"), str) and payload.get("log_path")
                else None
            ),
            updated_at=payload.get("updated_at") if isinstance(payload.get("updated_at"), str) else None,
        )
    except (KeyError, TypeError, ValueError):
        return None


def load_context_for_repo(repo: Path | None) -> CanonicalContext | None:
    pointer = load_repo_pointer(repo)
    if pointer is not None:
        return load_canonical_context(pointer.artifact_root)
    return None


def require_context_for_repo(repo: Path | None) -> CanonicalContext:
    resolved_repo = require_git_repo(repo)
    try:
        pointer_path = repo_pointer_path(resolved_repo)
    except AutoresearchError as exc:
        raise AutoresearchError(
            f"Could not resolve codex-autoresearch pointer path for repo {resolved_repo}: {exc}"
        ) from exc
    if not pointer_path.exists():
        legacy_error = legacy_layout_error(resolved_repo)
        if legacy_error is not None:
            raise AutoresearchError(legacy_error)
        raise AutoresearchError(
            f"No codex-autoresearch context found for repo {resolved_repo}; expected git-local "
            f"pointer at {pointer_path} to canonical autoresearch-results/context.json."
        )

    pointer = load_repo_pointer(resolved_repo)
    if pointer is None:
        raise AutoresearchError(
            f"Invalid codex-autoresearch pointer at {pointer_path}; expected a v{POINTER_VERSION} "
            "git-local pointer to canonical autoresearch-results/context.json."
        )

    context_path = canonical_context_path(pointer.artifact_root)
    context = load_canonical_context(context_path)
    if context is None:
        raise AutoresearchError(
            f"Invalid or missing canonical autoresearch context at {context_path}; "
            "pointer-based run context cannot be recovered."
        )
    if context.workspace_root != pointer.workspace_root:
        raise AutoresearchError(
            f"Git-local pointer at {pointer_path} disagrees with canonical context workspace_root."
        )
    if context.artifact_root != pointer.artifact_root:
        raise AutoresearchError(
            f"Git-local pointer at {pointer_path} disagrees with canonical context artifact_root."
        )
    if context.primary_repo != pointer.primary_repo:
        raise AutoresearchError(
            f"Git-local pointer at {pointer_path} disagrees with canonical context primary_repo."
        )
    return context


def resolve_context_workspace_root(
    *,
    repo: Path,
    context: CanonicalContext,
    raw_workspace_root: str | None,
) -> Path:
    if raw_workspace_root is None or not str(raw_workspace_root).strip():
        return context.workspace_root
    requested = resolve_workspace_root(repo, raw_workspace_root)
    if requested != context.workspace_root:
        raise AutoresearchError(
            f"--workspace-root {requested} does not match canonical context workspace_root "
            f"{context.workspace_root}."
        )
    return context.workspace_root


def _repo_target_paths(primary_repo: Path, repo_targets: Any) -> list[Path]:
    paths = [primary_repo.resolve()]
    for entry in serialize_repo_targets(repo_targets):
        candidate = Path(entry["path"]).resolve()
        if candidate not in paths:
            paths.append(candidate)
    return paths


def require_managed_git_repos(primary_repo: Path, repo_targets: Any) -> list[Path]:
    return [require_git_repo(repo) for repo in _repo_target_paths(primary_repo, repo_targets)]


def _path_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def ensure_local_exclude_entry(repo: Path, artifact_root: Path) -> bool:
    if not _path_within(artifact_root, repo):
        return False
    relative = artifact_root.resolve().relative_to(repo.resolve()).as_posix().rstrip("/") + "/"
    exclude_path = git_path(repo, "info/exclude")
    exclude_path.parent.mkdir(parents=True, exist_ok=True)
    existing = exclude_path.read_text(encoding="utf-8") if exclude_path.exists() else ""
    lines = [line.strip() for line in existing.splitlines() if line.strip()]
    if relative in lines:
        return False
    updated = existing
    if updated and not updated.endswith("\n"):
        updated += "\n"
    updated += relative + "\n"
    exclude_path.write_text(updated, encoding="utf-8")
    return True


def persist_run_context(
    *,
    workspace_root: Path,
    primary_repo: Path,
    repo_targets: Any,
    verify_cwd: str | None,
    active: bool,
    session_mode: str | None,
    results_path: Path,
    state_path: Path,
    launch_path: Path | None,
    runtime_path: Path | None,
    log_path: Path | None,
) -> Path:
    resolved_primary_repo = Path(primary_repo).resolve()
    resolved_repos = require_managed_git_repos(primary_repo, repo_targets)
    context_path = write_canonical_context(
        workspace_root=workspace_root,
        primary_repo=resolved_primary_repo,
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
    artifact_root = workspace_artifact_root(workspace_root)
    for resolved_repo in resolved_repos:
        write_repo_pointer(
            repo=resolved_repo,
            workspace_root=workspace_root,
            artifact_root=artifact_root,
            primary_repo=resolved_primary_repo,
            active=active,
        )
        ensure_local_exclude_entry(resolved_repo, artifact_root)
    return context_path


def update_run_context(
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
    repo_targets: Any | object = UNSET,
) -> Path:
    current = load_context_for_repo(repo)
    if current is None:
        raise AutoresearchError(
            f"No canonical autoresearch context is available for repo {Path(repo).resolve()}."
        )

    resolved_workspace_root = current.workspace_root if workspace_root is UNSET else Path(workspace_root).resolve()  # type: ignore[arg-type]
    resolved_primary_repo = (
        current.primary_repo if primary_repo is UNSET else Path(primary_repo).resolve()  # type: ignore[arg-type]
    )
    resolved_repo_targets = current.repo_targets if repo_targets is UNSET else repo_targets
    resolved_active = current.active if active is UNSET else bool(active)
    resolved_session_mode = current.session_mode if session_mode is UNSET else session_mode
    resolved_results_path = current.results_path if results_path is UNSET else results_path
    resolved_state_path = current.state_path if state_path is UNSET else state_path
    resolved_launch_path = current.launch_path if launch_path is UNSET else launch_path
    resolved_runtime_path = current.runtime_path if runtime_path is UNSET else runtime_path
    resolved_log_path = current.log_path if log_path is UNSET else log_path
    resolved_verify_cwd = current.verify_cwd if verify_cwd is UNSET else verify_cwd

    if resolved_results_path is None or resolved_state_path is None:
        raise AutoresearchError("Canonical context requires results_path and state_path.")

    return persist_run_context(
        workspace_root=resolved_workspace_root,
        primary_repo=resolved_primary_repo,
        repo_targets=resolved_repo_targets,
        verify_cwd=resolved_verify_cwd,
        active=resolved_active,
        session_mode=resolved_session_mode,
        results_path=Path(resolved_results_path).resolve(),
        state_path=Path(resolved_state_path).resolve(),
        launch_path=Path(resolved_launch_path).resolve() if resolved_launch_path is not None else None,
        runtime_path=Path(resolved_runtime_path).resolve() if resolved_runtime_path is not None else None,
        log_path=Path(resolved_log_path).resolve() if resolved_log_path is not None else None,
    )


def detect_legacy_repo_root_artifacts(repo: Path) -> list[Path]:
    resolved_repo = Path(repo).resolve()
    found: list[Path] = []
    for name in sorted(LEGACY_AUTORESEARCH_OWNED_BASENAMES):
        candidate = resolved_repo / name
        if candidate.exists():
            found.append(candidate)
    return found


def legacy_layout_error(repo: Path) -> str | None:
    found = detect_legacy_repo_root_artifacts(repo)
    if not found:
        return None
    return (
        "Found legacy repo-root autoresearch artifacts. This version uses workspace-owned "
        "autoresearch-results/. Former autoresearch-hook-context.json is now context.json "
        "inside that directory. Start a fresh run or move/archive the old artifacts."
    )
