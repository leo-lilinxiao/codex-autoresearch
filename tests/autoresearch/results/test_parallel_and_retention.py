from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from ..base import AutoresearchScriptsTestBase, REPO_ROOT, SCRIPTS_DIR


class AutoresearchParallelRetentionTest(AutoresearchScriptsTestBase):
    maxDiff = None

    def test_parallel_batch_uses_best_discarded_attempt_when_nothing_keeps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            results_path = tmpdir / "autoresearch-results/results.tsv"
            state_path = tmpdir / "autoresearch-results/state.json"
            batch_path = self.artifact_root(tmpdir) / "batch.json"

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
                "python3 -c pass",
                "--baseline-metric",
                "10",
                "--baseline-commit",
                "a1b2c3d",
                "--baseline-description",
                "baseline failures",
                "--parallel-mode",
                "parallel",
            )
            batch_path.write_text(
                json.dumps(
                    [
                        {
                            "worker_id": "a",
                            "commit": "c3d4e5f",
                            "metric": 12,
                            "guard": "pass",
                            "description": "worse attempt",
                        },
                        {
                            "worker_id": "b",
                            "commit": "d4e5f6a",
                            "metric": 11,
                            "guard": "pass",
                            "description": "closer miss",
                        },
                    ]
                ),
                encoding="utf-8",
            )

            result = self.run_script(
                "autoresearch_select_parallel_batch.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
                "--batch-file",
                str(batch_path),
            )
            self.assertIsNone(result["selected_worker"])
            self.assertEqual(result["status"], "discard")

            log_text = results_path.read_text(encoding="utf-8")
            self.assertIn("1\td4e5f6a\t11\t+1\tpass\tdiscard", log_text)

            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["state"]["current_metric"], 10)
            self.assertEqual(state["state"]["last_trial_metric"], 11)
            self.assertEqual(state["state"]["last_trial_commit"], "d4e5f6a")

    def test_parallel_batch_keep_requires_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            results_path = tmpdir / "autoresearch-results/results.tsv"
            state_path = tmpdir / "autoresearch-results/state.json"
            batch_path = self.artifact_root(tmpdir) / "batch.json"

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
                "python3 -c pass",
                "--baseline-metric",
                "10",
                "--baseline-commit",
                "a1b2c3d",
                "--baseline-description",
                "baseline failures",
                "--parallel-mode",
                "parallel",
            )
            batch_path.write_text(
                json.dumps(
                    [
                        {
                            "worker_id": "a",
                            "metric": 8,
                            "guard": "pass",
                            "description": "better attempt without commit",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            completed = self.run_script_completed(
                "autoresearch_select_parallel_batch.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
                "--batch-file",
                str(batch_path),
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("did not report a commit", completed.stderr)

    def test_parallel_batch_keep_preserves_supervisor_and_appends_lesson(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            results_path = tmpdir / "autoresearch-results/results.tsv"
            state_path = tmpdir / "autoresearch-results/state.json"
            batch_path = self.artifact_root(tmpdir) / "batch.json"
            lessons_path = tmpdir / "autoresearch-results/lessons.md"

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
                "python3 -c pass",
                "--baseline-metric",
                "10",
                "--baseline-commit",
                "a1b2c3d",
                "--baseline-description",
                "baseline failures",
                "--parallel-mode",
                "parallel",
            )
            payload = json.loads(state_path.read_text(encoding="utf-8"))
            payload["supervisor"] = {
                "recommended_action": "relaunch",
                "should_continue": True,
                "terminal_reason": "none",
                "last_exit_kind": "turn_complete",
                "last_turn_finished_at": "2026-03-21T00:00:00Z",
                "restart_count": 1,
                "stagnation_count": 0,
            }
            state_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
            batch_path.write_text(
                json.dumps(
                    [
                        {
                            "worker_id": "a",
                            "commit": "c3d4e5f",
                            "metric": 7,
                            "guard": "pass",
                            "description": "narrowed hot path",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            self.run_script(
                "autoresearch_select_parallel_batch.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
                "--batch-file",
                str(batch_path),
            )

            updated = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(updated["supervisor"]["recommended_action"], "relaunch")
            lessons = self.run_script(
                "autoresearch_lessons.py",
                "list",
                "--lessons-path",
                str(lessons_path),
            )
            self.assertEqual(len(lessons), 1)
            self.assertEqual(lessons[0]["outcome"], "keep")
            self.assertEqual(lessons[0]["iteration"], "1")

    def test_parallel_batch_keep_updates_multi_repo_commit_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            primary = root / "primary"
            companion = root / "companion"
            primary.mkdir()
            companion.mkdir()
            results_path = primary / "autoresearch-results/results.tsv"
            state_path = primary / "autoresearch-results/state.json"
            batch_path = root / "batch.json"

            self.run_script(
                "autoresearch_init_run.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
                "--mode",
                "loop",
                "--goal",
                "Coordinate two repos",
                "--scope",
                "src/",
                "--companion-repo-scope",
                f"{companion}=lib/",
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
                "--repo-commit",
                f"{companion}=comp111",
                "--baseline-description",
                "baseline failures",
                "--parallel-mode",
                "parallel",
            )
            batch_path.write_text(
                json.dumps(
                    [
                        {
                            "worker_id": "a",
                            "commit": "keep222",
                            "repo_commits": {
                                str(companion.resolve()): "comp222",
                            },
                            "metric": 7,
                            "guard": "pass",
                            "description": "coordinated improvement",
                            "diff_size": 3,
                        }
                    ]
                ),
                encoding="utf-8",
            )

            self.run_script(
                "autoresearch_select_parallel_batch.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
                "--batch-file",
                str(batch_path),
            )

            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(
                state["state"]["last_repo_commits"],
                {
                    str(primary.resolve()): "keep222",
                    str(companion.resolve()): "comp222",
                },
            )
            self.assertEqual(state["state"]["last_trial_repo_commits"], state["state"]["last_repo_commits"])

    def test_parallel_batch_blocks_on_unexpected_worktree_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            repo = tmpdir / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
            results_path = repo / "autoresearch-results/results.tsv"
            state_path = repo / "autoresearch-results/state.json"
            batch_path = self.artifact_root(repo) / "batch.json"

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
                "python3 -c pass",
                "--baseline-metric",
                "10",
                "--baseline-commit",
                "a1b2c3d",
                "--baseline-description",
                "baseline failures",
                "--parallel-mode",
                "parallel",
            )
            (repo / "notes.txt").write_text("user drift\n", encoding="utf-8")
            batch_path.write_text(
                json.dumps(
                    [
                        {
                            "worker_id": "a",
                            "commit": "c3d4e5f",
                            "metric": 7,
                            "guard": "pass",
                            "description": "narrowed hot path",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            completed = self.run_script_completed(
                "autoresearch_select_parallel_batch.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
                "--batch-file",
                str(batch_path),
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("Parallel batch preflight failed", completed.stderr)
            self.assertIn("unexpected worktree changes before parallel batch", completed.stderr)
            log_text = results_path.read_text(encoding="utf-8")
            self.assertNotIn("[PARALLEL batch]", log_text)

    def test_drift_and_later_keep_preserve_historical_best_metric(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            results_path = tmpdir / "autoresearch-results/results.tsv"
            state_path = tmpdir / "autoresearch-results/state.json"

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
                "autoresearch_record_iteration.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
                "--status",
                "keep",
                "--metric",
                "5",
                "--commit",
                "keep001",
                "--guard",
                "pass",
                "--description",
                "strong improvement",
            )
            self.run_script(
                "autoresearch_record_iteration.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
                "--status",
                "drift",
                "--metric",
                "7",
                "--description",
                "environment drift after resume check",
            )
            self.run_script(
                "autoresearch_record_iteration.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
                "--status",
                "keep",
                "--metric",
                "6",
                "--commit",
                "keep002",
                "--guard",
                "pass",
                "--description",
                "partial recovery after drift",
            )

            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["state"]["current_metric"], 6)
            self.assertEqual(state["state"]["best_metric"], 5)
            self.assertEqual(state["state"]["best_iteration"], 1)

    def test_record_iteration_preserves_existing_supervisor_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            results_path = tmpdir / "autoresearch-results/results.tsv"
            state_path = tmpdir / "autoresearch-results/state.json"

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

            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["supervisor"] = {
                "recommended_action": "relaunch",
                "should_continue": True,
                "terminal_reason": "none",
                "last_exit_kind": "turn_complete",
                "last_turn_finished_at": "2026-03-21T00:00:00Z",
                "last_observed_signature": "sig-1",
                "last_observed_iteration": 0,
                "last_observed_status": "baseline",
                "last_observed_updated_at": state["updated_at"],
                "last_observed_metric": 10,
                "restart_count": 4,
                "stagnation_count": 1,
                "last_reason": "still making progress",
            }
            state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

            self.run_script(
                "autoresearch_record_iteration.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
                "--status",
                "discard",
                "--metric",
                "12",
                "--commit",
                "deadbee",
                "--description",
                "worse attempt",
            )

            updated = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(updated["supervisor"]["restart_count"], 4)
            self.assertEqual(updated["supervisor"]["stagnation_count"], 1)
            self.assertEqual(updated["supervisor"]["recommended_action"], "relaunch")

    def test_blocked_iteration_preserves_retained_metric_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            results_path = tmpdir / "autoresearch-results/results.tsv"
            state_path = tmpdir / "autoresearch-results/state.json"

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
                "autoresearch_record_iteration.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
                "--status",
                "keep",
                "--metric",
                "8",
                "--commit",
                "keep001",
                "--guard",
                "pass",
                "--description",
                "initial improvement",
            )
            self.run_script(
                "autoresearch_record_iteration.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
                "--status",
                "blocked",
                "--description",
                "verify command removed unexpectedly",
            )

            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["state"]["iteration"], 2)
            self.assertEqual(state["state"]["blocked"], 1)
            self.assertEqual(state["state"]["current_metric"], 8)
            self.assertEqual(state["state"]["best_metric"], 8)
            self.assertEqual(state["state"]["best_iteration"], 1)
            self.assertEqual(state["state"]["last_commit"], "keep001")
