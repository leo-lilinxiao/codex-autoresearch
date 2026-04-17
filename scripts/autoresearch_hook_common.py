#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from autoresearch_core import (
    LAUNCH_MANIFEST_NAME,
    RESULTS_FILE_NAME,
    RUNTIME_STATE_NAME,
    STATE_FILE_NAME,
)
from autoresearch_hook_context import load_hook_context_pointer
from autoresearch_workspace import default_workspace_artifacts


MARKER_FILES = (
    LAUNCH_MANIFEST_NAME,
    RUNTIME_STATE_NAME,
    STATE_FILE_NAME,
)
HELPER_ROOT_RELATIVE_CANDIDATES = (
    Path(".agents/skills/codex-autoresearch"),
    Path(".codex/skills/codex-autoresearch"),
)
HELPER_REQUIRED_FILES = (
    "autoresearch_supervisor_status.py",
    "autoresearch_helpers.py",
    "autoresearch_artifacts.py",
    "autoresearch_core.py",
    "autoresearch_paths.py",
    "autoresearch_repo_targets.py",
)
RESULTS_HEADER_PREFIX = "iteration\tcommit\tmetric\t"
AUTORESEARCH_SKILL_MARKER = "$codex-autoresearch"
AUTORESEARCH_BACKGROUND_MARKER = "This repo is managed by the autoresearch runtime controller."

HOOK_ACTIVE_ENV = "AUTORESEARCH_HOOK_ACTIVE"
HOOK_RESULTS_PATH_ENV = "AUTORESEARCH_HOOK_RESULTS_PATH"
HOOK_STATE_PATH_ENV = "AUTORESEARCH_HOOK_STATE_PATH"
HOOK_LAUNCH_PATH_ENV = "AUTORESEARCH_HOOK_LAUNCH_PATH"
HOOK_RUNTIME_PATH_ENV = "AUTORESEARCH_HOOK_RUNTIME_PATH"


@dataclass(frozen=True)
class HookArtifactPaths:
    results_path: Path | None
    state_path: Path | None
    launch_path: Path | None
    runtime_path: Path | None


@dataclass(frozen=True)
class HookContext:
    payload: dict[str, object]
    cwd: Path
    repo: Path
    helper_root: Path | None
    artifacts: HookArtifactPaths
    opt_in_env: bool
    transcript_marked: bool
    pointer_active: bool | None

    @property
    def session_is_autoresearch(self) -> bool:
        return self.opt_in_env or self.transcript_marked

    @property
    def has_active_artifacts(self) -> bool:
        if self.pointer_active is False and not self.opt_in_env:
            return False
        paths = self.artifacts
        if paths.launch_path is not None and paths.launch_path.exists():
            return True
        if paths.runtime_path is not None and paths.runtime_path.exists():
            return True
        if paths.state_path is not None and paths.state_path.exists():
            return True
        return paths.results_path is not None and results_log_looks_autoresearch(paths.results_path)


def load_input() -> dict[str, object]:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def manifest_path(script_path: str | Path) -> Path:
    return Path(script_path).resolve().with_name("manifest.json")


