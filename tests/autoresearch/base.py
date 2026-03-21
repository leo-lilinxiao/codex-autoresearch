from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"



class AutoresearchScriptsTestBase(unittest.TestCase):
    maxDiff = None

    def run_script_completed(
        self,
        script_name: str,
        *args: str,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / script_name), *args],
            capture_output=True,
            text=True,
            cwd=cwd,
            env=env,
        )

    def run_script(
        self,
        script_name: str,
        *args: str,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> dict[str, object]:
        completed = self.run_script_completed(script_name, *args, cwd=cwd, env=env)
        completed.check_returncode()
        return json.loads(completed.stdout)

    def run_script_text(
        self,
        script_name: str,
        *args: str,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> str:
        completed = self.run_script_completed(script_name, *args, cwd=cwd, env=env)
        completed.check_returncode()
        return completed.stdout.strip()

    def write_fake_codex(self, path: Path, *, body_lines: list[str]) -> None:
        path.write_text(
            "#!/usr/bin/env bash\nset -euo pipefail\n" + "\n".join(body_lines) + "\n",
            encoding="utf-8",
        )
        path.chmod(0o755)

    def wait_for_runtime_status(
        self,
        repo: Path,
        expected_statuses: set[str],
        *,
        timeout: float = 10.0,
    ) -> dict[str, object]:
        deadline = time.time() + timeout
        while time.time() < deadline:
            status = self.run_script(
                "autoresearch_runtime_ctl.py",
                "status",
                "--repo",
                str(repo),
            )
            if status["status"] in expected_statuses:
                return status
            time.sleep(0.1)
        self.fail(f"Timed out waiting for runtime status in {expected_statuses}")

    def create_launch_manifest(
        self,
        repo: Path,
        *,
        original_goal: str = "Reduce failures in this repo",
        mode: str = "loop",
        goal: str = "Reduce failures",
        scope: str = "src/**/*.py",
        metric_name: str = "failure count",
        direction: str = "lower",
        verify: str = "python3 -c pass",
        guard: str | None = "python -m py_compile src",
        stop_condition: str | None = None,
    ) -> dict[str, object]:
        args = [
            "autoresearch_runtime_ctl.py",
            "create-launch",
            "--repo",
            str(repo),
            "--original-goal",
            original_goal,
            "--mode",
            mode,
            "--goal",
            goal,
            "--scope",
            scope,
            "--metric-name",
            metric_name,
            "--direction",
            direction,
            "--verify",
            verify,
        ]
        if guard is not None:
            args.extend(["--guard", guard])
        if stop_condition is not None:
            args.extend(["--stop-condition", stop_condition])
        return self.run_script(*args)

    def write_sleeping_fake_codex(self, path: Path) -> None:
        self.write_fake_codex(
            path,
            body_lines=[
                'repo=""',
                'while [[ $# -gt 0 ]]; do',
                '  case "$1" in',
                '    -C) repo="$2"; shift 2 ;;',
                '    *) shift ;;',
                '  esac',
                'done',
                'if [[ -n "$repo" ]]; then cd "$repo"; fi',
                "sleep 30",
            ],
        )

    def launch_runtime(
        self,
        repo: Path,
        *,
        fake_codex_path: Path,
        original_goal: str = "Reduce failures in this repo",
        goal: str = "Reduce failures",
        scope: str = "src/**/*.py",
        metric_name: str = "failure count",
        direction: str = "lower",
        verify: str = "python3 -c pass",
        guard: str = "python -m py_compile src",
        fresh_start: bool = False,
    ) -> dict[str, object]:
        args = [
            "autoresearch_runtime_ctl.py",
            "launch",
            "--repo",
            str(repo),
            "--original-goal",
            original_goal,
            "--mode",
            "loop",
            "--goal",
            goal,
            "--scope",
            scope,
            "--metric-name",
            metric_name,
            "--direction",
            direction,
            "--verify",
            verify,
            "--guard",
            guard,
            "--codex-bin",
            str(fake_codex_path),
        ]
        if fresh_start:
            args.append("--fresh-start")
        return self.run_script(*args)
