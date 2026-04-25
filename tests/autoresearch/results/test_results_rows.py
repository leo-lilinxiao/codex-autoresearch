from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from ..base import AutoresearchScriptsTestBase, REPO_ROOT, SCRIPTS_DIR


class AutoresearchResultsRowsTest(AutoresearchScriptsTestBase):
    maxDiff = None

    def test_init_and_serial_iteration_state_is_consistent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            results_path = tmpdir / "autoresearch-results/results.tsv"
            state_path = tmpdir / "autoresearch-results/state.json"
            results_path.parent.mkdir(parents=True, exist_ok=True)
            results_path.parent.mkdir(parents=True, exist_ok=True)

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
            )
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
                "b2c3d4e",
                "--guard",
                "pass",
                "--description",
                "better attempt",
            )

            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["config"]["session_mode"], "foreground")
            self.assertNotIn("execution_policy", state["config"])
            self.assertEqual(state["state"]["iteration"], 2)
            self.assertEqual(state["state"]["current_metric"], 8)
            self.assertEqual(state["state"]["best_metric"], 8)
            self.assertEqual(state["state"]["best_iteration"], 2)
            self.assertEqual(state["state"]["keeps"], 1)
            self.assertEqual(state["state"]["discards"], 1)
            self.assertEqual(state["state"]["last_commit"], "b2c3d4e")
            self.assertEqual(state["state"]["last_trial_metric"], 8)

            resume = self.run_script(
                "autoresearch_resume_check.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
            )
            self.assertEqual(resume["decision"], "full_resume")
            self.assertEqual(resume["tsv_summary"]["iteration"], 2)
            self.assertFalse((tmpdir / "autoresearch-results/launch.json").exists())
            self.assertFalse((tmpdir / "autoresearch-results/runtime.json").exists())
            self.assertFalse((tmpdir / "autoresearch-results/runtime.log").exists())

    def test_init_run_preserves_utf8_paths_in_results_state_and_context_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            workspace = tmpdir / "工作区"
            repo = workspace / "仓库"
            artifact_root = workspace / "autoresearch-results"
            results_path = artifact_root / "results.tsv"
            state_path = artifact_root / "state.json"
            context_path = artifact_root / "context.json"

            self.run_script(
                "autoresearch_init_run.py",
                "--repo",
                str(repo),
                "--workspace-root",
                str(workspace),
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
            )

            results_text = results_path.read_text(encoding="utf-8")
            state_text = state_path.read_text(encoding="utf-8")
            context_text = context_path.read_text(encoding="utf-8")

            self.assertIn("工作区", results_text)
            self.assertIn("仓库", results_text)
            self.assertIn("工作区", state_text)
            self.assertIn("仓库", state_text)
            self.assertIn("工作区", context_text)
            self.assertIn("仓库", context_text)
            self.assertNotIn("\\u5de5", results_text)
            self.assertNotIn("\\u4ed3", results_text)
            self.assertNotIn("\\u5de5", state_text)
            self.assertNotIn("\\u4ed3", state_text)
            self.assertNotIn("\\u5de5", context_text)
            self.assertNotIn("\\u4ed3", context_text)

    def test_required_stop_labels_and_iteration_labels_are_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            results_path = tmpdir / "autoresearch-results/results.tsv"
            state_path = tmpdir / "autoresearch-results/state.json"
            results_path.parent.mkdir(parents=True, exist_ok=True)
            results_path.parent.mkdir(parents=True, exist_ok=True)

            self.run_script(
                "autoresearch_init_run.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
                "--mode",
                "loop",
                "--goal",
                "Improve throughput with PTO-ISA",
                "--scope",
                "src/**/*.py",
                "--metric-name",
                "mfu",
                "--direction",
                "higher",
                "--verify",
                "python3 -c pass",
                "--stop-condition",
                "stop when metric reaches 55",
                "--required-stop-label",
                "pto-isa",
                "--required-stop-label",
                "shmem",
                "--baseline-metric",
                "52",
                "--baseline-commit",
                "a1b2c3d",
                "--baseline-description",
                "baseline mfu",
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
                "54",
                "--commit",
                "b2c3d4e",
                "--guard",
                "pass",
                "--label",
                "pto-isa",
                "--label",
                "shmem",
                "--description",
                "fused training path improved overlap",
            )

            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["config"]["required_stop_labels"], ["pto-isa", "shmem"])
            self.assertEqual(state["state"]["current_labels"], ["pto-isa", "shmem"])
            self.assertEqual(state["state"]["last_trial_labels"], ["pto-isa", "shmem"])
            log_text = results_path.read_text(encoding="utf-8")
            self.assertIn(
                "[labels: pto-isa, shmem] fused training path improved overlap",
                log_text,
            )

    def test_required_keep_labels_downgrade_improved_keep_to_discard_without_polluting_retained_state(self) -> None:
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
                "Root-Cause",
                "--required-keep-label",
                "production-path",
                "--required-keep-label",
                "root-cause",
                "--baseline-metric",
                "150",
                "--baseline-commit",
                "base111",
                "--baseline-description",
                "baseline latency",
            )

            result = self.run_script(
                "autoresearch_record_iteration.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
                "--status",
                "keep",
                "--metric",
                "120",
                "--commit",
                "keep222",
                "--guard",
                "pass",
                "--label",
                "Production-Path",
                "--label",
                "production-path",
                "--description",
                "optimized the live request path",
            )
            self.assertEqual(result["status"], "discard")

            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(
                state["config"]["required_keep_labels"],
                ["root-cause", "production-path"],
            )
            self.assertEqual(state["state"]["current_metric"], 150)
            self.assertEqual(state["state"]["best_metric"], 150)
            self.assertEqual(state["state"]["current_labels"], [])
            self.assertEqual(state["state"]["last_trial_commit"], "keep222")
            self.assertEqual(state["state"]["last_trial_metric"], 120)
            self.assertEqual(state["state"]["last_trial_labels"], ["production-path"])

            log_text = results_path.read_text(encoding="utf-8")
            self.assertIn(
                "1\tkeep222\t120\t-30\tpass\tdiscard\t"
                "[labels: production-path] optimized the live request path "
                "[KEEP-GATE miss] missing required keep labels: root-cause",
                log_text,
            )

    def test_tsv_reconstruction_preserves_structured_labels(self) -> None:
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
                "Improve latency through the production path",
                "--scope",
                "src/**/*.py",
                "--metric-name",
                "latency ms",
                "--direction",
                "lower",
                "--verify",
                "python3 -c pass",
                "--stop-condition",
                "stop when metric reaches 120",
                "--required-stop-label",
                "production-path",
                "--required-stop-label",
                "real-backend",
                "--baseline-metric",
                "150",
                "--baseline-commit",
                "a1b2c3d",
                "--baseline-description",
                "baseline latency",
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
                "119",
                "--commit",
                "b2c3d4e",
                "--guard",
                "pass",
                "--label",
                "production-path",
                "--label",
                "real-backend",
                "--description",
                "optimized the retained production path",
            )

            state_path.unlink()

            resume = self.run_script(
                "autoresearch_resume_check.py",
                "--results-path",
                str(results_path),
            )
            self.assertEqual(resume["decision"], "tsv_fallback")
            self.assertEqual(
                resume["tsv_summary"]["current_labels"],
                ["production-path", "real-backend"],
            )
            self.assertEqual(
                resume["tsv_summary"]["last_trial_labels"],
                ["production-path", "real-backend"],
            )

    def test_resume_check_accepts_repo_as_primary_entrypoint(self) -> None:
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
                "python3 -c pass",
                "--baseline-metric",
                "10",
                "--baseline-commit",
                "a1b2c3d",
                "--baseline-description",
                "baseline failures",
            )

            resume = self.run_script(
                "autoresearch_resume_check.py",
                "--repo",
                str(tmpdir),
            )
            self.assertEqual(resume["decision"], "full_resume")
            self.assertEqual(Path(resume["results_path"]).resolve(), results_path.resolve())
            self.assertEqual(Path(resume["state_path"]).resolve(), state_path.resolve())

    def test_multi_repo_provenance_is_persisted_in_state_for_init_and_iterations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            primary = root / "primary"
            companion = root / "companion"
            primary.mkdir()
            companion.mkdir()
            results_path = primary / "autoresearch-results/results.tsv"
            state_path = primary / "autoresearch-results/state.json"

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
            )

            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["config"]["session_mode"], "foreground")
            self.assertEqual(
                state["state"]["last_repo_commits"],
                {
                    str(primary.resolve()): "base111",
                    str(companion.resolve()): "comp111",
                },
            )
            self.assertEqual(state["state"]["last_trial_repo_commits"], state["state"]["last_repo_commits"])

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
                "trial222",
                "--repo-commit",
                f"{companion}=comp222",
                "--description",
                "worse coordinated attempt",
            )

            discarded = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(
                discarded["state"]["last_repo_commits"],
                {
                    str(primary.resolve()): "base111",
                    str(companion.resolve()): "comp111",
                },
            )
            self.assertEqual(
                discarded["state"]["last_trial_repo_commits"],
                {
                    str(primary.resolve()): "trial222",
                    str(companion.resolve()): "comp222",
                },
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
                "keep333",
                "--repo-commit",
                f"{companion}=comp333",
                "--guard",
                "pass",
                "--description",
                "better coordinated attempt",
            )

            kept = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(
                kept["state"]["last_repo_commits"],
                {
                    str(primary.resolve()): "keep333",
                    str(companion.resolve()): "comp333",
                },
            )
            self.assertEqual(kept["state"]["last_trial_repo_commits"], kept["state"]["last_repo_commits"])

    def test_discard_requires_commit(self) -> None:
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
                "python3 -c pass",
                "--baseline-metric",
                "10",
                "--baseline-commit",
                "a1b2c3d",
                "--baseline-description",
                "baseline failures",
            )

            completed = self.run_script_completed(
                "autoresearch_record_iteration.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
                "--status",
                "discard",
                "--metric",
                "12",
                "--description",
                "worse attempt without commit",
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("Status discard must provide --commit", completed.stderr)

    def test_crash_requires_commit(self) -> None:
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
                "python3 -c pass",
                "--baseline-metric",
                "10",
                "--baseline-commit",
                "a1b2c3d",
                "--baseline-description",
                "baseline failures",
            )

            completed = self.run_script_completed(
                "autoresearch_record_iteration.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
                "--status",
                "crash",
                "--description",
                "verification crashed before metric extraction",
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("Status crash must provide --commit", completed.stderr)

    def test_strategy_only_refine_can_omit_commit_but_measured_refine_cannot(self) -> None:
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
                "python3 -c pass",
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
                "refine",
                "--description",
                "switch strategy family without testing a committed diff",
            )

            completed = self.run_script_completed(
                "autoresearch_record_iteration.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
                "--status",
                "refine",
                "--metric",
                "9",
                "--guard",
                "pass",
                "--description",
                "measured refine without commit",
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("Status refine must provide --commit", completed.stderr)

    def test_refine_counts_toward_consecutive_discards_for_state_and_resume(self) -> None:
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
                "python3 -c pass",
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
                "discard",
                "--metric",
                "11",
                "--commit",
                "deadbee",
                "--description",
                "first miss",
            )
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
                "beadfed",
                "--description",
                "second miss",
            )
            self.run_script(
                "autoresearch_record_iteration.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
                "--status",
                "refine",
                "--description",
                "shift strategy without a measured trial",
            )

            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["state"]["consecutive_discards"], 3)
            self.assertEqual(state["state"]["last_status"], "refine")

            resume = self.run_script(
                "autoresearch_resume_check.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
            )
            self.assertEqual(resume["decision"], "full_resume")
            if str(SCRIPTS_DIR) not in sys.path:
                sys.path.insert(0, str(SCRIPTS_DIR))
            from autoresearch_artifacts import log_summary, parse_results_log

            reconstructed = log_summary(parse_results_log(results_path), "lower")
            self.assertEqual(reconstructed["consecutive_discards"], 3)

    def test_parallel_batch_selects_best_worker_and_appends_main_row(self) -> None:
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
                            "metric": 7,
                            "guard": "pass",
                            "description": "narrowed hot path",
                            "diff_size": 12,
                        },
                        {
                            "worker_id": "b",
                            "commit": "d4e5f6a",
                            "metric": 9,
                            "guard": "pass",
                            "description": "wrapper experiment",
                            "diff_size": 4,
                        },
                        {
                            "worker_id": "c",
                            "status": "crash",
                            "description": "timeout after 20m",
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
            self.assertEqual(result["selected_worker"], "a")
            self.assertEqual(result["status"], "keep")

            log_text = results_path.read_text(encoding="utf-8")
            self.assertIn("1a\tc3d4e5f\t7\t-3\tpass\tkeep", log_text)
            self.assertIn("1b\t-\t9\t-1\tpass\tdiscard", log_text)
            self.assertIn("1c\t-\t10\t0\t-\tcrash", log_text)
            self.assertIn("1\tc3d4e5f\t7\t-3\tpass\tkeep\t[PARALLEL batch] selected worker-a", log_text)

            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["state"]["iteration"], 1)
            self.assertEqual(state["state"]["current_metric"], 7)

    def test_parallel_batch_keep_gate_preserves_best_discarded_trial_provenance(self) -> None:
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
                "Improve latency through the production path",
                "--scope",
                "src/**/*.py",
                "--metric-name",
                "latency ms",
                "--direction",
                "lower",
                "--verify",
                "python3 -c pass",
                "--parallel-mode",
                "parallel",
                "--required-keep-label",
                "production-path",
                "--required-keep-label",
                "real-backend",
                "--baseline-metric",
                "10",
                "--baseline-commit",
                "base111",
                "--baseline-description",
                "baseline latency",
            )
            batch_path.write_text(
                json.dumps(
                    [
                        {
                            "worker_id": "a",
                            "commit": "cand111",
                            "metric": 7,
                            "guard": "pass",
                            "description": "narrowed the live request path",
                            "labels": ["production-path"],
                            "diff_size": 12,
                        },
                        {
                            "worker_id": "b",
                            "commit": "cand222",
                            "metric": 11,
                            "guard": "pass",
                            "description": "wrapper experiment",
                            "diff_size": 4,
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

            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["state"]["current_metric"], 10)
            self.assertEqual(state["state"]["best_metric"], 10)
            self.assertEqual(state["state"]["current_labels"], [])
            self.assertEqual(state["state"]["last_trial_commit"], "cand111")
            self.assertEqual(state["state"]["last_trial_metric"], 7)
            self.assertEqual(state["state"]["last_trial_labels"], ["production-path"])

            log_text = results_path.read_text(encoding="utf-8")
            self.assertIn(
                "1a\t-\t7\t-3\tpass\tdiscard\t"
                "[labels: production-path] [PARALLEL worker-a] narrowed the live request path "
                "[KEEP-GATE miss] missing required keep labels: real-backend",
                log_text,
            )
            self.assertIn(
                "1\tcand111\t7\t-3\tpass\tdiscard\t"
                "[labels: production-path] [PARALLEL batch] no worker produced a keepable improvement; "
                "best discarded worker-a: narrowed the live request path "
                "[KEEP-GATE miss] missing required keep labels: real-backend",
                log_text,
            )

    def test_resume_check_can_rebuild_missing_state_from_tsv(self) -> None:
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
                "python3 -c pass",
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
                "b2c3d4e",
                "--guard",
                "pass",
                "--description",
                "better attempt",
            )
            state_path.unlink()

            resume = self.run_script(
                "autoresearch_resume_check.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
                "--write-repaired-state",
            )
            self.assertEqual(resume["decision"], "tsv_fallback")
            self.assertTrue(resume["repaired_state"])

            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["config"], {"direction": "lower"})
            self.assertEqual(state["state"]["iteration"], 1)
            self.assertEqual(state["state"]["current_metric"], 8)

            second_resume = self.run_script(
                "autoresearch_resume_check.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
            )
            self.assertEqual(second_resume["decision"], "mini_wizard")
            self.assertTrue(
                any("config is missing required resume fields" in reason for reason in second_resume["reasons"])
            )

    def test_resume_check_detects_json_tsv_divergence(self) -> None:
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
                "python3 -c pass",
                "--baseline-metric",
                "10",
                "--baseline-commit",
                "a1b2c3d",
                "--baseline-description",
                "baseline failures",
            )
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["state"]["current_metric"] = 999
            state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

            resume = self.run_script(
                "autoresearch_resume_check.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
            )
            self.assertEqual(resume["decision"], "mini_wizard")
            self.assertTrue(any("current_metric" in reason for reason in resume["reasons"]))

    def test_resume_check_requires_context_instead_of_stale_exec_scratch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            scratch_state_path = Path(
                self.run_script_text(
                    "autoresearch_exec_state.py",
                    "--repo-root",
                    str(repo),
                )
            )
            scratch_state_path.parent.mkdir(parents=True, exist_ok=True)
            scratch_state_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "mode": "exec",
                        "config": {"direction": "lower"},
                        "state": {
                            "iteration": 3,
                            "baseline_metric": 10,
                            "best_metric": 7,
                            "best_iteration": 2,
                            "current_metric": 7,
                            "last_commit": "keep123",
                            "last_trial_commit": "keep123",
                            "last_trial_metric": 7,
                            "keeps": 1,
                            "discards": 2,
                            "crashes": 0,
                            "no_ops": 0,
                            "blocked": 0,
                            "consecutive_discards": 0,
                            "pivot_count": 0,
                            "last_status": "keep",
                        },
                    }
                ),
                encoding="utf-8",
            )

            completed = self.run_script_completed("autoresearch_resume_check.py", cwd=repo)
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("No codex-autoresearch context found", completed.stderr)

    def test_resume_check_treats_incomplete_json_state_as_unusable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            results_path = tmpdir / "autoresearch-results/results.tsv"
            state_path = tmpdir / "autoresearch-results/state.json"
            results_path.parent.mkdir(parents=True, exist_ok=True)

            results_path.write_text(
                "\n".join(
                    [
                        "# metric_direction: lower",
                        "iteration\tcommit\tmetric\tdelta\tguard\tstatus\tdescription",
                        "0\tbase123\t10\t0\t-\tbaseline\tbaseline score",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            state_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "mode": "loop",
                        "config": {"direction": "lower"},
                        "state": {},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            resume = self.run_script(
                "autoresearch_resume_check.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
            )
            self.assertEqual(resume["decision"], "tsv_fallback")
            self.assertTrue(any("missing state fields" in reason for reason in resume["reasons"]))

    def test_resume_check_rejects_missing_main_iteration_row(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            results_path = tmpdir / "autoresearch-results/results.tsv"
            state_path = tmpdir / "autoresearch-results/state.json"
            results_path.parent.mkdir(parents=True, exist_ok=True)

            results_path.write_text(
                "\n".join(
                    [
                        "# metric_direction: lower",
                        "iteration\tcommit\tmetric\tdelta\tguard\tstatus\tdescription",
                        "0\tbase123\t10\t0\t-\tbaseline\tbaseline score",
                        "2\tkeep123\t8\t-2\tpass\tkeep\tjumped iteration",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            state_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "mode": "loop",
                        "config": {"direction": "lower"},
                        "state": {
                            "iteration": 2,
                            "baseline_metric": 10,
                            "best_metric": 8,
                            "best_iteration": 2,
                            "current_metric": 8,
                            "last_commit": "keep123",
                            "last_trial_commit": "keep123",
                            "last_trial_metric": 8,
                            "keeps": 1,
                            "discards": 0,
                            "crashes": 0,
                            "no_ops": 0,
                            "blocked": 0,
                            "consecutive_discards": 0,
                            "pivot_count": 0,
                            "last_status": "keep",
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            resume = self.run_script(
                "autoresearch_resume_check.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
            )
            self.assertEqual(resume["decision"], "mini_wizard")
            self.assertTrue(any("expected 1, got 2" in reason for reason in resume["reasons"]))

    def test_resume_check_keeps_json_path_when_tsv_is_missing(self) -> None:
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
                "python3 -c pass",
                "--baseline-metric",
                "10",
                "--baseline-commit",
                "a1b2c3d",
                "--baseline-description",
                "baseline failures",
            )
            results_path.unlink()

            resume = self.run_script(
                "autoresearch_resume_check.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
            )
            self.assertEqual(resume["decision"], "mini_wizard")
            self.assertTrue(any("results log is missing" in reason for reason in resume["reasons"]))

    def test_init_run_defaults_state_path_for_absolute_results_path_outside_repo_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
            results_path = repo / "autoresearch-results/results.tsv"
            state_path = repo / "autoresearch-results/state.json"

            result = self.run_script(
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
            self.assertEqual(Path(result["state_path"]).resolve(), state_path.resolve())
            self.assertTrue(state_path.exists())

    def test_resume_check_uses_repo_state_for_absolute_results_path_outside_repo_cwd(self) -> None:
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

            resume = self.run_script(
                "autoresearch_resume_check.py",
                "--results-path",
                str(results_path),
                cwd=REPO_ROOT.parent,
            )
            self.assertEqual(resume["decision"], "full_resume")
            self.assertEqual(Path(str(resume["state_path"])).resolve(), state_path.resolve())

    def test_resume_check_repo_entrypoint_requires_git_local_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.init_git_repo(Path(tmp))

            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS_DIR / "autoresearch_resume_check.py"),
                    "--repo",
                    str(repo),
                ],
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("No codex-autoresearch context found", completed.stderr)
            self.assertFalse((repo / "autoresearch-results").exists())

    def test_resume_check_reports_legacy_repo_root_artifacts_before_missing_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.init_git_repo(Path(tmp))
            (repo / "research-results.tsv").write_text("legacy\n", encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS_DIR / "autoresearch_resume_check.py"),
                    "--repo",
                    str(repo),
                ],
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("Found legacy repo-root autoresearch artifacts", completed.stderr)
            self.assertNotIn("No codex-autoresearch context found", completed.stderr)
            self.assertFalse((repo / "autoresearch-results").exists())

    def test_init_run_requires_explicit_workspace_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            repo = self.init_git_repo(workspace / "repo")

            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS_DIR / "autoresearch_init_run.py"),
                    "--repo",
                    str(repo),
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
                ],
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("the following arguments are required: --workspace-root", completed.stderr)
            self.assertFalse((repo / "autoresearch-results").exists())
            self.assertFalse((workspace / "autoresearch-results").exists())

    def test_init_run_validates_managed_repos_before_writing_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            primary = self.init_git_repo(workspace / "primary")
            companion = workspace / "companion"
            companion.mkdir(parents=True)
            artifact_root = workspace / "autoresearch-results"

            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS_DIR / "autoresearch_init_run.py"),
                    "--repo",
                    str(primary),
                    "--workspace-root",
                    str(workspace),
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
                    "--baseline-metric",
                    "10",
                    "--baseline-commit",
                    "a1b2c3d",
                    "--baseline-description",
                    "baseline failures",
                ],
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("Managed repos must be git repositories", completed.stderr)
            self.assertFalse((artifact_root / "results.tsv").exists())
            self.assertFalse((artifact_root / "state.json").exists())
            self.assertFalse((artifact_root / "context.json").exists())
