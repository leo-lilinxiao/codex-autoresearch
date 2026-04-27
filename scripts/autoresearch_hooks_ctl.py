#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from autoresearch_core import print_json
from autoresearch_helpers import AutoresearchError, utc_now


MANIFEST_VERSION = 1
FEATURE_SECTION = "features"
FEATURE_KEY = "codex_hooks"
MANAGED_DIR_NAME = "autoresearch-hooks"
SESSION_SCRIPT_NAME = "session_start.py"
STOP_SCRIPT_NAME = "stop.py"
COMMON_SCRIPT_NAME = "autoresearch_hook_common.py"
CONTEXT_SCRIPT_NAME = "autoresearch_hook_context.py"
MANIFEST_FILE_NAME = "manifest.json"
SESSION_STATUS_MESSAGE = "codex-autoresearch SessionStart hook"
STOP_STATUS_MESSAGE = "codex-autoresearch Stop hook"
SESSION_TIMEOUT_SECONDS = 5
STOP_TIMEOUT_SECONDS = 10
HELPER_BUNDLE_SCRIPT_NAMES = (
    "autoresearch_acceptance.py",
    "autoresearch_supervisor_status.py",
    "autoresearch_helpers.py",
    "autoresearch_artifacts.py",
    "autoresearch_core.py",
    "autoresearch_paths.py",
    "autoresearch_repo_targets.py",
    "autoresearch_workspace.py",
)


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser().resolve()


def hooks_home() -> Path:
    return codex_home() / MANAGED_DIR_NAME


def config_path() -> Path:
    return codex_home() / "config.toml"


def hooks_path() -> Path:
    return codex_home() / "hooks.json"


def manifest_path() -> Path:
    return hooks_home() / MANIFEST_FILE_NAME


def common_script_path() -> Path:
    return hooks_home() / COMMON_SCRIPT_NAME


def context_script_path() -> Path:
    return hooks_home() / CONTEXT_SCRIPT_NAME


def session_script_path() -> Path:
    return hooks_home() / SESSION_SCRIPT_NAME


def stop_script_path() -> Path:
    return hooks_home() / STOP_SCRIPT_NAME


def managed_helper_script_path(name: str) -> Path:
    return hooks_home() / name


def source_helper_script_path(name: str) -> Path:
    return Path(__file__).resolve().with_name(name)


def managed_bundle_paths() -> list[Path]:
    return [
        common_script_path(),
        context_script_path(),
        session_script_path(),
        stop_script_path(),
        *(managed_helper_script_path(name) for name in HELPER_BUNDLE_SCRIPT_NAMES),
    ]


def source_session_script() -> Path:
    return Path(__file__).resolve().with_name("autoresearch_hook_session_start.py")


def source_stop_script() -> Path:
    return Path(__file__).resolve().with_name("autoresearch_hook_stop.py")


def source_common_script() -> Path:
    return Path(__file__).resolve().with_name("autoresearch_hook_common.py")


def source_context_script() -> Path:
    return Path(__file__).resolve().with_name("autoresearch_hook_context.py")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Install, inspect, or remove the optional user-level Codex hooks used by codex-autoresearch."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    status = subparsers.add_parser("status", help="Inspect the current hook installation.")
    install = subparsers.add_parser("install", help="Install or update the managed user-level hooks.")
    uninstall = subparsers.add_parser("uninstall", help="Remove the managed user-level hooks.")
    for subparser in (status, install, uninstall):
        subparser.add_argument(
            "--repo",
            help="Compatibility no-op. Hooks are installed per user CODEX_HOME, not per repo.",
        )
    return parser


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def backup_path(path: Path) -> Path:
    timestamp = utc_now().replace(":", "").replace("-", "")
    return path.with_name(f"{path.name}.bak.{timestamp}")


def write_text_with_backup(path: Path, content: str) -> str | None:
    existing = read_text(path)
    if existing == content:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    if path.exists():
        backup = backup_path(path)
        shutil.copy2(path, backup)
    path.write_text(content, encoding="utf-8")
    return str(backup) if backup is not None else None


