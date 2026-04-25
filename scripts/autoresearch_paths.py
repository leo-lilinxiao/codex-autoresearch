#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from autoresearch_core import (
    ARTIFACT_DIR_NAME,
    AUTORESEARCH_OWNED_BASENAMES,
    EXEC_SCRATCH_ROOT,
    HOOK_CONTEXT_NAME,
    AutoresearchError,
    LESSONS_FILE_NAME,
    LAUNCH_MANIFEST_NAME,
    LEGACY_AUTORESEARCH_OWNED_BASENAMES,
    RESULTS_FILE_NAME,
    ParsedLog,
    RUNTIME_LOG_NAME,
    RUNTIME_STATE_NAME,
    STATE_FILE_NAME,
)
from autoresearch_workspace import (
    artifact_root_from_start,
    default_workspace_artifacts,
)


@dataclass(frozen=True)
class GitStatusEntry:
    status: str
    paths: tuple[str, ...]

    @property
    def staged_code(self) -> str:
        return self.status[0] if self.status else " "

    @property
    def unstaged_code(self) -> str:
        return self.status[1] if len(self.status) > 1 else " "

    @property
    def has_staged_change(self) -> bool:
        return self.staged_code not in {" ", "?"}

    @property
    def touched_paths(self) -> tuple[str, ...]:
        return self.paths


def lexical_abspath(path: Path | None = None) -> Path:
    return Path(os.path.abspath(str(path or Path.cwd())))


def find_repo_root(start: Path | None = None) -> Path:
    current = lexical_abspath(start)
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return current


def canonical_repo_root(start: Path | None = None) -> Path:
    return find_repo_root(start).resolve()


def has_git_repo(start: Path | None = None) -> bool:
    return (find_repo_root(start) / ".git").exists()


def default_launch_manifest_path(cwd: Path | None = None) -> Path:
    return artifact_root_from_start(cwd) / LAUNCH_MANIFEST_NAME


def default_runtime_state_path(cwd: Path | None = None) -> Path:
    return artifact_root_from_start(cwd) / RUNTIME_STATE_NAME


def default_runtime_log_path(cwd: Path | None = None) -> Path:
    return artifact_root_from_start(cwd) / RUNTIME_LOG_NAME


def default_lessons_path(cwd: Path | None = None) -> Path:
    if cwd is None:
        return Path(ARTIFACT_DIR_NAME) / LESSONS_FILE_NAME
    return artifact_root_from_start(cwd) / LESSONS_FILE_NAME


def default_hook_context_path(cwd: Path | None = None) -> Path:
    return artifact_root_from_start(cwd) / HOOK_CONTEXT_NAME


def default_state_path(cwd: Path | None = None) -> Path:
    if cwd is None:
        return Path(ARTIFACT_DIR_NAME) / STATE_FILE_NAME
    return artifact_root_from_start(cwd) / STATE_FILE_NAME


def resolve_repo_path(repo_arg: str | None) -> Path:
    return find_repo_root(Path(repo_arg or Path.cwd())).resolve()


def resolve_repo_relative(repo: Path, raw: str | None, default_path: Path) -> Path:
    if raw is None:
        return default_path
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = repo / candidate
    return candidate.resolve()


def parse_scope_patterns(scope_text: str | None) -> list[str]:
    if not scope_text:
        return []
    return [token for token in re.split(r"[\s,]+", scope_text.strip()) if token]


def path_is_in_scope(path: str, patterns: list[str]) -> bool:
    if not patterns:
        return False

    normalized = path.replace("\\", "/")
    stripped_path = normalized[2:] if normalized.startswith("./") else normalized
    candidate = PurePosixPath(stripped_path)
    for pattern in patterns:
        pattern = pattern.strip()
        if not pattern:
            continue

        normalized_pattern = pattern.replace("\\", "/")
        if normalized_pattern.startswith("./"):
            normalized_pattern = normalized_pattern[2:]
        is_glob = any(marker in normalized_pattern for marker in "*?[")
        base = normalized_pattern.rstrip("/")

        # Treat directory/** as a recursive prefix, including hidden directories such as .github/.
        if normalized_pattern.endswith("/**"):
            recursive_base = normalized_pattern[: -len("/**")].rstrip("/")
            if recursive_base and (
                stripped_path == recursive_base or stripped_path.startswith(f"{recursive_base}/")
            ):
                return True

        if normalized_pattern.endswith("/") or not is_glob:
            if base and (stripped_path == base or stripped_path.startswith(f"{base}/")):
                return True

        variants = {normalized_pattern}
        while True:
            expanded = {variant.replace("**/", "") for variant in variants if "**/" in variant}
            expanded -= variants
            if not expanded:
                break
            variants |= expanded

        if any(candidate.match(variant) for variant in variants):
            return True

    return False


