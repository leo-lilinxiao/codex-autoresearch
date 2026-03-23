from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from unittest import mock
from pathlib import Path

from .base import AutoresearchScriptsTestBase, REPO_ROOT, SCRIPTS_DIR

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import autoresearch_runtime_ops


class AutoresearchRuntimeControllerTest(AutoresearchScriptsTestBase):
    maxDiff = None

    def test_runtime_launch_command_atomically_creates_manifest_and_starts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            fake_codex_path = tmpdir / "fake-codex"
            self.write_sleeping_fake_codex(fake_codex_path)

            launched = self.launch_runtime(tmpdir, fake_codex_path=fake_codex_path)
            self.assertEqual(launched["status"], "running")
            self.assertTrue((tmpdir / "autoresearch-launch.json").exists())
            self.assertTrue((tmpdir / "autoresearch-runtime.json").exists())

            running = self.wait_for_runtime_status(tmpdir, {"running"})
            self.assertEqual(running["status"], "running")

            stopped = self.run_script(
                "autoresearch_runtime_ctl.py",
                "stop",
                "--repo",
                str(tmpdir),
            )
            self.assertEqual(stopped["status"], "stopped")

    def test_runtime_launch_fresh_start_archives_prior_results_and_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            fake_codex_path = tmpdir / "fake-codex"
            self.write_sleeping_fake_codex(fake_codex_path)

            old_results = tmpdir / "research-results.tsv"
            old_state = tmpdir / "autoresearch-state.json"
            old_launch = tmpdir / "autoresearch-launch.json"
            old_runtime = tmpdir / "autoresearch-runtime.json"
            old_runtime_log = tmpdir / "autoresearch-runtime.log"

            old_results.write_text(
                "iteration\tcommit\tmetric\tdelta\tguard\tstatus\tdescription\n"
                "0\tabc1234\t10\t0\t-\tbaseline\told baseline\n",
                encoding="utf-8",
            )
            old_state.write_text(
                json.dumps(
                    {
                        "mode": "loop",
                        "run_tag": "old-run",
                        "config": {
                            "goal": "Old goal",
                            "scope": "src/**/*.py",
                            "metric": "failure count",
                            "direction": "lower",
                            "verify": "python3 -c pass",
                            "guard": "python -m py_compile src",
                            "iterations": None,
                            "stop_condition": None,
                            "rollback_policy": None,
                            "parallel_mode": "serial",
                            "web_search": "disabled",
                        },
                        "state": {
                            "iteration": 0,
                            "baseline_metric": 10,
                            "best_metric": 10,
                            "best_iteration": 0,
                            "current_metric": 10,
                            "last_commit": "abc1234",
                            "last_trial_commit": "abc1234",
                            "last_trial_metric": 10,
                            "keeps": 0,
                            "discards": 0,
                            "crashes": 0,
                            "no_ops": 0,
                            "blocked": 0,
                            "consecutive_discards": 0,
                            "pivot_count": 0,
                            "last_status": "baseline",
                        },
                        "updated_at": "2026-03-21T00:00:00Z",
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            old_launch.write_text(
                json.dumps({"original_goal": "stale manifest"}, indent=2) + "\n",
                encoding="utf-8",
            )
            old_runtime.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "repo": str(tmpdir),
                        "launch_path": str(old_launch),
                        "results_path": str(old_results),
                        "state_path": str(old_state),
                        "log_path": str(old_runtime_log),
                        "status": "terminal",
                        "terminal_reason": "completed",
                        "pid": 12345,
                        "pgid": None,
                        "command": [],
                        "requested_stop_at": None,
                        "last_decision": "stop",
                        "last_reason": "completed",
                        "last_seen_iteration": 0,
                        "last_seen_status": "baseline",
                        "created_at": "2026-03-21T00:00:00Z",
                        "updated_at": "2026-03-21T00:00:00Z",
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            old_runtime_log.write_text("old runtime log\n", encoding="utf-8")

            launched = self.launch_runtime(
                tmpdir,
                fake_codex_path=fake_codex_path,
                original_goal="New goal",
                goal="Reduce failures",
                fresh_start=True,
            )
            self.assertEqual(launched["status"], "running")
            self.assertEqual(
                sorted(str(Path(path).resolve()) for path in launched["archived_paths"]),
                sorted(
                    [
                        str((tmpdir / "research-results.prev.tsv").resolve()),
                        str((tmpdir / "autoresearch-state.prev.json").resolve()),
                        str((tmpdir / "autoresearch-launch.prev.json").resolve()),
                        str((tmpdir / "autoresearch-runtime.prev.json").resolve()),
                        str((tmpdir / "autoresearch-runtime.prev.log").resolve()),
                    ]
                ),
            )
            self.assertTrue((tmpdir / "research-results.prev.tsv").exists())
            self.assertTrue((tmpdir / "autoresearch-state.prev.json").exists())
            self.assertTrue((tmpdir / "autoresearch-launch.prev.json").exists())
            self.assertTrue((tmpdir / "autoresearch-runtime.prev.json").exists())
            self.assertTrue((tmpdir / "autoresearch-runtime.prev.log").exists())
            manifest = json.loads((tmpdir / "autoresearch-launch.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["original_goal"], "New goal")
            self.assertEqual(manifest["config"]["session_mode"], "background")

            stopped = self.run_script(
                "autoresearch_runtime_ctl.py",
                "stop",
                "--repo",
                str(tmpdir),
            )
            self.assertEqual(stopped["status"], "stopped")

    def test_runtime_start_syncs_existing_foreground_state_to_background(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            fake_codex_path = tmpdir / "fake-codex"
            self.write_sleeping_fake_codex(fake_codex_path)

            self.run_script(
                "autoresearch_init_run.py",
                "--results-path",
                str(tmpdir / "research-results.tsv"),
                "--state-path",
                str(tmpdir / "autoresearch-state.json"),
                "--mode",
                "loop",
                "--session-mode",
                "foreground",
                "--goal",
                "Reduce failures",
                "--scope",
                "src/**/*.py",
                "--metric-name",
                "failure count",
                "--direction",
                "lower",
                "--verify",
                "python3 -c pass",
                "--baseline-metric",
                "10",
                "--baseline-commit",
                "base111",
                "--baseline-description",
                "baseline failures",
            )

            launched = self.launch_runtime(
                tmpdir,
                fake_codex_path=fake_codex_path,
                original_goal="Resume in background",
                goal="Reduce failures",
            )
            self.assertEqual(launched["status"], "running")

            state = json.loads((tmpdir / "autoresearch-state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["config"]["session_mode"], "background")
            self.assertEqual(state["config"]["execution_policy"], "danger_full_access")

            stopped = self.run_script(
                "autoresearch_runtime_ctl.py",
                "stop",
                "--repo",
                str(tmpdir),
            )
            self.assertEqual(stopped["status"], "stopped")

    def test_multi_repo_background_foreground_background_switch_keeps_shared_state_consistent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as tools_tmp:
            root = Path(tmp)
            tool_dir = Path(tools_tmp)
            primary = root / "primary"
            companion_a = root / "companion_a"
            companion_b = root / "companion_b"
            for repo in (primary, companion_a, companion_b):
                repo.mkdir()
                subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
                subprocess.run(["git", "config", "user.email", "a@b.c"], cwd=repo, check=True)
                subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)

            fake_codex_path = tool_dir / "fake-codex"
            self.write_sleeping_fake_codex(fake_codex_path)

            self.run_script(
                "autoresearch_init_run.py",
                "--results-path",
                str(primary / "research-results.tsv"),
                "--state-path",
                str(primary / "autoresearch-state.json"),
                "--mode",
                "loop",
                "--session-mode",
                "background",
                "--goal",
                "Reduce failures",
                "--scope",
                "src/",
                "--companion-repo-scope",
                f"{companion_a}=pkg/",
                "--companion-repo-scope",
                f"{companion_b}=lib/",
                "--metric-name",
                "failure count",
                "--direction",
                "lower",
                "--verify",
                "python3 -c pass",
                "--baseline-metric",
                "10",
                "--baseline-commit",
                "base111",
                "--baseline-description",
                "baseline failures",
            )

            launched = self.launch_runtime(
                primary,
                fake_codex_path=fake_codex_path,
                scope="src/",
                companion_repo_scopes=[
                    f"{companion_a}=pkg/",
                    f"{companion_b}=lib/",
                ],
            )
            self.assertEqual(launched["status"], "running")

            stopped = self.run_script(
                "autoresearch_runtime_ctl.py",
                "stop",
                "--repo",
                str(primary),
            )
            self.assertEqual(stopped["status"], "stopped")

            switched = self.run_script(
                "autoresearch_set_session_mode.py",
                "--repo",
                str(primary),
                "--session-mode",
                "foreground",
            )
            self.assertEqual(switched["session_mode"], "foreground")

            state = json.loads((primary / "autoresearch-state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["config"]["session_mode"], "foreground")
            self.assertNotIn("execution_policy", state["config"])
            self.assertTrue((primary / "autoresearch-launch.json").exists())
            self.assertTrue((primary / "autoresearch-runtime.json").exists())

            restarted = self.run_script(
                "autoresearch_runtime_ctl.py",
                "start",
                "--repo",
                str(primary),
                "--codex-bin",
                str(fake_codex_path),
            )
            self.assertEqual(restarted["status"], "running")

            state = json.loads((primary / "autoresearch-state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["config"]["session_mode"], "background")
            self.assertEqual(state["config"]["execution_policy"], "danger_full_access")

            stopped = self.run_script(
                "autoresearch_runtime_ctl.py",
                "stop",
                "--repo",
                str(primary),
            )
            self.assertEqual(stopped["status"], "stopped")

    def test_runtime_launch_fresh_start_in_git_repo_accepts_prev_archives(self) -> None:
        with tempfile.TemporaryDirectory() as repo_tmp, tempfile.TemporaryDirectory() as tool_tmp:
            repo = Path(repo_tmp)
            tool_dir = Path(tool_tmp)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.email", "a@b.c"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)

            fake_codex_path = tool_dir / "fake-codex"
            self.write_sleeping_fake_codex(fake_codex_path)

            (repo / "research-results.tsv").write_text(
                "iteration\tcommit\tmetric\tdelta\tguard\tstatus\tdescription\n"
                "0\tabc1234\t10\t0\t-\tbaseline\told baseline\n",
                encoding="utf-8",
            )
            (repo / "autoresearch-state.json").write_text("{}\n", encoding="utf-8")
            (repo / "autoresearch-launch.json").write_text("{}\n", encoding="utf-8")
            (repo / "autoresearch-runtime.json").write_text(
                json.dumps(
                    {
                        "version": 1,
                        "repo": str(repo),
                        "launch_path": str(repo / "autoresearch-launch.json"),
                        "results_path": str(repo / "research-results.tsv"),
                        "state_path": str(repo / "autoresearch-state.json"),
                        "log_path": str(repo / "autoresearch-runtime.log"),
                        "status": "terminal",
                        "terminal_reason": "completed",
                        "pid": 12345,
                        "pgid": None,
                        "command": [],
                        "requested_stop_at": None,
                        "last_decision": "stop",
                        "last_reason": "completed",
                        "last_seen_iteration": 0,
                        "last_seen_status": "baseline",
                        "created_at": "2026-03-21T00:00:00Z",
                        "updated_at": "2026-03-21T00:00:00Z",
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            launched = self.launch_runtime(
                repo,
                fake_codex_path=fake_codex_path,
                original_goal="New goal",
                goal="Reduce failures",
                fresh_start=True,
            )
            self.assertEqual(launched["status"], "running")
            self.assertTrue((repo / "research-results.prev.tsv").exists())
            self.assertTrue((repo / "autoresearch-state.prev.json").exists())
            self.assertTrue((repo / "autoresearch-launch.prev.json").exists())
            self.assertTrue((repo / "autoresearch-runtime.prev.json").exists())

            stopped = self.run_script(
                "autoresearch_runtime_ctl.py",
                "stop",
                "--repo",
                str(repo),
            )
            self.assertEqual(stopped["status"], "stopped")

    def test_runtime_launch_fresh_start_refuses_when_runtime_is_alive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            fake_codex_path = tmpdir / "fake-codex"
            self.write_sleeping_fake_codex(fake_codex_path)

            sleeper = subprocess.Popen(["sleep", "30"])
            try:
                (tmpdir / "autoresearch-launch.json").write_text(
                    json.dumps({"status": "stale manifest"}, indent=2) + "\n",
                    encoding="utf-8",
                )
                runtime_path = tmpdir / "autoresearch-runtime.json"
                runtime_path.write_text(
                    json.dumps(
                        {
                            "version": 1,
                            "repo": str(tmpdir),
                            "launch_path": str(tmpdir / "autoresearch-launch.json"),
                            "results_path": str(tmpdir / "research-results.tsv"),
                            "state_path": str(tmpdir / "autoresearch-state.json"),
                            "log_path": str(tmpdir / "autoresearch-runtime.log"),
                            "status": "running",
                            "terminal_reason": "none",
                            "pid": sleeper.pid,
                            "pgid": None,
                            "command": [],
                            "requested_stop_at": None,
                            "last_decision": "",
                            "last_reason": "",
                            "last_seen_iteration": None,
                            "last_seen_status": "",
                            "created_at": "2026-03-21T00:00:00Z",
                            "updated_at": "2026-03-21T00:00:00Z",
                        },
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                completed = self.run_script_completed(
                    "autoresearch_runtime_ctl.py",
                    "launch",
                    "--fresh-start",
                    "--repo",
                    str(tmpdir),
                    "--original-goal",
                    "New goal",
                    "--mode",
                    "loop",
                    "--goal",
                    "Reduce failures",
                    "--scope",
                    "src/**/*.py",
                    "--metric-name",
                    "failure count",
                    "--direction",
                    "lower",
                    "--verify",
                    "python3 -c pass",
                    "--guard",
                    "python -m py_compile src",
                    "--codex-bin",
                    str(fake_codex_path),
                )
                self.assertNotEqual(completed.returncode, 0)
                self.assertIn("already running", completed.stderr)
                self.assertTrue(runtime_path.exists())
                self.assertFalse((tmpdir / "autoresearch-runtime.prev.json").exists())
            finally:
                sleeper.terminate()
                sleeper.wait()

    def test_runtime_launch_fresh_start_blocks_on_invalid_runtime_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            fake_codex_path = tmpdir / "fake-codex"
            self.write_sleeping_fake_codex(fake_codex_path)

            runtime_path = tmpdir / "autoresearch-runtime.json"
            runtime_path.write_text("{bad json", encoding="utf-8")

            completed = self.run_script_completed(
                "autoresearch_runtime_ctl.py",
                "launch",
                "--fresh-start",
                "--repo",
                str(tmpdir),
                "--original-goal",
                "New goal",
                "--mode",
                "loop",
                "--goal",
                "Reduce failures",
                "--scope",
                "src/**/*.py",
                "--metric-name",
                "failure count",
                "--direction",
                "lower",
                "--verify",
                "python3 -c pass",
                "--guard",
                "python -m py_compile src",
                "--codex-bin",
                str(fake_codex_path),
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("Invalid JSON", completed.stderr)
            self.assertTrue(runtime_path.exists())
            self.assertFalse((tmpdir / "autoresearch-runtime.prev.json").exists())

    def test_runtime_status_reports_invalid_runtime_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            runtime_path = tmpdir / "autoresearch-runtime.json"
            runtime_path.write_text("{bad json", encoding="utf-8")

            status = self.run_script(
                "autoresearch_runtime_ctl.py",
                "status",
                "--repo",
                str(tmpdir),
            )
            self.assertEqual(status["status"], "needs_human")
            self.assertEqual(status["reason"], "invalid_runtime_state")
            self.assertIn("Invalid JSON", status["error"])
            self.assertEqual(status["runtime_path"], str(runtime_path.resolve()))

    def test_runtime_stop_reports_invalid_runtime_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            runtime_path = tmpdir / "autoresearch-runtime.json"
            runtime_path.write_text("{bad json", encoding="utf-8")

            stopped = self.run_script(
                "autoresearch_runtime_ctl.py",
                "stop",
                "--repo",
                str(tmpdir),
            )
            self.assertEqual(stopped["status"], "needs_human")
            self.assertEqual(stopped["reason"], "invalid_runtime_state")
            self.assertIn("Invalid JSON", stopped["error"])
            self.assertEqual(stopped["runtime_path"], str(runtime_path.resolve()))

    def test_runtime_stop_marks_needs_human_when_runner_survives_sigkill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            runtime_path = tmpdir / "autoresearch-runtime.json"
            runtime_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "repo": str(tmpdir),
                        "launch_path": str(tmpdir / "autoresearch-launch.json"),
                        "results_path": str(tmpdir / "research-results.tsv"),
                        "state_path": str(tmpdir / "autoresearch-state.json"),
                        "log_path": str(tmpdir / "autoresearch-runtime.log"),
                        "status": "running",
                        "terminal_reason": "none",
                        "pid": 4242,
                        "pgid": 4242,
                        "command": [],
                        "requested_stop_at": None,
                        "last_decision": "",
                        "last_reason": "",
                        "last_seen_iteration": None,
                        "last_seen_status": "",
                        "created_at": "2026-03-21T00:00:00Z",
                        "updated_at": "2026-03-21T00:00:00Z",
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            args = argparse.Namespace(
                repo=str(tmpdir),
                runtime_path=None,
                grace_seconds=0.0,
            )
            with (
                mock.patch.object(autoresearch_runtime_ops, "pid_is_alive", return_value=True),
                mock.patch.object(
                    autoresearch_runtime_ops,
                    "wait_for_process_exit",
                    side_effect=[False, False],
                ),
                mock.patch.object(autoresearch_runtime_ops.os, "killpg") as killpg,
            ):
                stopped = autoresearch_runtime_ops.stop_runtime(args)

            self.assertEqual(stopped["status"], "needs_human")
            self.assertEqual(stopped["reason"], "stop_failed")
            self.assertIn("remained alive after SIGKILL", stopped["error"])
            self.assertEqual(
                killpg.call_args_list,
                [
                    mock.call(4242, autoresearch_runtime_ops.signal.SIGTERM),
                    mock.call(4242, autoresearch_runtime_ops.signal.SIGKILL),
                ],
            )
            runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
            self.assertEqual(runtime["status"], "needs_human")
            self.assertEqual(runtime["terminal_reason"], "stop_failed")
            self.assertIn("remained alive after SIGKILL", runtime["last_error"])

    def test_runtime_status_reports_stop_failed_even_if_pid_still_alive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            runtime_path = tmpdir / "autoresearch-runtime.json"
            runtime_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "repo": str(tmpdir),
                        "launch_path": str(tmpdir / "autoresearch-launch.json"),
                        "results_path": str(tmpdir / "research-results.tsv"),
                        "state_path": str(tmpdir / "autoresearch-state.json"),
                        "log_path": str(tmpdir / "autoresearch-runtime.log"),
                        "status": "stopped",
                        "terminal_reason": "user_stopped",
                        "pid": 4242,
                        "pgid": 4242,
                        "command": [],
                        "requested_stop_at": "2026-03-21T00:00:00Z",
                        "last_decision": "",
                        "last_reason": "",
                        "last_seen_iteration": None,
                        "last_seen_status": "",
                        "last_error": "Runtime process 4242 remained alive after SIGKILL.",
                        "created_at": "2026-03-21T00:00:00Z",
                        "updated_at": "2026-03-21T00:00:00Z",
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            with mock.patch.object(autoresearch_runtime_ops, "pid_is_alive", return_value=True):
                status = autoresearch_runtime_ops.runtime_summary(
                    repo=tmpdir,
                    results_path=tmpdir / "research-results.tsv",
                    state_path_arg=None,
                    launch_path=tmpdir / "autoresearch-launch.json",
                    runtime_path=runtime_path,
                )

            self.assertEqual(status["status"], "needs_human")
            self.assertEqual(status["reason"], "stop_failed")
            self.assertTrue(status["runtime_running"])
            self.assertIn("remained alive after SIGKILL", status["error"])

    def test_runtime_launch_blocks_when_codex_bin_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)

            completed = self.run_script_completed(
                "autoresearch_runtime_ctl.py",
                "launch",
                "--repo",
                str(tmpdir),
                "--original-goal",
                "New goal",
                "--mode",
                "loop",
                "--goal",
                "Reduce failures",
                "--scope",
                "src/**/*.py",
                "--metric-name",
                "failure count",
                "--direction",
                "lower",
                "--verify",
                "python3 -c pass",
                "--guard",
                "python -m py_compile src",
                "--codex-bin",
                "definitely-not-a-real-codex-bin",
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("Codex executable is not available", completed.stderr)
            self.assertFalse((tmpdir / "autoresearch-runtime.json").exists())

    def test_runtime_launch_blocks_on_out_of_scope_companion_repo_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            primary = root / "primary"
            companion = root / "companion"
            primary.mkdir()
            companion.mkdir()
            subprocess.run(["git", "init", str(primary)], check=True, capture_output=True, text=True)
            subprocess.run(["git", "init", str(companion)], check=True, capture_output=True, text=True)
            (companion / "notes.txt").write_text("drift\n", encoding="utf-8")

            fake_codex_path = primary / "fake-codex"
            self.write_sleeping_fake_codex(fake_codex_path)

            completed = self.run_script_completed(
                "autoresearch_runtime_ctl.py",
                "launch",
                "--repo",
                str(primary),
                "--original-goal",
                "Coordinate two repos",
                "--mode",
                "loop",
                "--goal",
                "Reduce failures",
                "--scope",
                "src/**/*.py",
                "--companion-repo-scope",
                f"{companion}=pkg/",
                "--metric-name",
                "failure count",
                "--direction",
                "lower",
                "--verify",
                "python3 -c pass",
                "--guard",
                "python -m py_compile src",
                "--codex-bin",
                str(fake_codex_path),
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("Runtime preflight failed", completed.stderr)
            self.assertIn("notes.txt", completed.stderr)
            self.assertFalse((primary / "autoresearch-runtime.json").exists())

    def test_runtime_run_marks_needs_human_when_codex_exec_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            self.create_launch_manifest(tmpdir)

            completed = self.run_script_completed(
                "autoresearch_runtime_ctl.py",
                "run",
                "--repo",
                str(tmpdir),
                "--codex-bin",
                "definitely-not-a-real-codex-bin",
                "--sleep-seconds",
                "0",
                "--max-stagnation",
                "1",
            )
            self.assertNotEqual(completed.returncode, 0)
            runtime = json.loads((tmpdir / "autoresearch-runtime.json").read_text(encoding="utf-8"))
            self.assertEqual(runtime["status"], "needs_human")
            self.assertEqual(runtime["terminal_reason"], "codex_exec_unavailable")
            self.assertIn("Codex executable is not available", runtime["last_error"])

            status = self.run_script(
                "autoresearch_runtime_ctl.py",
                "status",
                "--repo",
                str(tmpdir),
            )
            self.assertEqual(status["status"], "needs_human")
            self.assertEqual(status["reason"], "codex_exec_unavailable")
            self.assertIn("Codex executable is not available", status["error"])

    def test_runtime_stop_appends_summary_lesson_when_state_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            results_path = tmpdir / "research-results.tsv"
            state_path = tmpdir / "autoresearch-state.json"
            fake_codex_path = tmpdir / "fake-codex"
            lessons_path = tmpdir / "autoresearch-lessons.md"

            self.create_launch_manifest(tmpdir)
            self.write_sleeping_fake_codex(fake_codex_path)
            self.run_script(
                "autoresearch_init_run.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
                "--mode",
                "loop",
                "--goal",
                "Reduce failures",
                "--scope",
                "src/**/*.py",
                "--metric-name",
                "failure count",
                "--direction",
                "lower",
                "--verify",
                "pytest -q",
                "--baseline-metric",
                "10",
                "--baseline-commit",
                "a1b2c3d",
                "--baseline-description",
                "baseline failures",
            )

            self.run_script(
                "autoresearch_runtime_ctl.py",
                "start",
                "--repo",
                str(tmpdir),
                "--codex-bin",
                str(fake_codex_path),
            )
            self.wait_for_runtime_status(tmpdir, {"running"})
            self.run_script(
                "autoresearch_runtime_ctl.py",
                "stop",
                "--repo",
                str(tmpdir),
            )

            entries = self.run_script(
                "autoresearch_lessons.py",
                "list",
                "--lessons-path",
                str(lessons_path),
            )
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["outcome"], "summary")
            self.assertEqual(entries[0]["iteration"], "0")

    def test_runtime_controller_can_start_report_running_and_stop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            fake_codex_path = tmpdir / "fake-codex"
            self.create_launch_manifest(tmpdir)
            self.write_sleeping_fake_codex(fake_codex_path)

            started = self.run_script(
                "autoresearch_runtime_ctl.py",
                "start",
                "--repo",
                str(tmpdir),
                "--codex-bin",
                str(fake_codex_path),
            )
            self.assertEqual(started["status"], "running")

            running = self.wait_for_runtime_status(tmpdir, {"running"})
            self.assertEqual(running["status"], "running")

            gate = self.run_script(
                "autoresearch_launch_gate.py",
                "--repo",
                str(tmpdir),
            )
            self.assertEqual(gate["decision"], "blocked_start")
            self.assertEqual(gate["reason"], "already_running")

            stopped = self.run_script(
                "autoresearch_runtime_ctl.py",
                "stop",
                "--repo",
                str(tmpdir),
            )
            self.assertEqual(stopped["status"], "stopped")

            final_status = self.wait_for_runtime_status(tmpdir, {"stopped"})
            self.assertEqual(final_status["status"], "stopped")

    def test_runtime_invariants_script_accepts_stopped_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            fake_codex_path = tmpdir / "fake-codex"
            self.write_sleeping_fake_codex(fake_codex_path)

            self.launch_runtime(tmpdir, fake_codex_path=fake_codex_path)
            self.wait_for_runtime_status(tmpdir, {"running"})
            self.run_script(
                "autoresearch_runtime_ctl.py",
                "stop",
                "--repo",
                str(tmpdir),
            )

            completed = self.run_script_completed(
                "check_skill_invariants.py",
                "runtime",
                "--repo",
                str(tmpdir),
            )
            completed.check_returncode()
            self.assertIn("runtime invariants: OK", completed.stdout)

    def test_runtime_controller_relaunches_and_then_stops_for_blocked_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            results_path = tmpdir / "research-results.tsv"
            state_path = tmpdir / "autoresearch-state.json"
            fake_codex_path = tmpdir / "fake-codex"
            counter_path = tmpdir / ".fake-codex-count"

            self.create_launch_manifest(tmpdir)
            self.write_fake_codex(
                fake_codex_path,
                body_lines=[
                    'repo=""',
                    'while [[ $# -gt 0 ]]; do',
                    '  case "$1" in',
                    '    -C) repo="$2"; shift 2 ;;',
                    '    *) shift ;;',
                    '  esac',
                    'done',
                    'if [[ -n "$repo" ]]; then cd "$repo"; fi',
                    f'counter_path="{counter_path}"',
                    'count=0',
                    'if [[ -f "$counter_path" ]]; then count="$(cat "$counter_path")"; fi',
                    'count=$((count + 1))',
                    'printf "%s" "$count" > "$counter_path"',
                    f'python_bin="{sys.executable}"',
                    f'init_script="{SCRIPTS_DIR / "autoresearch_init_run.py"}"',
                    f'record_script="{SCRIPTS_DIR / "autoresearch_record_iteration.py"}"',
                    'if [[ "$count" -eq 1 ]]; then',
                    '  "$python_bin" "$init_script" --results-path research-results.tsv --state-path autoresearch-state.json --mode loop --session-mode background --goal "Reduce failures" --scope "src/**/*.py" --metric-name "failure count" --direction lower --verify "pytest -q" --baseline-metric 10 --baseline-commit a1b2c3d --baseline-description "baseline failures"',
                    '  "$python_bin" "$record_script" --results-path research-results.tsv --state-path autoresearch-state.json --status pivot --description "close this branch and continue with a new strategy"',
                    "else",
                    '  "$python_bin" "$record_script" --results-path research-results.tsv --state-path autoresearch-state.json --status blocked --description "external dependency vanished"',
                    "fi",
                ],
            )

            started = self.run_script(
                "autoresearch_runtime_ctl.py",
                "start",
                "--repo",
                str(tmpdir),
                "--codex-bin",
                str(fake_codex_path),
                "--sleep-seconds",
                "0",
                "--max-stagnation",
                "3",
            )
            self.assertEqual(started["status"], "running")

            status = self.wait_for_runtime_status(tmpdir, {"needs_human"})
            self.assertEqual(status["status"], "needs_human")
            self.assertEqual(status["reason"], "blocked")
            self.assertEqual(counter_path.read_text(encoding="utf-8"), "2")

            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["state"]["iteration"], 2)
            self.assertEqual(state["state"]["last_status"], "blocked")
            self.assertEqual(state["config"]["session_mode"], "background")
            self.assertEqual(state["supervisor"]["recommended_action"], "needs_human")
            self.assertEqual(state["supervisor"]["terminal_reason"], "blocked")
            self.assertEqual(state["supervisor"]["restart_count"], 2)

            runtime = json.loads((tmpdir / "autoresearch-runtime.json").read_text(encoding="utf-8"))
            self.assertEqual(runtime["status"], "needs_human")
            self.assertEqual(runtime["terminal_reason"], "blocked")
            self.assertTrue(results_path.exists())
            self.assertTrue(state_path.exists())

    def test_runtime_controller_uses_codex_exec_with_prompt_on_stdin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            results_path = tmpdir / "research-results.tsv"
            state_path = tmpdir / "autoresearch-state.json"
            fake_codex_path = tmpdir / "fake-codex"
            prompt_path = tmpdir / ".runtime-prompt.txt"
            args_path = tmpdir / ".codex-args.txt"

            self.create_launch_manifest(
                tmpdir,
                original_goal="Reduce failures in this repo",
                goal="Reduce failures",
            )
            self.write_fake_codex(
                fake_codex_path,
                body_lines=[
                    'if [[ "${1:-}" != "exec" ]]; then',
                    '  echo "expected codex exec" >&2',
                    "  exit 64",
                    "fi",
                    "shift",
                    'repo=""',
                    "prompt_from_stdin=0",
                    f'prompt_path="{prompt_path}"',
                    f'args_path="{args_path}"',
                    'printf "%s\\n" "$@" >"$args_path"',
                    'while [[ $# -gt 0 ]]; do',
                    '  case "$1" in',
                    '    -C) repo="$2"; shift 2 ;;',
                    '    -) prompt_from_stdin=1; shift ;;',
                    '    *) shift ;;',
                    '  esac',
                    'done',
                    'if [[ "$prompt_from_stdin" -ne 1 ]]; then',
                    '  echo "expected prompt from stdin" >&2',
                    "  exit 65",
                    "fi",
                    'cat >"$prompt_path"',
                    'if [[ -n "$repo" ]]; then cd "$repo"; fi',
                    f'python_bin="{sys.executable}"',
                    f'init_script="{SCRIPTS_DIR / "autoresearch_init_run.py"}"',
                    f'record_script="{SCRIPTS_DIR / "autoresearch_record_iteration.py"}"',
                    'if [[ ! -f "research-results.tsv" ]]; then',
                    '  "$python_bin" "$init_script" --results-path research-results.tsv --state-path autoresearch-state.json --mode loop --session-mode background --goal "Reduce failures" --scope "src/**/*.py" --metric-name "failure count" --direction lower --verify "pytest -q" --baseline-metric 10 --baseline-commit a1b2c3d --baseline-description "baseline failures"',
                    "fi",
                    '  "$python_bin" "$record_script" --results-path research-results.tsv --state-path autoresearch-state.json --status blocked --description "validation complete"',
                ],
            )

            started = self.run_script(
                "autoresearch_runtime_ctl.py",
                "start",
                "--repo",
                str(tmpdir),
                "--codex-bin",
                str(fake_codex_path),
                "--sleep-seconds",
                "0",
                "--max-stagnation",
                "2",
            )
            self.assertEqual(started["status"], "running")

            status = self.wait_for_runtime_status(tmpdir, {"needs_human"})
            self.assertEqual(status["reason"], "blocked")
            prompt_text = prompt_path.read_text(encoding="utf-8")
            codex_args = args_path.read_text(encoding="utf-8")
            self.assertIn("$codex-autoresearch", prompt_text)
            self.assertIn("Reduce failures in this repo", prompt_text)
            self.assertIn("--dangerously-bypass-approvals-and-sandbox", codex_args)
            self.assertNotIn("--full-auto", codex_args)
            self.assertTrue(results_path.exists())
            self.assertTrue(state_path.exists())

    def test_runtime_controller_honors_workspace_write_execution_policy_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            fake_codex_path = tmpdir / "fake-codex"
            args_path = tmpdir / ".codex-args.txt"

            self.create_launch_manifest(
                tmpdir,
                execution_policy="workspace_write",
            )
            self.write_fake_codex(
                fake_codex_path,
                body_lines=[
                    'if [[ "${1:-}" != "exec" ]]; then',
                    '  echo "expected codex exec" >&2',
                    "  exit 64",
                    "fi",
                    "shift",
                    f'args_path="{args_path}"',
                    'printf "%s\\n" "$@" >"$args_path"',
                    "cat >/dev/null",
                    f'python_bin="{sys.executable}"',
                    f'init_script="{SCRIPTS_DIR / "autoresearch_init_run.py"}"',
                    f'record_script="{SCRIPTS_DIR / "autoresearch_record_iteration.py"}"',
                    'if [[ ! -f "research-results.tsv" ]]; then',
                    '  "$python_bin" "$init_script" --results-path research-results.tsv --state-path autoresearch-state.json --mode loop --session-mode background --goal "Reduce failures" --scope "src/**/*.py" --metric-name "failure count" --direction lower --verify "pytest -q" --execution-policy workspace_write --baseline-metric 10 --baseline-commit a1b2c3d --baseline-description "baseline failures"',
                    "fi",
                    '  "$python_bin" "$record_script" --results-path research-results.tsv --state-path autoresearch-state.json --status blocked --description "validation complete"',
                ],
            )

            self.run_script(
                "autoresearch_runtime_ctl.py",
                "start",
                "--repo",
                str(tmpdir),
                "--codex-bin",
                str(fake_codex_path),
                "--sleep-seconds",
                "0",
                "--max-stagnation",
                "2",
            )
            self.wait_for_runtime_status(tmpdir, {"needs_human"})
            codex_args = args_path.read_text(encoding="utf-8")
            self.assertIn("--full-auto", codex_args)
            self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", codex_args)

    def test_runtime_controller_retries_preinit_failures_then_stops(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            fake_codex_path = tmpdir / "fake-codex"
            counter_path = tmpdir / ".fake-codex-count"

            self.create_launch_manifest(tmpdir)
            self.write_fake_codex(
                fake_codex_path,
                body_lines=[
                    'repo=""',
                    'while [[ $# -gt 0 ]]; do',
                    '  case "$1" in',
                    '    -C) repo="$2"; shift 2 ;;',
                    '    *) shift ;;',
                    '  esac',
                    'done',
                    'if [[ -n "$repo" ]]; then cd "$repo"; fi',
                    f'counter_path="{counter_path}"',
                    'count=0',
                    'if [[ -f "$counter_path" ]]; then count="$(cat "$counter_path")"; fi',
                    'count=$((count + 1))',
                    'printf "%s" "$count" > "$counter_path"',
                    "exit 1",
                ],
            )

            self.run_script(
                "autoresearch_runtime_ctl.py",
                "start",
                "--repo",
                str(tmpdir),
                "--codex-bin",
                str(fake_codex_path),
                "--sleep-seconds",
                "0",
                "--max-stagnation",
                "2",
            )
            status = self.wait_for_runtime_status(tmpdir, {"needs_human"})
            self.assertEqual(status["status"], "needs_human")
            self.assertEqual(status["reason"], "startup_failed_before_artifacts")
            self.assertEqual(counter_path.read_text(encoding="utf-8"), "2")