def load_manifest(script_path: str | Path) -> dict[str, object]:
    path = manifest_path(script_path)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def resolve_git_repo(cwd: Path) -> Path | None:
    completed = subprocess.run(
        ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        return None
    repo = Path(completed.stdout.strip())
    return repo if repo.exists() else None


def resolve_repo(cwd: Path) -> Path:
    repo = resolve_git_repo(cwd)
    if repo is not None:
        return repo
    return cwd


def resolve_repo_relative(repo: Path, raw: str | None, default_name: str) -> Path:
    candidate = Path(raw) if raw else Path(default_name)
    if not candidate.is_absolute():
        candidate = repo / candidate
    return candidate.expanduser().resolve()


def results_log_looks_autoresearch(results_path: Path) -> bool:
    if not results_path.exists():
        return False
    try:
        lines = results_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    for line in lines[:20]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        return stripped.startswith(RESULTS_HEADER_PREFIX)
    return False


def helper_bundle_present(path: Path) -> bool:
    return all((path / name).exists() for name in HELPER_REQUIRED_FILES)


def valid_helper_root(path: Path | None) -> Path | None:
    if path is None:
        return None
    resolved = path.expanduser().resolve()
    for candidate in (resolved, resolved / "scripts"):
        if candidate.exists() and helper_bundle_present(candidate):
            return candidate
    return None


def resolve_helper_root(
    *,
    script_path: str | Path,
    cwd: Path,
    manifest: dict[str, object],
) -> Path | None:
    local = valid_helper_root(Path(script_path).resolve().parent)
    if local is not None:
        return local

    for base in (cwd, *cwd.parents):
        for relative in HELPER_ROOT_RELATIVE_CANDIDATES:
            candidate = valid_helper_root(base / relative)
            if candidate is not None:
                return candidate

    home = Path.home()
    for relative in HELPER_ROOT_RELATIVE_CANDIDATES:
        candidate = valid_helper_root(home / relative)
        if candidate is not None:
            return candidate

    for key in ("helper_root_fallback", "skill_root_fallback"):
        fallback = manifest.get(key)
        if isinstance(fallback, str):
            candidate = valid_helper_root(Path(fallback))
            if candidate is not None:
                return candidate
    return None


def env_truthy(name: str) -> bool:
    value = os.environ.get(name, "")
    return value.strip().lower() in {"1", "true", "yes", "on", "enabled"}


def _coalesce_path(
    *,
    repo: Path,
    env_name: str,
    pointer_path: Path | None,
    default_name: str | None = None,
) -> Path | None:
    raw = os.environ.get(env_name)
    if raw:
        return resolve_repo_relative(repo, raw, default_name or raw)
    if pointer_path is not None:
        return pointer_path
    if default_name is not None:
        return resolve_repo_relative(repo, None, default_name)
    return None


def resolve_artifact_paths(repo: Path) -> tuple[HookArtifactPaths, bool | None]:
    pointer = load_hook_context_pointer(repo)
    has_env_artifact_paths = any(
        os.environ.get(name)
        for name in (
            HOOK_RESULTS_PATH_ENV,
            HOOK_STATE_PATH_ENV,
            HOOK_LAUNCH_PATH_ENV,
            HOOK_RUNTIME_PATH_ENV,
        )
    )
    if pointer is None and not has_env_artifact_paths:
        return HookArtifactPaths(
            results_path=None,
            state_path=None,
            launch_path=None,
            runtime_path=None,
        ), None

    default_artifacts = default_workspace_artifacts(pointer.workspace_root if pointer is not None else repo)
    return HookArtifactPaths(
        results_path=_coalesce_path(
            repo=default_artifacts.workspace_root,
            env_name=HOOK_RESULTS_PATH_ENV,
            pointer_path=pointer.results_path if pointer is not None else None,
            default_name=(
                str(default_artifacts.results_path.relative_to(default_artifacts.workspace_root))
                if pointer is not None
                else None
            ),
        ),
        state_path=_coalesce_path(
            repo=default_artifacts.workspace_root,
            env_name=HOOK_STATE_PATH_ENV,
            pointer_path=pointer.state_path if pointer is not None else None,
            default_name=(
                str(default_artifacts.state_path.relative_to(default_artifacts.workspace_root))
                if pointer is not None
                else None
            ),
        ),
        launch_path=_coalesce_path(
            repo=default_artifacts.workspace_root,
            env_name=HOOK_LAUNCH_PATH_ENV,
            pointer_path=pointer.launch_path if pointer is not None else None,
            default_name=(
                str(default_artifacts.launch_path.relative_to(default_artifacts.workspace_root))
                if pointer is not None
                else None
            ),
        ),
        runtime_path=_coalesce_path(
            repo=default_artifacts.workspace_root,
            env_name=HOOK_RUNTIME_PATH_ENV,
            pointer_path=pointer.runtime_path if pointer is not None else None,
            default_name=(
                str(default_artifacts.runtime_path.relative_to(default_artifacts.workspace_root))
                if pointer is not None
                else None
            ),
        ),
    ), (pointer.active if pointer is not None else None)


def payload_transcript_path(payload: dict[str, object]) -> Path | None:
    raw = payload.get("transcript_path")
    if not isinstance(raw, str) or not raw.strip():
        return None
    return Path(raw).expanduser().resolve()


def iter_text_fields(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "text" and isinstance(item, str):
                found.append(item)
            else:
                found.extend(iter_text_fields(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(iter_text_fields(item))
    return found


def rollout_line_texts(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return []
    if value.get("type") != "response_item":
        return []
    payload = value.get("payload")
    if not isinstance(payload, dict):
        return []
    if payload.get("type") != "message":
        return []
    if payload.get("role") not in {"user", "assistant"}:
        return []
    return iter_text_fields(payload.get("content"))


def transcript_indicates_autoresearch_session(transcript_path: Path | None) -> bool:
    if transcript_path is None or not transcript_path.exists():
        return False
    try:
        with transcript_path.open("r", encoding="utf-8", errors="ignore") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                for text in rollout_line_texts(payload):
                    stripped = text.lstrip()
                    if stripped.startswith(AUTORESEARCH_SKILL_MARKER):
                        return True
                    if stripped.startswith(AUTORESEARCH_BACKGROUND_MARKER):
                        return True
    except OSError:
        return False
    return False


def build_context(script_path: str | Path) -> HookContext | None:
    payload = load_input()
    cwd_value = payload.get("cwd")
    if not isinstance(cwd_value, str) or not cwd_value:
        return None

    cwd = Path(cwd_value).expanduser().resolve()
    manifest = load_manifest(script_path)
    repo = resolve_repo(cwd)
    transcript_path = payload_transcript_path(payload)
    artifacts, pointer_active = resolve_artifact_paths(repo)

    return HookContext(
        payload=payload,
        cwd=cwd,
        repo=repo,
        helper_root=resolve_helper_root(script_path=script_path, cwd=cwd, manifest=manifest),
        artifacts=artifacts,
        opt_in_env=env_truthy(HOOK_ACTIVE_ENV),
        transcript_marked=transcript_indicates_autoresearch_session(transcript_path),
        pointer_active=pointer_active,
    )
