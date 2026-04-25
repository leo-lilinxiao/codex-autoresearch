from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from .base import AutoresearchScriptsTestBase, REPO_ROOT, SCRIPTS_DIR


class AutoresearchSupervisorLaunchTest(AutoresearchScriptsTestBase):
    maxDiff = None

    def test_supervisor_status_relaunches_after_non_terminal_turn(self) -> None:
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
                "pivot",
                "--description",
                "close this branch and continue with a new strategy",
            )

            status = self.run_script(
                "autoresearch_supervisor_status.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
                "--after-run",
                "--write-state",
            )
            self.assertEqual(status["decision"], "relaunch")
            self.assertEqual(status["reason"], "none")

            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["supervisor"]["recommended_action"], "relaunch")
            self.assertTrue(state["supervisor"]["should_continue"])
            self.assertEqual(state["supervisor"]["last_exit_kind"], "turn_complete")

    def test_supervisor_status_needs_human_after_blocked(self) -> None:
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
                "blocked",
                "--description",
                "external dependency vanished",
            )

            status = self.run_script(
                "autoresearch_supervisor_status.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
                "--after-run",
                "--write-state",
            )
            self.assertEqual(status["decision"], "needs_human")
            self.assertEqual(status["reason"], "blocked")

    def test_supervisor_status_accepts_repo_as_primary_entrypoint(self) -> None:
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
                "blocked",
                "--description",
                "external dependency vanished",
            )

            status = self.run_script(
                "autoresearch_supervisor_status.py",
                "--repo",
                str(tmpdir),
                "--after-run",
            )
            self.assertEqual(status["decision"], "needs_human")
            self.assertEqual(status["reason"], "blocked")
            self.assertEqual(Path(status["results_path"]).resolve(), results_path.resolve())
            self.assertEqual(Path(status["state_path"]).resolve(), state_path.resolve())

    def test_supervisor_status_stops_at_iteration_cap(self) -> None:
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
                "--iterations",
                "1",
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
                "bounded miss",
            )

            status = self.run_script(
                "autoresearch_supervisor_status.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
                "--after-run",
                "--write-state",
            )
            self.assertEqual(status["decision"], "stop")
            self.assertEqual(status["reason"], "iteration_cap_reached")

    def test_supervisor_status_needs_human_after_three_pivots_without_keep(self) -> None:
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
            for description in (
                "pivot from auth wrappers to API handlers",
                "pivot from API handlers to shared utilities",
                "pivot from shared utilities to architectural cleanup",
            ):
                self.run_script(
                    "autoresearch_record_iteration.py",
                    "--results-path",
                    str(results_path),
                    "--state-path",
                    str(state_path),
                    "--status",
                    "pivot",
                    "--description",
                    description,
                )

            status = self.run_script(
                "autoresearch_supervisor_status.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
                "--after-run",
                "--write-state",
            )
            self.assertEqual(status["decision"], "needs_human")
            self.assertEqual(status["reason"], "soft_blocked")

            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["supervisor"]["recommended_action"], "needs_human")
            self.assertEqual(state["supervisor"]["last_exit_kind"], "soft_blocked")

    def test_supervisor_status_stops_when_stop_condition_reaches_zero(self) -> None:
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
                "Fix all errors",
                "--scope",
                "src/**/*.py",
                "--metric-name",
                "error count",
                "--direction",
                "lower",
                "--verify",
                "pytest -q",
                "--stop-condition",
                "stop when metric reaches 0",
                "--baseline-metric",
                "1",
                "--baseline-commit",
                "a1b2c3d",
                "--baseline-description",
                "baseline error count",
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
                "0",
                "--commit",
                "keep000",
                "--guard",
                "pass",
                "--description",
                "fixed last error",
            )

            status = self.run_script(
                "autoresearch_supervisor_status.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
                "--after-run",
                "--write-state",
            )
            self.assertEqual(status["decision"], "stop")
            self.assertEqual(status["reason"], "goal_reached")

            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["supervisor"]["recommended_action"], "stop")
            self.assertEqual(state["supervisor"]["terminal_reason"], "goal_reached")

    def test_supervisor_status_stops_when_symbolic_stop_condition_equals_zero(self) -> None:
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
                "fix",
                "--goal",
                "Fix all errors",
                "--scope",
                "src/**/*.py",
                "--metric-name",
                "error count",
                "--direction",
                "lower",
                "--verify",
                "pytest -q",
                "--stop-condition",
                "metric == 0",
                "--baseline-metric",
                "1",
                "--baseline-commit",
                "a1b2c3d",
                "--baseline-description",
                "baseline error count",
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
                "0",
                "--commit",
                "keep000",
                "--guard",
                "pass",
                "--description",
                "fixed last error",
            )

            status = self.run_script(
                "autoresearch_supervisor_status.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
                "--after-run",
                "--write-state",
            )
            self.assertEqual(status["decision"], "stop")
            self.assertEqual(status["reason"], "goal_reached")

            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["supervisor"]["recommended_action"], "stop")
            self.assertEqual(state["supervisor"]["terminal_reason"], "goal_reached")

    def test_supervisor_status_stops_when_fix_mode_reaches_zero(self) -> None:
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
                "fix",
                "--goal",
                "Repair failing tests",
                "--scope",
                "tests/**/*.py",
                "--metric-name",
                "error count",
                "--direction",
                "lower",
                "--verify",
                "pytest -q",
                "--baseline-metric",
                "1",
                "--baseline-commit",
                "a1b2c3d",
                "--baseline-description",
                "baseline error count",
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
                "0",
                "--commit",
                "keepfix",
                "--guard",
                "pass",
                "--description",
                "fixed remaining failure",
            )

            status = self.run_script(
                "autoresearch_supervisor_status.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
                "--after-run",
                "--write-state",
            )
            self.assertEqual(status["decision"], "stop")
            self.assertEqual(status["reason"], "goal_reached")

    def test_supervisor_status_does_not_auto_stop_fix_mode_higher_without_stop_condition(self) -> None:
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
                "fix",
                "--goal",
                "Increase passing checks",
                "--scope",
                "tests/**/*.py",
                "--metric-name",
                "passing checks",
                "--direction",
                "higher",
                "--verify",
                "pytest -q",
                "--baseline-metric",
                "99",
                "--baseline-commit",
                "a1b2c3d",
                "--baseline-description",
                "baseline passing checks",
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
                "100",
                "--commit",
                "keephigh",
                "--guard",
                "pass",
                "--description",
                "improved passing checks",
            )

            status = self.run_script(
                "autoresearch_supervisor_status.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
                "--after-run",
                "--write-state",
            )
            self.assertEqual(status["decision"], "relaunch")
            self.assertEqual(status["reason"], "none")
            self.assertTrue(
                any("loop remains resumable" in reason for reason in status["reasons"])
            )

    def test_supervisor_status_does_not_auto_stop_debug_mode_at_zero(self) -> None:
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
                "debug",
                "--goal",
                "Investigate failing tests",
                "--scope",
                "tests/**/*.py",
                "--metric-name",
                "error count",
                "--direction",
                "lower",
                "--verify",
                "pytest -q",
                "--baseline-metric",
                "1",
                "--baseline-commit",
                "a1b2c3d",
                "--baseline-description",
                "baseline error count",
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
                "0",
                "--commit",
                "keepdbg",
                "--guard",
                "pass",
                "--description",
                "removed the failing symptom",
            )

            status = self.run_script(
                "autoresearch_supervisor_status.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
                "--after-run",
                "--write-state",
            )
            self.assertEqual(status["decision"], "relaunch")
            self.assertEqual(status["reason"], "none")
            self.assertTrue(
                any("loop remains resumable" in reason for reason in status["reasons"])
            )

            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["supervisor"]["recommended_action"], "relaunch")
            self.assertEqual(state["supervisor"]["terminal_reason"], "none")

    def test_supervisor_status_stops_when_stop_condition_reaches_nonzero_threshold(self) -> None:
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
                "3",
                "--baseline-commit",
                "a1b2c3d",
                "--baseline-description",
                "baseline failures",
                "--stop-condition",
                "stop when metric reaches 1",
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
                "1",
                "--commit",
                "keep001",
                "--guard",
                "pass",
                "--description",
                "reduced failures to threshold",
            )

            status = self.run_script(
                "autoresearch_supervisor_status.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
                "--after-run",
            )
            self.assertEqual(status["decision"], "stop")
            self.assertEqual(status["reason"], "goal_reached")

    def test_supervisor_status_stops_when_higher_direction_threshold_is_met(self) -> None:
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
                "Improve accuracy",
                "--scope",
                "src/**/*.py",
                "--metric-name",
                "accuracy",
                "--direction",
                "higher",
                "--verify",
                "python eval.py",
                "--baseline-metric",
                "87.5",
                "--baseline-commit",
                "a1b2c3d",
                "--baseline-description",
                "baseline accuracy",
                "--stop-condition",
                "stop when metric reaches 90",
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
                "90",
                "--commit",
                "keep090",
                "--guard",
                "pass",
                "--description",
                "raised accuracy to threshold",
            )

            status = self.run_script(
                "autoresearch_supervisor_status.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
                "--after-run",
            )
            self.assertEqual(status["decision"], "stop")
            self.assertEqual(status["reason"], "goal_reached")

    def test_supervisor_status_does_not_stop_without_required_stop_labels(self) -> None:
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
                "Improve MFU through PTO-ISA shmem",
                "--scope",
                "src/**/*.py",
                "--metric-name",
                "mfu",
                "--direction",
                "higher",
                "--verify",
                "python eval.py",
                "--baseline-metric",
                "52",
                "--baseline-commit",
                "a1b2c3d",
                "--baseline-description",
                "baseline mfu",
                "--stop-condition",
                "stop when metric reaches 55",
                "--required-stop-label",
                "pto-isa",
                "--required-stop-label",
                "shmem",
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
                "55",
                "--commit",
                "keep055",
                "--guard",
                "pass",
                "--label",
                "pto-isa",
                "--description",
                "improved MFU but not through the full PTO-ISA shmem path",
            )

            status = self.run_script(
                "autoresearch_supervisor_status.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
                "--after-run",
            )
            self.assertEqual(status["decision"], "relaunch")
            self.assertEqual(status["reason"], "none")
            self.assertTrue(
                any("required stop labels" in reason for reason in status["reasons"])
            )

    def test_supervisor_status_stops_when_required_stop_labels_are_present(self) -> None:
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
                "Improve MFU through PTO-ISA shmem",
                "--scope",
                "src/**/*.py",
                "--metric-name",
                "mfu",
                "--direction",
                "higher",
                "--verify",
                "python eval.py",
                "--baseline-metric",
                "52",
                "--baseline-commit",
                "a1b2c3d",
                "--baseline-description",
                "baseline mfu",
                "--stop-condition",
                "stop when metric reaches 55",
                "--required-stop-label",
                "pto-isa",
                "--required-stop-label",
                "shmem",
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
                "55",
                "--commit",
                "keep055",
                "--guard",
                "pass",
                "--label",
                "pto-isa",
                "--label",
                "shmem",
                "--description",
                "improved MFU through the PTO-ISA shmem path",
            )

            status = self.run_script(
                "autoresearch_supervisor_status.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
                "--after-run",
            )
            self.assertEqual(status["decision"], "stop")
            self.assertEqual(status["reason"], "goal_reached")
            self.assertTrue(any("required stop labels" in reason for reason in status["reasons"]))

    def test_supervisor_status_detects_stagnation(self) -> None:
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

            first = self.run_script(
                "autoresearch_supervisor_status.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
                "--after-run",
                "--write-state",
                "--max-stagnation",
                "2",
            )
            second = self.run_script(
                "autoresearch_supervisor_status.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
                "--after-run",
                "--write-state",
                "--max-stagnation",
                "2",
            )
            third = self.run_script(
                "autoresearch_supervisor_status.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
                "--after-run",
                "--write-state",
                "--max-stagnation",
                "2",
            )

            self.assertEqual(first["decision"], "relaunch")
            self.assertEqual(second["decision"], "relaunch")
            self.assertEqual(third["decision"], "needs_human")
            self.assertEqual(third["reason"], "stagnated")

            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["supervisor"]["last_exit_kind"], "stagnated")

    def test_supervisor_status_allows_missing_artifacts_after_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            results_path = tmpdir / "autoresearch-results/results.tsv"

            status = self.run_script(
                "autoresearch_supervisor_status.py",
                "--results-path",
                str(results_path),
                "--after-run",
            )
            self.assertEqual(status["decision"], "relaunch")
            self.assertEqual(status["reason"], "missing_artifacts")

    def test_launch_gate_and_runtime_prompt_use_confirmed_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            launch = self.create_launch_manifest(
                tmpdir,
                original_goal="Make the test suite healthier overnight",
                guard="python -m py_compile src",
                stop_condition="stop when metric reaches 0",
            )
            launch_path = Path(launch["launch_path"])

            gate = self.run_script(
                "autoresearch_launch_gate.py",
                "--repo",
                str(tmpdir),
                "--results-path",
                str(tmpdir / "autoresearch-results/results.tsv"),
                "--launch-path",
                str(launch_path),
                "--runtime-path",
                str(tmpdir / "autoresearch-results/runtime.json"),
            )
            self.assertEqual(gate["decision"], "fresh")
            self.assertEqual(gate["reason"], "confirmed_launch_without_artifacts")

            prompt = self.run_script_text(
                "autoresearch_resume_prompt.py",
                "--repo",
                str(tmpdir),
                "--results-path",
                str(tmpdir / "autoresearch-results/results.tsv"),
                "--launch-path",
                str(launch_path),
                "--runtime-path",
                str(tmpdir / "autoresearch-results/runtime.json"),
            )
            self.assertIn("$codex-autoresearch", prompt)
            self.assertIn("The human already completed the confirmation phase", prompt)
            self.assertIn(f"Use {launch_path}", prompt)
            self.assertIn("Session mode: background", prompt)
            self.assertIn("Do not run the interactive wizard again.", prompt)
            self.assertIn("Stop condition: stop when metric reaches 0", prompt)
            self.assertIn("Runtime checklist:", prompt)
            self.assertIn("Record every completed experiment before starting the next one.", prompt)
            self.assertIn("Use helper scripts for authoritative TSV/state updates.", prompt)

            status = self.run_script(
                "autoresearch_runtime_ctl.py",
                "status",
                "--repo",
                str(tmpdir),
            )
            self.assertEqual(status["status"], "idle")
            self.assertEqual(status["reason"], "confirmed_launch_without_artifacts")

    def test_launch_gate_uses_repo_context_for_manifest_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            repo = tmpdir / "repo"
            outside = tmpdir / "outside"
            repo.mkdir()
            outside.mkdir()

            results_path = self.managed_results_path(repo)
            state_path = self.managed_state_path(repo)
            launch = self.create_launch_manifest(repo)

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

            gate = self.run_script(
                "autoresearch_launch_gate.py",
                "--repo",
                str(repo),
                "--results-path",
                str(results_path),
                cwd=outside,
            )
            self.assertEqual(gate["decision"], "resumable")
            self.assertEqual(Path(gate["launch_path"]).resolve(), Path(launch["launch_path"]).resolve())
            self.assertEqual(
                Path(gate["runtime_path"]).resolve(),
                self.managed_runtime_path(repo).resolve(),
            )

    def test_launch_gate_accepts_repo_as_primary_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            self.create_launch_manifest(tmpdir)

            gate = self.run_script(
                "autoresearch_launch_gate.py",
                "--repo",
                str(tmpdir),
            )
            self.assertEqual(gate["decision"], "fresh")
            self.assertEqual(gate["reason"], "confirmed_launch_without_artifacts")
            self.assertEqual(Path(gate["results_path"]).resolve(), self.managed_results_path(tmpdir).resolve())
            self.assertEqual(Path(gate["launch_path"]).resolve(), self.managed_launch_path(tmpdir).resolve())
            self.assertEqual(Path(gate["runtime_path"]).resolve(), self.managed_runtime_path(tmpdir).resolve())

    def test_launch_gate_repo_subdirectory_resolves_to_actual_repo_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            subprocess.run(["git", "init", str(tmpdir)], check=True, capture_output=True, text=True)
            nested = tmpdir / "nested" / "deeper"
            nested.mkdir(parents=True)
            self.create_launch_manifest(tmpdir)

            gate = self.run_script(
                "autoresearch_launch_gate.py",
                "--repo",
                str(nested),
            )
            self.assertEqual(Path(gate["results_path"]).resolve(), self.managed_results_path(tmpdir).resolve())
            self.assertEqual(Path(gate["launch_path"]).resolve(), self.managed_launch_path(tmpdir).resolve())
            self.assertEqual(Path(gate["runtime_path"]).resolve(), self.managed_runtime_path(tmpdir).resolve())

    def test_resume_prompt_uses_repo_context_for_manifest_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            repo = tmpdir / "repo"
            outside = tmpdir / "outside"
            repo.mkdir()
            outside.mkdir()

            results_path = self.managed_results_path(repo)
            state_path = self.managed_state_path(repo)
            launch = self.create_launch_manifest(
                repo,
                original_goal="Make the test suite healthier overnight",
                guard="python -m py_compile src",
                stop_condition="stop when metric reaches 0",
            )

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

            prompt = self.run_script_text(
                "autoresearch_resume_prompt.py",
                "--repo",
                str(repo),
                "--results-path",
                str(results_path),
                cwd=outside,
            )
            self.assertTrue(
                any(
                    f"Use {candidate} as the authoritative launch manifest." in prompt
                    for candidate in {
                        str(Path(launch["launch_path"]).resolve()),
                        str(Path(launch["launch_path"]).resolve()).replace("/private/var/", "/private/private/var/"),
                    }
                )
            )
            self.assertIn("Results path:", prompt)
            self.assertIn("autoresearch-results/results.tsv", prompt)
            self.assertIn("State path:", prompt)
            self.assertIn("autoresearch-results/state.json", prompt)

    def test_resume_prompt_accepts_repo_as_primary_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            repo = tmpdir / "repo"
            repo.mkdir()

            launch = self.create_launch_manifest(
                repo,
                original_goal="Make the test suite healthier overnight",
                guard="python -m py_compile src",
                stop_condition="stop when metric reaches 0",
            )
            results_path = self.managed_results_path(repo)
            state_path = self.managed_state_path(repo)
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

            prompt = self.run_script_text(
                "autoresearch_resume_prompt.py",
                "--repo",
                str(repo),
            )
            normalized = prompt.replace("/private/private/var/", "/private/var/")
            self.assertIn(
                f"Use {Path(launch['launch_path']).resolve()} as the authoritative launch manifest.",
                normalized,
            )
            self.assertIn(f"Results path: {results_path.resolve()}", normalized)
            self.assertIn(f"State path: {state_path.resolve()}", normalized)
            self.assertIn("Runtime checklist:", normalized)
            self.assertIn("Record every completed experiment before starting the next one.", normalized)

    def test_create_launch_manifest_persists_managed_repo_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            primary = root / "primary"
            companion = root / "companion"
            primary.mkdir()
            companion.mkdir()

            launch = self.create_launch_manifest(
                primary,
                scope="src/**/*.py",
                companion_repo_scopes=[f"{companion}=pkg/"],
            )

            manifest = json.loads(Path(str(launch["launch_path"])).read_text(encoding="utf-8"))
            self.assertEqual(manifest["config"]["session_mode"], "background")
            self.assertEqual(manifest["config"]["scope"], "src/**/*.py")
            self.assertEqual(manifest["config"]["execution_policy"], "danger_full_access")
            self.assertEqual(
                manifest["config"]["repos"],
                [
                    {"path": str(primary.resolve()), "scope": "src/**/*.py", "role": "primary"},
                    {"path": str(companion.resolve()), "scope": "pkg/", "role": "companion"},
                ],
            )

    def test_resume_prompt_lists_managed_repo_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            primary = root / "primary"
            companion = root / "companion"
            outside = root / "outside"
            primary.mkdir()
            companion.mkdir()
            outside.mkdir()

            self.create_launch_manifest(
                primary,
                scope="src/**/*.py",
                companion_repo_scopes=[f"{companion}=pkg/"],
            )
            results_path = self.managed_results_path(primary)
            state_path = self.managed_state_path(primary)
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
                "--companion-repo-scope",
                f"{companion}=pkg/",
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

            prompt = self.run_script_text(
                "autoresearch_resume_prompt.py",
                "--repo",
                str(primary),
                "--results-path",
                str(results_path),
                cwd=outside,
            )
            self.assertIn("Managed repos:", prompt)
            self.assertIn("- . (primary) :: src/**/*.py", prompt)
            self.assertIn(f"- {companion.resolve()} (companion) :: pkg/", prompt)

    def test_resume_prompt_requires_confirmed_launch_manifest_for_legacy_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            results_path = tmpdir / "autoresearch-results/results.tsv"
            state_path = tmpdir / "autoresearch-results/state.json"
            launch_path = tmpdir / "autoresearch-results/launch.json"

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
                "autoresearch_resume_prompt.py",
                "--repo",
                str(tmpdir),
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
                "--launch-path",
                str(launch_path),
                "--runtime-path",
                str(tmpdir / "autoresearch-results/runtime.json"),
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("fresh_start_required", completed.stderr)
            self.assertFalse(launch_path.exists())

    def test_launch_gate_requires_human_when_state_and_tsv_diverge(self) -> None:
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

            payload = json.loads(state_path.read_text(encoding="utf-8"))
            payload["state"]["current_metric"] = "999"
            state_path.write_text(json.dumps(payload), encoding="utf-8")

            gate = self.run_script(
                "autoresearch_launch_gate.py",
                "--repo",
                str(tmpdir),
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
            )
            self.assertEqual(gate["decision"], "needs_human")
            self.assertEqual(gate["reason"], "state_tsv_diverged")
            self.assertEqual(gate["resume_strategy"], "none")
            self.assertTrue(
                any("current_metric: state=999 tsv=10" in reason for reason in gate["reasons"])
            )

    def test_launch_gate_uses_resume_helper_for_corrupt_results_log(self) -> None:
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
            with results_path.open("a", encoding="utf-8") as handle:
                handle.write("corrupt\n")

            gate = self.run_script(
                "autoresearch_launch_gate.py",
                "--repo",
                str(tmpdir),
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
            )
            self.assertEqual(gate["decision"], "needs_human")
            self.assertEqual(gate["reason"], "resume_confirmation_required")
            self.assertEqual(gate["resume_strategy"], "mini_resume")
            self.assertTrue(
                any("TSV is unavailable" in reason or "TSV unavailable" in reason for reason in gate["reasons"])
            )

    def test_launch_gate_requires_manifest_confirmation_for_tsv_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            results_path = tmpdir / "autoresearch-results/results.tsv"
            results_path.parent.mkdir(parents=True, exist_ok=True)
            results_path.write_text(
                "\n".join(
                    [
                        "# metric_direction: lower",
                        "# mode: loop",
                        "iteration\tcommit\tmetric\tdelta\tguard\tstatus\tdescription",
                        "0\ta1b2c3d\t10\t0\t-\tbaseline\tbaseline failures",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            gate = self.run_script(
                "autoresearch_launch_gate.py",
                "--repo",
                str(tmpdir),
                "--results-path",
                str(results_path),
                "--launch-path",
                str(tmpdir / "autoresearch-results/launch.json"),
                "--runtime-path",
                str(tmpdir / "autoresearch-results/runtime.json"),
            )
            self.assertEqual(gate["decision"], "needs_human")
            self.assertEqual(gate["reason"], "launch_manifest_required")
            self.assertEqual(gate["resume_strategy"], "mini_resume")
            self.assertTrue(any("confirmed launch manifest" in reason for reason in gate["reasons"]))

    def test_runtime_start_requires_canonical_context_before_manifest_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            completed = self.run_script_completed(
                "autoresearch_runtime_ctl.py",
                "start",
                "--repo",
                str(tmpdir),
                "--codex-bin",
                "/bin/echo",
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("No codex-autoresearch context found", completed.stderr)
            self.assertFalse((tmpdir / "autoresearch-results/runtime.json").exists())

    def test_runtime_start_rejects_legacy_full_resume_without_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            results_path = tmpdir / "autoresearch-results/results.tsv"
            state_path = tmpdir / "autoresearch-results/state.json"
            fake_codex_path = tmpdir / "fake-codex"
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
                "python3 -c pass",
                "--baseline-metric",
                "10",
                "--baseline-commit",
                "a1b2c3d",
                "--baseline-description",
                "baseline failures",
            )

            gate = self.run_script(
                "autoresearch_launch_gate.py",
                "--repo",
                str(tmpdir),
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
                "--launch-path",
                str(tmpdir / "autoresearch-results/launch.json"),
                "--runtime-path",
                str(tmpdir / "autoresearch-results/runtime.json"),
            )
            self.assertEqual(gate["decision"], "needs_human")
            self.assertEqual(gate["reason"], "fresh_start_required")

            completed = self.run_script_completed(
                "autoresearch_runtime_ctl.py",
                "start",
                "--repo",
                str(tmpdir),
                "--codex-bin",
                str(fake_codex_path),
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("fresh_start_required", completed.stderr)
            self.assertFalse((tmpdir / "autoresearch-results/launch.json").exists())

    def test_runtime_start_blocks_on_unexpected_out_of_scope_worktree_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
            self.create_launch_manifest(repo, verify="python3 -c pass")
            (repo / "notes.txt").write_text("user drift\n", encoding="utf-8")

            completed = self.run_script_completed(
                "autoresearch_runtime_ctl.py",
                "start",
                "--repo",
                str(repo),
                "--codex-bin",
                "/bin/echo",
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("Runtime preflight failed", completed.stderr)
            self.assertIn("unexpected worktree changes before commit", completed.stderr)
            self.assertFalse((repo / "autoresearch-results/runtime.json").exists())

    def test_runtime_start_allows_in_scope_worktree_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
            (repo / "src").mkdir(parents=True, exist_ok=True)
            (repo / "src" / "core.py").write_text("print('ok')\n", encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(repo), "config", "user.email", "test@example.com"],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "-C", str(repo), "config", "user.name", "Test User"],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "-C", str(repo), "add", "src/core.py"],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "-C", str(repo), "commit", "-m", "seed scope file"],
                check=True,
                capture_output=True,
                text=True,
            )
            self.create_launch_manifest(repo, verify="python3 -c pass")
            (repo / "src" / "core.py").write_text("print('changed')\n", encoding="utf-8")

            started = self.run_script(
                "autoresearch_runtime_ctl.py",
                "start",
                "--repo",
                str(repo),
                "--codex-bin",
                "/bin/echo",
            )
            self.assertEqual(started["status"], "running")