def is_autoresearch_owned_artifact(path: str | Path) -> bool:
    candidate = Path(path)
    if ARTIFACT_DIR_NAME in candidate.parts:
        return True
    names = [candidate.name]
    parent_name = candidate.parent.name
    if parent_name and parent_name != ".":
        names.append(parent_name)

    for name in names:
        pending = [name]
        seen = set()
        while pending:
            current = pending.pop()
            if current in seen:
                continue
            seen.add(current)
            if current in AUTORESEARCH_OWNED_BASENAMES:
                return True
            if current in LEGACY_AUTORESEARCH_OWNED_BASENAMES:
                return True
            for base in AUTORESEARCH_OWNED_BASENAMES:
                if current.startswith(f"{base}.") or current.endswith(f".{base}"):
                    return True

            path_name = Path(current)
            suffix = path_name.suffix
            if suffix:
                stem = path_name.stem
                for marker in (".prev", ".bak", ".tmp"):
                    if stem.endswith(marker):
                        pending.append(f"{stem[: -len(marker)]}{suffix}")
            for marker in (".prev", ".bak", ".tmp"):
                if current.endswith(marker):
                    pending.append(current[: -len(marker)])
    return False


def default_exec_state_path(cwd: Path | None = None) -> Path:
    repo_root = canonical_repo_root(cwd)
    digest = hashlib.sha256(str(repo_root).encode("utf-8")).hexdigest()[:12]
    return EXEC_SCRATCH_ROOT / digest / "autoresearch-state.exec.json"


def prev_archive_path(path: Path) -> Path:
    if path.suffix:
        return path.with_name(f"{path.stem}.prev{path.suffix}")
    return path.with_name(f"{path.name}.prev")


def archive_path_to_prev(path: Path) -> Path | None:
    if not path.exists():
        return None
    archive_path = prev_archive_path(path)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    path.replace(archive_path)
    return archive_path


def resolve_state_path(
    requested_path: str | None,
    *,
    mode: str | None = None,
    cwd: Path | None = None,
) -> Path:
    if requested_path:
        candidate = Path(requested_path)
        if candidate.is_absolute():
            return candidate
        base = lexical_abspath(cwd) if cwd is not None else lexical_abspath()
        return lexical_abspath(base / candidate)

    if mode == "exec":
        return default_exec_state_path(cwd)
    return default_state_path(cwd)


def _metadata_path(metadata: dict[str, str], key: str) -> Path | None:
    value = metadata.get(key)
    if not isinstance(value, str) or not value.strip():
        return None
    return Path(value).expanduser().resolve()


def _state_path_from_results_metadata(metadata: dict[str, str]) -> Path | None:
    if metadata.get("mode") == "exec":
        workspace_root = _metadata_path(metadata, "workspace_root")
        if workspace_root is None:
            raise AutoresearchError(
                "Exec results log is missing workspace_root metadata needed to locate scratch state."
            )
        return default_exec_state_path(workspace_root)

    artifact_root = _metadata_path(metadata, "artifact_root")
    if artifact_root is not None:
        return artifact_root / STATE_FILE_NAME

    workspace_root = _metadata_path(metadata, "workspace_root")
    if workspace_root is not None:
        return default_workspace_artifacts(workspace_root).state_path

    return None


def _state_path_from_results_path(results_path: Path | None) -> Path | None:
    if results_path is None:
        return None
    candidate = results_path.expanduser()
    if candidate.name != RESULTS_FILE_NAME:
        return None
    artifact_root = candidate.parent
    if artifact_root.name != ARTIFACT_DIR_NAME:
        return None
    return (artifact_root / STATE_FILE_NAME).resolve()


def resolve_state_path_for_log(
    requested_path: str | None,
    parsed: ParsedLog | dict[str, str] | None,
    *,
    cwd: Path | None = None,
    default_path: Path | None = None,
    results_path: Path | None = None,
) -> Path:
    if isinstance(parsed, ParsedLog):
        metadata = parsed.metadata
    elif isinstance(parsed, dict):
        metadata = parsed
    else:
        metadata = {}

    if requested_path is not None:
        return resolve_state_path(requested_path, cwd=cwd)

    metadata_state_path = _state_path_from_results_metadata(metadata)
    if metadata_state_path is not None:
        return metadata_state_path

    if default_path is not None:
        return default_path.resolve()

    derived_state_path = _state_path_from_results_path(results_path)
    if derived_state_path is not None:
        return derived_state_path

    if cwd is not None:
        return default_state_path(cwd)

    return default_state_path(None)


def cleanup_exec_state(cwd: Path | None = None) -> tuple[Path, bool]:
    state_path = default_exec_state_path(cwd)
    removed = False
    if state_path.exists():
        state_path.unlink()
        removed = True

    scratch_root = EXEC_SCRATCH_ROOT.resolve()
    parent = state_path.parent
    while parent.exists() and parent != scratch_root:
        try:
            parent.rmdir()
        except OSError:
            break
        parent = parent.parent

    return state_path, removed


def git_status_entries(repo: Path) -> list[GitStatusEntry]:
    completed = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "-z",
        ],
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        raise AutoresearchError(stderr or "git status failed")

    entries = [entry for entry in completed.stdout.decode("utf-8", errors="replace").split("\0") if entry]
    parsed_entries: list[GitStatusEntry] = []
    index = 0
    while index < len(entries):
        entry = entries[index]
        status = entry[:2]
        paths = [entry[3:] if len(entry) > 3 else entry]
        if "R" in status or "C" in status:
            if index + 1 < len(entries):
                paths.append(entries[index + 1])
            index += 1
        parsed_entries.append(GitStatusEntry(status=status, paths=tuple(paths)))
        index += 1
    return parsed_entries


def git_status_paths(repo: Path) -> list[str]:
    paths: list[str] = []
    for entry in git_status_entries(repo):
        paths.extend(entry.touched_paths)
    return paths
