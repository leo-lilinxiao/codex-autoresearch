from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import autoresearch_platform


class AutoresearchPlatformTest(unittest.TestCase):
    def test_exec_scratch_root_uses_platform_tempdir(self) -> None:
        self.assertEqual(
            autoresearch_platform.default_exec_scratch_root(),
            Path(tempfile.gettempdir()) / "codex-autoresearch-exec",
        )

    def test_command_join_uses_windows_quoting_when_needed(self) -> None:
        with mock.patch.object(autoresearch_platform, "is_windows", return_value=True):
            joined = autoresearch_platform.command_join(
                [r"C:\Program Files\Python\python.exe", r"C:\repo\hook.py"]
            )
        self.assertIn('"C:\\Program Files\\Python\\python.exe"', joined)
        self.assertIn("C:\\repo\\hook.py", joined)

    def test_windows_absolute_executable_accepts_pathext_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "codex.exe"
            exe.write_text("", encoding="utf-8")
            with (
                mock.patch.object(autoresearch_platform, "is_windows", return_value=True),
                mock.patch.dict(os.environ, {"PATHEXT": ".COM;.EXE;.BAT;.CMD"}),
            ):
                self.assertTrue(autoresearch_platform.command_is_executable(str(exe)))
                self.assertTrue(autoresearch_platform.command_is_executable(f'"{exe}" exec'))

    def test_windows_absolute_executable_rejects_unknown_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "codex.txt"
            exe.write_text("", encoding="utf-8")
            with mock.patch.object(autoresearch_platform, "is_windows", return_value=True):
                self.assertFalse(autoresearch_platform.command_is_executable(str(exe)))

    def test_windows_liveness_uses_process_exit_code(self) -> None:
        with (
            mock.patch.object(autoresearch_platform, "is_windows", return_value=True),
            mock.patch.object(
                autoresearch_platform,
                "_windows_process_exit_code",
                return_value=autoresearch_platform.STILL_ACTIVE_EXIT_CODE,
            ),
        ):
            self.assertTrue(autoresearch_platform.process_is_alive(4242))

        with (
            mock.patch.object(autoresearch_platform, "is_windows", return_value=True),
            mock.patch.object(
                autoresearch_platform,
                "_windows_process_exit_code",
                return_value=0,
            ),
        ):
            self.assertFalse(autoresearch_platform.process_is_alive(4242))

    def test_windows_liveness_fails_closed_when_winapi_is_unavailable(self) -> None:
        with (
            mock.patch.object(autoresearch_platform, "is_windows", return_value=True),
            mock.patch.object(autoresearch_platform, "_windows_process_api", return_value=None),
        ):
            self.assertFalse(autoresearch_platform.process_is_alive(4242))

    def test_windows_identity_uses_pid_as_process_group_and_creation_time(self) -> None:
        with (
            mock.patch.object(autoresearch_platform, "is_windows", return_value=True),
            mock.patch.object(
                autoresearch_platform,
                "_windows_process_exit_code",
                return_value=autoresearch_platform.STILL_ACTIVE_EXIT_CODE,
            ),
            mock.patch.object(
                autoresearch_platform,
                "_windows_process_started_at",
                return_value="windows-filetime:123",
            ),
        ):
            self.assertEqual(
                autoresearch_platform.inspect_process_identity(4242),
                {
                    "pid": 4242,
                    "pgid": 4242,
                    "started_at": "windows-filetime:123",
                    "command": autoresearch_platform.WINDOWS_COMMAND_UNAVAILABLE,
                },
            )

    def test_windows_identity_fails_closed_without_creation_time(self) -> None:
        with (
            mock.patch.object(autoresearch_platform, "is_windows", return_value=True),
            mock.patch.object(
                autoresearch_platform,
                "_windows_process_exit_code",
                return_value=autoresearch_platform.STILL_ACTIVE_EXIT_CODE,
            ),
            mock.patch.object(
                autoresearch_platform,
                "_windows_process_started_at",
                return_value=None,
            ),
        ):
            self.assertIsNone(autoresearch_platform.inspect_process_identity(4242))


if __name__ == "__main__":
    unittest.main()
