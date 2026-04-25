from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from ..base import AutoresearchScriptsTestBase, REPO_ROOT, SCRIPTS_DIR


class AutoresearchExecStateTest(AutoresearchScriptsTestBase):
    maxDiff = None

    def test_exec_mode_uses_scratch_state_and_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            results_path = tmpdir / "autoresearch-results/results.tsv"
            repo_state_path = tmpdir / "autoresearch-results/state.json"
            scratch_state_path = Path(
                self.run_script_text(
                    "autoresearch_exec_state.py",
                    "--repo-root",
                    str(tmpdir),
                )
            )

            self.run_script(
                "autoresearch_init_run.py",
                "--results-path",
                str(results_path),
                "--mode",
                "exec",
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
                "a1b2c3d",
                "--baseline-description",
                "baseline failures",
                cwd=tmpdir,
            )
            self.run_script(
                "autoresearch_record_iteration.py",
                "--results-path",
                str(results_path),
                "--status",
                "keep",
                "--metric",
                "8",
                "--commit",
                "b2c3d4e",
                "--guard",
                "pass",
                "--description",
                "better attempt",
                cwd=tmpdir,
            )

            self.assertFalse(repo_state_path.exists())
            self.assertTrue(scratch_state_path.exists())

            state = json.loads(scratch_state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["mode"], "exec")
            self.assertEqual(state["state"]["iteration"], 1)
            self.assertEqual(state["state"]["current_metric"], 8)

            cleanup = self.run_script(
                "autoresearch_exec_state.py",
                "--repo-root",
                str(tmpdir),
                "--cleanup",
                "--json",
            )
            self.assertTrue(cleanup["removed"])
            self.assertEqual(cleanup["state_path"], str(scratch_state_path))
            self.assertFalse(scratch_state_path.exists())

    def test_exec_record_iteration_rebuilds_missing_scratch_state_from_results_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            results_path = tmpdir / "autoresearch-results/results.tsv"
            scratch_state_path = Path(
                self.run_script_text(
                    "autoresearch_exec_state.py",
                    "--repo-root",
                    str(tmpdir),
                )
            )

            self.run_script(
                "autoresearch_init_run.py",
                "--results-path",
                str(results_path),
                "--mode",
                "exec",
                "--goal",
                "Improve latency through the real production path",
                "--scope",
                "src/**/*.py",
                "--metric-name",
                "latency ms",
                "--direction",
                "lower",
                "--verify",
                "python3 -c pass",
                "--required-keep-label",
                "Real-Backend",
                "--baseline-metric",
                "10",
                "--baseline-commit",
                "base111",
                "--baseline-description",
                "baseline latency",
                cwd=tmpdir,
            )
            self.assertTrue(scratch_state_path.exists())
            scratch_state_path.unlink()

            result = self.run_script(
                "autoresearch_record_iteration.py",
                "--results-path",
                str(results_path),
                "--status",
                "keep",
                "--metric",
                "8",
                "--commit",
                "keep222",
                "--guard",
                "pass",
                "--label",
                "production-path",
                "--description",
                "optimized the live request path",
                cwd=tmpdir,
            )

            self.assertEqual(result["status"], "discard")
            self.assertEqual(result["state_path"], str(scratch_state_path))
            self.assertTrue(scratch_state_path.exists())

            state = json.loads(scratch_state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["mode"], "exec")
            self.assertEqual(state["config"]["required_keep_labels"], ["real-backend"])
            self.assertEqual(state["state"]["current_metric"], 10)
            self.assertEqual(state["state"]["best_metric"], 10)
            self.assertEqual(state["state"]["last_trial_commit"], "keep222")
            self.assertEqual(state["state"]["last_trial_metric"], 8)
            self.assertEqual(state["state"]["last_trial_labels"], ["production-path"])

            log_text = results_path.read_text(encoding="utf-8")
            self.assertIn("# required_keep_labels: real-backend", log_text)
            self.assertIn(
                "[labels: production-path] optimized the live request path "
                "[KEEP-GATE miss] missing required keep labels: real-backend",
                log_text,
            )

    def test_exec_rebuild_preserves_multi_repo_targets_from_results_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            primary = workspace / "primary"
            companion = workspace / "companion"
            self.init_git_repo(primary)
            self.init_git_repo(companion)
            results_path = self.managed_results_path(workspace)
            scratch_state_path = Path(
                self.run_script_text(
                    "autoresearch_exec_state.py",
                    "--repo-root",
                    str(workspace),
                )
            )

            self.run_script(
                "autoresearch_init_run.py",
                "--repo",
                str(primary),
                "--workspace-root",
                str(workspace),
                "--results-path",
                str(results_path),
                "--mode",
                "exec",
                "--goal",
                "Improve latency across primary and companion repos",
                "--scope",
                "src/**/*.py",
                "--companion-repo-scope",
                f"{companion}=pkg/**/*.py",
                "--metric-name",
                "latency ms",
                "--direction",
                "lower",
                "--verify",
                "python3 -c pass",
                "--baseline-metric",
                "10",
                "--baseline-commit",
                "base111",
                "--baseline-description",
                "baseline latency",
                cwd=primary,
            )
            scratch_state_path.unlink()

            result = self.run_script(
                "autoresearch_record_iteration.py",
                "--results-path",
                str(results_path),
                "--status",
                "keep",
                "--metric",
                "8",
                "--commit",
                "keep222",
                "--repo-commit",
                f"{companion}=comp333",
                "--guard",
                "pass",
                "--description",
                "optimized both repos",
                cwd=primary,
            )

            self.assertEqual(result["status"], "keep")
            state = json.loads(scratch_state_path.read_text(encoding="utf-8"))
            self.assertEqual(len(state["config"]["repos"]), 2)
            self.assertEqual(
                state["state"]["last_trial_repo_commits"][str(companion.resolve())],
                "comp333",
            )
            log_text = results_path.read_text(encoding="utf-8")
            self.assertIn("# repos_json: ", log_text)

    def test_exec_rebuild_fails_on_malformed_acceptance_criteria_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            results_path = tmpdir / "autoresearch-results/results.tsv"
            scratch_state_path = Path(
                self.run_script_text(
                    "autoresearch_exec_state.py",
                    "--repo-root",
                    str(tmpdir),
                )
            )

            self.run_script(
                "autoresearch_init_run.py",
                "--results-path",
                str(results_path),
                "--mode",
                "exec",
                "--goal",
                "Improve accuracy",
                "--scope",
                "src/**/*.py",
                "--metric-name",
                "accuracy",
                "--direction",
                "higher",
                "--verify",
                "python3 -c pass",
                "--acceptance-criteria",
                json.dumps([{"metric_key": "accuracy", "operator": ">=", "target": 0.9}]),
                "--baseline-metric",
                "0.5",
                "--baseline-commit",
                "base111",
                "--baseline-description",
                "baseline accuracy",
                cwd=tmpdir,
            )
            scratch_state_path.unlink()

            lines = results_path.read_text(encoding="utf-8").splitlines()
            for index, line in enumerate(lines):
                if line.startswith("# acceptance_criteria_json: "):
                    lines[index] = "# acceptance_criteria_json: {"
                    break
            results_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

            completed = self.run_script_completed(
                "autoresearch_record_iteration.py",
                "--results-path",
                str(results_path),
                "--status",
                "keep",
                "--metric",
                "0.95",
                "--commit",
                "keep222",
                "--guard",
                "pass",
                "--description",
                "improved accuracy",
                cwd=tmpdir,
            )

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("Malformed acceptance_criteria_json in results metadata", completed.stderr)
            self.assertFalse(scratch_state_path.exists())

    def test_exec_rebuild_fails_on_malformed_repos_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            primary = workspace / "primary"
            companion = workspace / "companion"
            self.init_git_repo(primary)
            self.init_git_repo(companion)
            results_path = self.managed_results_path(workspace)
            scratch_state_path = Path(
                self.run_script_text(
                    "autoresearch_exec_state.py",
                    "--repo-root",
                    str(workspace),
                )
            )

            self.run_script(
                "autoresearch_init_run.py",
                "--repo",
                str(primary),
                "--workspace-root",
                str(workspace),
                "--results-path",
                str(results_path),
                "--mode",
                "exec",
                "--goal",
                "Improve latency across primary and companion repos",
                "--scope",
                "src/**/*.py",
                "--companion-repo-scope",
                f"{companion}=pkg/**/*.py",
                "--metric-name",
                "latency ms",
                "--direction",
                "lower",
                "--verify",
                "python3 -c pass",
                "--baseline-metric",
                "10",
                "--baseline-commit",
                "base111",
                "--baseline-description",
                "baseline latency",
                cwd=primary,
            )
            scratch_state_path.unlink()

            lines = results_path.read_text(encoding="utf-8").splitlines()
            for index, line in enumerate(lines):
                if line.startswith("# repos_json: "):
                    lines[index] = "# repos_json: {"
                    break
            results_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

            completed = self.run_script_completed(
                "autoresearch_record_iteration.py",
                "--results-path",
                str(results_path),
                "--status",
                "keep",
                "--metric",
                "8",
                "--commit",
                "keep222",
                "--repo-commit",
                f"{companion}=comp333",
                "--guard",
                "pass",
                "--description",
                "optimized both repos",
                cwd=primary,
            )

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("Malformed repos_json in results metadata", completed.stderr)
            self.assertFalse(scratch_state_path.exists())

    def test_exec_rebuild_fails_on_legacy_required_keep_criteria_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            results_path = tmpdir / "autoresearch-results/results.tsv"
            scratch_state_path = Path(
                self.run_script_text(
                    "autoresearch_exec_state.py",
                    "--repo-root",
                    str(tmpdir),
                )
            )

            self.run_script(
                "autoresearch_init_run.py",
                "--results-path",
                str(results_path),
                "--mode",
                "exec",
                "--goal",
                "Improve accuracy",
                "--scope",
                "src/**/*.py",
                "--metric-name",
                "accuracy",
                "--direction",
                "higher",
                "--verify",
                "python3 -c pass",
                "--required-keep-criteria",
                json.dumps([{"metric_key": "accuracy", "operator": ">=", "target": 0.9}]),
                "--baseline-metric",
                "0.5",
                "--baseline-commit",
                "base111",
                "--baseline-description",
                "baseline accuracy",
                cwd=tmpdir,
            )
            scratch_state_path.unlink()

            lines = results_path.read_text(encoding="utf-8").splitlines()
            for index, line in enumerate(lines):
                if line.startswith("# required_keep_criteria_json: "):
                    lines[index] = (
                        '# required_keep_criteria_json: [{"metric":"accuracy","op":">=","value":0.9}]'
                    )
                    break
            results_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

            completed = self.run_script_completed(
                "autoresearch_record_iteration.py",
                "--results-path",
                str(results_path),
                "--status",
                "keep",
                "--metric",
                "0.95",
                "--commit",
                "keep222",
                "--guard",
                "pass",
                "--description",
                "improved accuracy",
                cwd=tmpdir,
            )

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("Malformed required_keep_criteria_json in results metadata", completed.stderr)
            self.assertIn("metric_key", completed.stderr)
            self.assertFalse(scratch_state_path.exists())

    def test_resume_check_defaults_to_exec_scratch_when_log_declares_exec_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            results_path = tmpdir / "autoresearch-results/results.tsv"
            scratch_state_path = Path(
                self.run_script_text(
                    "autoresearch_exec_state.py",
                    "--repo-root",
                    str(tmpdir),
                )
            )

            self.run_script(
                "autoresearch_init_run.py",
                "--results-path",
                str(results_path),
                "--mode",
                "exec",
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
                "a1b2c3d",
                "--baseline-description",
                "baseline failures",
                cwd=tmpdir,
            )
            self.run_script(
                "autoresearch_record_iteration.py",
                "--results-path",
                str(results_path),
                "--status",
                "keep",
                "--metric",
                "8",
                "--commit",
                "b2c3d4e",
                "--guard",
                "pass",
                "--description",
                "better attempt",
                cwd=tmpdir,
            )

            resume = self.run_script(
                "autoresearch_resume_check.py",
                "--results-path",
                str(results_path),
                cwd=tmpdir,
            )
            self.assertEqual(resume["decision"], "full_resume")
            self.assertEqual(resume["state_path"], str(scratch_state_path))

    def test_exec_init_run_clears_stale_default_scratch_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
            scratch_state_path = Path(
                self.run_script_text(
                    "autoresearch_exec_state.py",
                    "--repo-root",
                    str(repo),
                )
            )
            scratch_state_path.parent.mkdir(parents=True, exist_ok=True)
            scratch_state_path.write_text('{"stale": true}\n', encoding="utf-8")

            result = self.run_script(
                "autoresearch_init_run.py",
                "--mode",
                "exec",
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
                "a1b2c3d",
                "--baseline-description",
                "baseline failures",
                cwd=repo,
            )

            self.assertEqual(result["state_path"], str(scratch_state_path))
            state = json.loads(scratch_state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["mode"], "exec")
            self.assertEqual(state["config"]["goal"], "Reduce failures")
            self.assertEqual(state["config"]["execution_policy"], "danger_full_access")
            self.assertFalse(state.get("stale", False))

    def test_exec_init_run_archives_prior_results_and_repo_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
            results_path = repo / "autoresearch-results/results.tsv"
            repo_state_path = repo / "autoresearch-results/state.json"
            prev_results_path = repo / "autoresearch-results/results.prev.tsv"
            prev_state_path = repo / "autoresearch-results/state.prev.json"
            results_path.parent.mkdir(parents=True, exist_ok=True)

            results_path.write_text("legacy results\n", encoding="utf-8")
            repo_state_path.write_text('{"legacy": true}\n', encoding="utf-8")

            result = self.run_script(
                "autoresearch_init_run.py",
                "--mode",
                "exec",
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
                "--iterations",
                "5",
                "--baseline-metric",
                "10",
                "--baseline-commit",
                "a1b2c3d",
                "--baseline-description",
                "baseline failures",
                cwd=repo,
            )

            self.assertTrue(results_path.exists())
            self.assertTrue(prev_results_path.exists())
            self.assertEqual(prev_results_path.read_text(encoding="utf-8"), "legacy results\n")
            self.assertFalse(repo_state_path.exists())
            self.assertTrue(prev_state_path.exists())
            self.assertEqual(prev_state_path.read_text(encoding="utf-8"), '{"legacy": true}\n')
            self.assertNotEqual(Path(result["state_path"]), repo_state_path)
            self.assertTrue(Path(result["state_path"]).exists())

    def test_exec_init_run_from_subdir_archives_repo_root_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
            subdir = repo / "sub"
            subdir.mkdir()
            repo_state_path = repo / "autoresearch-results/state.json"
            prev_state_path = repo / "autoresearch-results/state.prev.json"
            results_path = repo / "autoresearch-results/results.tsv"
            repo_state_path.parent.mkdir(parents=True, exist_ok=True)

            repo_state_path.write_text('{"legacy": true}\n', encoding="utf-8")

            result = self.run_script(
                "autoresearch_init_run.py",
                "--mode",
                "exec",
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
                "--iterations",
                "5",
                "--baseline-metric",
                "10",
                "--baseline-commit",
                "a1b2c3d",
                "--baseline-description",
                "baseline failures",
                cwd=subdir,
            )

            self.assertTrue(results_path.exists())
            self.assertFalse(repo_state_path.exists())
            self.assertTrue(prev_state_path.exists())
            self.assertEqual(prev_state_path.read_text(encoding="utf-8"), '{"legacy": true}\n')
            self.assertTrue(Path(result["state_path"]).exists())

    def test_exec_init_run_blocks_dirty_worktree_before_launch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
            (repo / "notes.txt").write_text("user drift\n", encoding="utf-8")

            completed = self.run_script_completed(
                "autoresearch_init_run.py",
                "--mode",
                "exec",
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
                "--iterations",
                "5",
                "--baseline-metric",
                "10",
                "--baseline-commit",
                "a1b2c3d",
                "--baseline-description",
                "baseline failures",
                cwd=repo,
            )
            self.assertEqual(completed.returncode, 2)
            self.assertIn("Exec prelaunch failed", completed.stderr)
            self.assertIn("unexpected worktree changes before launch", completed.stderr)
            self.assertFalse((repo / "autoresearch-results/results.tsv").exists())

    def test_record_iteration_does_not_use_exec_scratch_for_loop_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            results_path = tmpdir / "autoresearch-results/results.tsv"
            scratch_state_path = Path(
                self.run_script_text(
                    "autoresearch_exec_state.py",
                    "--repo-root",
                    str(tmpdir),
                )
            )
            results_path.parent.mkdir(parents=True, exist_ok=True)

            results_path.write_text(
                "\n".join(
                    [
                        "# metric_direction: lower",
                        "# mode: loop",
                        "iteration\tcommit\tmetric\tdelta\tguard\tstatus\tdescription",
                        "0\tbase123\t10\t0\t-\tbaseline\tbaseline score",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            scratch_state_path.parent.mkdir(parents=True, exist_ok=True)
            scratch_state_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "mode": "exec",
                        "config": {
                            "goal": "Reduce failures",
                            "scope": "src/**/*.py",
                            "metric": "failure count",
                            "direction": "lower",
                            "verify": "pytest -q",
                            "guard": None,
                        },
                        "state": {
                            "iteration": 0,
                            "baseline_metric": 10,
                            "best_metric": 10,
                            "best_iteration": 0,
                            "current_metric": 10,
                            "last_commit": "base123",
                            "last_trial_commit": "base123",
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
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            completed = self.run_script_completed(
                "autoresearch_record_iteration.py",
                "--results-path",
                str(results_path),
                "--status",
                "discard",
                "--metric",
                "12",
                "--commit",
                "deadbee",
                "--description",
                "worse attempt",
                cwd=tmpdir,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("Missing JSON file:", completed.stderr)
            self.assertIn("autoresearch-results/state.json", completed.stderr)

    def test_record_iteration_uses_repo_state_for_absolute_results_path_outside_repo_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
            results_path = repo / "autoresearch-results/results.tsv"
            state_path = repo / "autoresearch-results/state.json"
            self.run_script(
                "autoresearch_init_run.py",
                "--results-path",
                str(results_path),
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
                "--baseline-metric",
                "10",
                "--baseline-commit",
                "a1b2c3d",
                "--baseline-description",
                "baseline failures",
                cwd=REPO_ROOT.parent,
            )

            result = self.run_script(
                "autoresearch_record_iteration.py",
                "--results-path",
                str(results_path),
                "--status",
                "keep",
                "--metric",
                "8",
                "--commit",
                "keep123",
                "--guard",
                "pass",
                "--description",
                "reduced failures",
                cwd=REPO_ROOT.parent,
            )
            self.assertEqual(Path(str(result["state_path"])).resolve(), state_path.resolve())
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["state"]["iteration"], 1)
            self.assertEqual(state["state"]["current_metric"], 8)
