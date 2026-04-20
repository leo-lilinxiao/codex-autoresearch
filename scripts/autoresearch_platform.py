#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import shlex
import shutil
import signal
import subprocess
import tempfile
from pathlib import Path
from typing import Any


ENV_ASSIGNMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=.*$")
STILL_ACTIVE_EXIT_CODE = 259
WINDOWS_ACCESS_DENIED = 5
WINDOWS_COMMAND_UNAVAILABLE = "<windows-command-unavailable>"


def is_windows() -> bool:
    return os.name == "nt"


def default_exec_scratch_root() -> Path:
    return Path(tempfile.gettempdir()) / "codex-autoresearch-exec"


def command_join(parts: list[str]) -> str:
    if is_windows():
        return subprocess.list2cmdline(parts)
    return shlex.join(parts)


def strip_wrapping_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def runtime_popen_kwargs() -> dict[str, Any]:
    if is_windows():
        return {
            "creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        }
    return {"start_new_session": True}


def process_is_zombie(pid: int) -> bool:
    if is_windows():
        return False
    try:
        completed = subprocess.run(
            ["ps", "-p", str(pid), "-o", "stat="],
            capture_output=True,
            text=True,
        )
    except OSError:
        return False
    if completed.returncode != 0:
        return False
    state = completed.stdout.strip().upper()
    return state.startswith("Z")


def _windows_process_api() -> tuple[Any, Any, Any] | None:
    try:
        import ctypes
        from ctypes import wintypes
    except (ImportError, AttributeError):
        return None

    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    except AttributeError:
        return None
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.GetProcessTimes.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
    ]
    kernel32.GetProcessTimes.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    return ctypes, wintypes, kernel32


def _windows_process_exit_code(pid: int) -> int | None:
    api = _windows_process_api()
    if api is None:
        return None
    ctypes, wintypes, kernel32 = api
    process_query_limited_information = 0x1000
    handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
    if not handle:
        get_last_error = getattr(ctypes, "get_last_error", lambda: 0)
        if get_last_error() == WINDOWS_ACCESS_DENIED:
            return STILL_ACTIVE_EXIT_CODE
        return None
    try:
        exit_code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return None
        return int(exit_code.value)
    finally:
        kernel32.CloseHandle(handle)


def _windows_process_started_at(pid: int) -> str | None:
    api = _windows_process_api()
    if api is None:
        return None
    ctypes, wintypes, kernel32 = api
    process_query_limited_information = 0x1000
    handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
    if not handle:
        return None
    try:
        creation = wintypes.FILETIME()
        exit_time = wintypes.FILETIME()
        kernel_time = wintypes.FILETIME()
        user_time = wintypes.FILETIME()
        ok = kernel32.GetProcessTimes(
            handle,
            ctypes.byref(creation),
            ctypes.byref(exit_time),
            ctypes.byref(kernel_time),
            ctypes.byref(user_time),
        )
        if not ok:
            return None
        ticks = (int(creation.dwHighDateTime) << 32) + int(creation.dwLowDateTime)
        return f"windows-filetime:{ticks}"
    finally:
        kernel32.CloseHandle(handle)


def process_is_alive(pid: int | None) -> bool:
    if pid is None or pid <= 0:
        return False
    if is_windows():
        exit_code = _windows_process_exit_code(pid)
        return exit_code == STILL_ACTIVE_EXIT_CODE
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True
    except ProcessLookupError:
        return False
    if process_is_zombie(pid):
        return False
    return True


def _ps_field(pid: int, field: str) -> str | None:
    try:
        completed = subprocess.run(
            ["ps", "-p", str(pid), "-o", f"{field}="],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except OSError:
        return None
    if completed.returncode != 0:
        return None
    value = completed.stdout.strip()
    return value or None


def inspect_process_identity(pid: int | None) -> dict[str, object] | None:
    if pid is None or pid <= 0 or not process_is_alive(pid):
        return None
    if is_windows():
        started_at = _windows_process_started_at(pid)
        if started_at is None:
            return None
        return {
            "pid": pid,
            "pgid": pid,
            "started_at": started_at,
            "command": WINDOWS_COMMAND_UNAVAILABLE,
        }

    pgid_text = _ps_field(pid, "pgid")
    started_at = _ps_field(pid, "lstart")
    command = _ps_field(pid, "command")
    if pgid_text is None or started_at is None or command is None:
        return None
    try:
        pgid = int(pgid_text)
    except ValueError:
        return None
    return {
        "pid": pid,
        "pgid": pgid,
        "started_at": started_at,
        "command": command,
    }


def runtime_process_group_id(pid: int) -> int:
    getpgid = getattr(os, "getpgid", None)
    if getpgid is None:
        return pid
    return int(getpgid(pid))


def current_runtime_process_group_id() -> int:
    getpgid = getattr(os, "getpgid", None)
    if getpgid is None:
        return os.getpid()
    return int(getpgid(0))


def signal_runtime_process_group(
    *,
    pid: int,
    pgid: int,
    sig: signal.Signals,
    force: bool = False,
) -> None:
    killpg = getattr(os, "killpg", None)
    if killpg is not None:
        killpg(pgid, sig)
        return

    if is_windows():
        if force:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            return
        if sig == signal.SIGTERM and hasattr(signal, "CTRL_BREAK_EVENT"):
            try:
                os.kill(pgid, signal.CTRL_BREAK_EVENT)
                return
            except OSError:
                pass

    os.kill(pid, sig)


def command_is_executable(command: str) -> bool:
    if not command.strip():
        return False
    try:
        parts = shlex.split(command, posix=not is_windows())
    except ValueError:
        return False
    if not parts:
        return False

    executable = ""
    for part in parts:
        if ENV_ASSIGNMENT_RE.fullmatch(part):
            continue
        executable = strip_wrapping_quotes(part)
        break
    if not executable:
        return False

    candidate = Path(executable)
    if candidate.is_absolute() or "/" in executable or "\\" in executable:
        if not candidate.is_file():
            return False
        if not is_windows():
            return os.access(candidate, os.X_OK)
        if candidate.suffix:
            pathext = os.environ.get("PATHEXT", ".COM;.EXE;.BAT;.CMD")
            executable_suffixes = {item.lower() for item in pathext.split(";") if item}
            return candidate.suffix.lower() in executable_suffixes
        return True
    return shutil.which(executable) is not None