def parse_feature_value(text: str) -> bool | None:
    section_match = re.search(
        rf"(?ms)^\[{re.escape(FEATURE_SECTION)}\]\s*$\n(?P<body>.*?)(?=^\[|\Z)",
        text,
    )
    if section_match is None:
        return None
    body = section_match.group("body")
    key_match = re.search(
        rf"(?m)^\s*{re.escape(FEATURE_KEY)}\s*=\s*(true|false)\s*(?:#.*)?$",
        body,
    )
    if key_match is None:
        return None
    return key_match.group(1) == "true"


def set_toml_boolean(text: str, *, section: str, key: str, value: bool) -> str:
    lines = text.splitlines()
    value_text = "true" if value else "false"
    section_header = f"[{section}]"
    section_start = None
    section_end = len(lines)
    for index, line in enumerate(lines):
        if line.strip() == section_header:
            section_start = index
            for probe in range(index + 1, len(lines)):
                if lines[probe].strip().startswith("[") and lines[probe].strip().endswith("]"):
                    section_end = probe
                    break
            break

    key_pattern = re.compile(rf"^\s*{re.escape(key)}\s*=")
    if section_start is not None:
        for index in range(section_start + 1, section_end):
            if key_pattern.match(lines[index]):
                lines[index] = f"{key} = {value_text}"
                break
        else:
            insert_at = section_end
            while insert_at > section_start + 1 and not lines[insert_at - 1].strip():
                insert_at -= 1
            lines.insert(insert_at, f"{key} = {value_text}")
    else:
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend([section_header, f"{key} = {value_text}"])

    rendered = "\n".join(lines).rstrip()
    return rendered + "\n"


def load_json_file(path: Path, *, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return json.loads(json.dumps(default))
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AutoresearchError(f"Invalid JSON file: {path}") from exc
    if not isinstance(payload, dict):
        raise AutoresearchError(f"Expected a JSON object in {path}")
    return payload


def normalize_hooks_payload(payload: dict[str, Any]) -> dict[str, Any]:
    hooks = payload.get("hooks")
    if hooks is None:
        payload["hooks"] = {}
        return payload
    if not isinstance(hooks, dict):
        raise AutoresearchError("hooks.json must contain an object at top-level key 'hooks'")
    return payload


def installed_command(script_path: Path) -> str:
    return subprocess.list2cmdline([sys.executable, str(script_path)])


def legacy_command_variants(script_path: Path) -> set[str]:
    quoted = shlex.quote(str(script_path))
    raw = str(script_path)
    return {
        f"python3 {quoted}",
        f"python {quoted}",
        f"python3 {raw}",
        f"python {raw}",
    }


def managed_command_variants(script_path: Path) -> set[str]:
    return {installed_command(script_path), *legacy_command_variants(script_path)}


def build_managed_group(*, command: str, status_message: str, timeout: int, matcher: str | None = None) -> dict[str, Any]:
    group: dict[str, Any] = {
        "hooks": [
            {
                "type": "command",
                "command": command,
                "timeout": timeout,
                "statusMessage": status_message,
            }
        ]
    }
    if matcher is not None:
        group["matcher"] = matcher
    return group


def group_matches_command(group: Any, command: str) -> bool:
    if not isinstance(group, dict):
        return False
    hooks = group.get("hooks")
    if not isinstance(hooks, list) or len(hooks) != 1:
        return False
    hook = hooks[0]
    if not isinstance(hook, dict):
        return False
    return hook.get("type") == "command" and hook.get("command") == command


def remove_managed_groups(groups: list[Any], commands: set[str]) -> tuple[list[Any], int]:
    kept: list[Any] = []
    removed = 0
    for group in groups:
        if any(group_matches_command(group, command) for command in commands):
            removed += 1
            continue
        kept.append(group)
    return kept, removed


def count_all_hook_groups(payload: dict[str, Any]) -> int:
    hooks = payload.get("hooks", {})
    if not isinstance(hooks, dict):
        return 0
    total = 0
    for groups in hooks.values():
        if isinstance(groups, list):
            total += len(groups)
    return total


def write_manifest(*, feature_enabled_by_installer: bool) -> None:
    managed_scripts = {
        "common": str(common_script_path()),
        "context": str(context_script_path()),
        "session_start": str(session_script_path()),
        "stop": str(stop_script_path()),
    }
    managed_scripts.update(
        {name: str(managed_helper_script_path(name)) for name in HELPER_BUNDLE_SCRIPT_NAMES}
    )
    payload = {
        "version": MANIFEST_VERSION,
        "installed_at": utc_now(),
        "helper_root_fallback": str(hooks_home()),
        "skill_root_fallback": str(hooks_home()),
        "feature_enabled_by_installer": feature_enabled_by_installer,
        "managed_scripts": managed_scripts,
    }
    manifest_path().parent.mkdir(parents=True, exist_ok=True)
    manifest_path().write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def read_manifest() -> dict[str, Any]:
    if not manifest_path().exists():
        return {}
    try:
        payload = json.loads(manifest_path().read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def install_managed_scripts() -> None:
    hooks_home().mkdir(parents=True, exist_ok=True)
    for source_path, destination_path in (
        (source_common_script(), common_script_path()),
        (source_context_script(), context_script_path()),
        (source_session_script(), session_script_path()),
        (source_stop_script(), stop_script_path()),
        *(
            (source_helper_script_path(name), managed_helper_script_path(name))
            for name in HELPER_BUNDLE_SCRIPT_NAMES
        ),
    ):
        shutil.copy2(source_path, destination_path)
        destination_path.chmod(0o755)


def status() -> dict[str, Any]:
    config_text = read_text(config_path())
    hooks_payload = normalize_hooks_payload(
        load_json_file(hooks_path(), default={"hooks": {}})
    )
    manifest = read_manifest()
    managed_paths = managed_bundle_paths()
    session_commands = managed_command_variants(session_script_path())
    stop_commands = managed_command_variants(stop_script_path())
    hooks_map = hooks_payload.get("hooks", {})
    session_groups = hooks_map.get("SessionStart", []) if isinstance(hooks_map, dict) else []
    stop_groups = hooks_map.get("Stop", []) if isinstance(hooks_map, dict) else []
    managed_session = any(
        any(group_matches_command(group, command) for command in session_commands)
        for group in session_groups
    )
    managed_stop = any(
        any(group_matches_command(group, command) for command in stop_commands)
        for group in stop_groups
    )

    return {
        "supported": True,
        "codex_home": str(codex_home()),
        "config_path": str(config_path()),
        "hooks_path": str(hooks_path()),
        "managed_dir": str(hooks_home()),
        "feature_enabled": parse_feature_value(config_text) is True,
        "feature_enabled_by_installer": bool(manifest.get("feature_enabled_by_installer")),
        "managed_session_start_installed": managed_session and session_script_path().exists(),
        "managed_stop_installed": managed_stop and stop_script_path().exists(),
        "managed_scripts_present": all(path.exists() for path in managed_paths),
        "manifest_present": manifest_path().exists(),
        "helper_root_fallback": manifest.get("helper_root_fallback") or str(hooks_home()),
        "skill_root_fallback": manifest.get("skill_root_fallback") or str(hooks_home()),
        "other_hook_groups_present": count_all_hook_groups(hooks_payload) - int(managed_session) - int(managed_stop),
        "ready_for_future_sessions": (
            parse_feature_value(config_text) is True
            and managed_session
            and managed_stop
            and all(path.exists() for path in managed_paths)
        ),
    }


def install() -> dict[str, Any]:
    config_before = read_text(config_path())
    previous_feature = parse_feature_value(config_before)
    feature_enabled_by_installer = previous_feature is not True

    install_managed_scripts()

    updated_config = set_toml_boolean(
        config_before,
        section=FEATURE_SECTION,
        key=FEATURE_KEY,
        value=True,
    )
    config_backup = write_text_with_backup(config_path(), updated_config)

    payload = normalize_hooks_payload(load_json_file(hooks_path(), default={"hooks": {}}))
    hooks_map = payload.setdefault("hooks", {})
    if not isinstance(hooks_map, dict):
        raise AutoresearchError("hooks.json must contain an object at top-level key 'hooks'")

    session_command = installed_command(session_script_path())
    stop_command = installed_command(stop_script_path())
    managed_commands = managed_command_variants(session_script_path()) | managed_command_variants(
        stop_script_path()
    )

    existing_session = hooks_map.get("SessionStart", [])
    if not isinstance(existing_session, list):
        raise AutoresearchError("hooks.SessionStart must be a list")
    session_groups, _ = remove_managed_groups(existing_session, managed_commands)
    session_groups.append(
        build_managed_group(
            command=session_command,
            status_message=SESSION_STATUS_MESSAGE,
            timeout=SESSION_TIMEOUT_SECONDS,
            matcher="startup|resume",
        )
    )
    hooks_map["SessionStart"] = session_groups

    existing_stop = hooks_map.get("Stop", [])
    if not isinstance(existing_stop, list):
        raise AutoresearchError("hooks.Stop must be a list")
    stop_groups, _ = remove_managed_groups(existing_stop, managed_commands)
    stop_groups.append(
        build_managed_group(
            command=stop_command,
            status_message=STOP_STATUS_MESSAGE,
            timeout=STOP_TIMEOUT_SECONDS,
        )
    )
    hooks_map["Stop"] = stop_groups

    hooks_backup = write_text_with_backup(
        hooks_path(),
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    )
    write_manifest(feature_enabled_by_installer=feature_enabled_by_installer)

    current = status()
    current["config_backup"] = config_backup
    current["hooks_backup"] = hooks_backup
    current["action"] = "install"
    return current


def uninstall() -> dict[str, Any]:
    manifest = read_manifest()
    feature_enabled_by_installer = bool(manifest.get("feature_enabled_by_installer"))

    payload = normalize_hooks_payload(load_json_file(hooks_path(), default={"hooks": {}}))
    hooks_map = payload.setdefault("hooks", {})
    if not isinstance(hooks_map, dict):
        raise AutoresearchError("hooks.json must contain an object at top-level key 'hooks'")

    managed_commands = managed_command_variants(session_script_path()) | managed_command_variants(
        stop_script_path()
    )

    removed_count = 0
    for event_name in ("SessionStart", "Stop"):
        groups = hooks_map.get(event_name, [])
        if not isinstance(groups, list):
            raise AutoresearchError(f"hooks.{event_name} must be a list")
        kept, removed = remove_managed_groups(groups, managed_commands)
        removed_count += removed
        if kept:
            hooks_map[event_name] = kept
        else:
            hooks_map.pop(event_name, None)

    hooks_backup = None
    if hooks_path().exists() or removed_count > 0:
        hooks_backup = write_text_with_backup(
            hooks_path(),
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        )

    config_backup = None
    if feature_enabled_by_installer and count_all_hook_groups(payload) == 0:
        config_before = read_text(config_path())
        updated_config = set_toml_boolean(
            config_before,
            section=FEATURE_SECTION,
            key=FEATURE_KEY,
            value=False,
        )
        config_backup = write_text_with_backup(config_path(), updated_config)

    for script_path in (*managed_bundle_paths(), manifest_path()):
        if script_path.exists():
            script_path.unlink()
    if hooks_home().exists():
        try:
            hooks_home().rmdir()
        except OSError:
            pass

    current = status()
    current["config_backup"] = config_backup
    current["hooks_backup"] = hooks_backup
    current["managed_groups_removed"] = removed_count
    current["action"] = "uninstall"
    return current


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "status":
        payload = status()
    elif args.command == "install":
        payload = install()
    else:
        payload = uninstall()
    print_json(payload)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutoresearchError as exc:
        raise SystemExit(f"error: {exc}")
