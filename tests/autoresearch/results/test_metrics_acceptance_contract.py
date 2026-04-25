from __future__ import annotations

import json
import tempfile
from pathlib import Path

from ..base import AutoresearchScriptsTestBase


class MetricsAcceptanceContractTest(AutoresearchScriptsTestBase):
    def test_acceptance_criteria_rejects_legacy_metric_op_value_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self.init_git_repo(repo)

            completed = self.run_script_completed(
                "autoresearch_init_run.py",
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
                "--acceptance-criteria",
                json.dumps([{"metric": "failure count", "op": "<=", "value": 0}]),
                "--baseline-metric",
                "10",
                "--baseline-commit",
                "base111",
                "--baseline-description",
                "baseline failures",
                cwd=repo,
            )

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("metric_key", completed.stderr)

    def test_metrics_json_requires_baseline_metrics_and_required_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self.init_git_repo(repo)
            criteria = json.dumps([{"metric_key": "accuracy", "operator": ">=", "target": 0.9}])

            missing_metrics = self.run_script_completed(
                "autoresearch_init_run.py",
                "--repo",
                str(repo),
                "--mode",
                "loop",
                "--goal",
                "Improve accuracy",
                "--scope",
                "src/**/*.py",
                "--metric-name",
                "loss",
                "--direction",
                "lower",
                "--verify",
                "python3 -c pass",
                "--verify-format",
                "metrics_json",
                "--primary-metric-key",
                "loss",
                "--acceptance-criteria",
                criteria,
                "--baseline-metric",
                "1.2",
                "--baseline-commit",
                "base111",
                "--baseline-description",
                "baseline loss",
                cwd=repo,
            )

            self.assertNotEqual(missing_metrics.returncode, 0)
            self.assertIn("--baseline-metrics-json is required", missing_metrics.stderr)

            missing_key = self.run_script_completed(
                "autoresearch_init_run.py",
                "--repo",
                str(repo),
                "--mode",
                "loop",
                "--goal",
                "Improve accuracy",
                "--scope",
                "src/**/*.py",
                "--metric-name",
                "loss",
                "--direction",
                "lower",
                "--verify",
                "python3 -c pass",
                "--verify-format",
                "metrics_json",
                "--primary-metric-key",
                "loss",
                "--acceptance-criteria",
                criteria,
                "--baseline-metric",
                "1.2",
                "--baseline-metrics-json",
                json.dumps({"loss": 1.2}),
                "--baseline-commit",
                "base111",
                "--baseline-description",
                "baseline loss",
                cwd=repo,
            )

            self.assertNotEqual(missing_key.returncode, 0)
            self.assertIn("requires metrics keys: accuracy", missing_key.stderr)

    def test_metrics_json_record_iteration_requires_structured_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self.init_git_repo(repo)
            criteria = json.dumps([{"metric_key": "accuracy", "operator": ">=", "target": 0.9}])

            self.run_script(
                "autoresearch_init_run.py",
                "--repo",
                str(repo),
                "--mode",
                "loop",
                "--goal",
                "Improve accuracy",
                "--scope",
                "src/**/*.py",
                "--metric-name",
                "loss",
                "--direction",
                "lower",
                "--verify",
                "python3 -c pass",
                "--verify-format",
                "metrics_json",
                "--primary-metric-key",
                "loss",
                "--acceptance-criteria",
                criteria,
                "--baseline-metric",
                "1.2",
                "--baseline-metrics-json",
                json.dumps({"loss": 1.2, "accuracy": 0.7}),
                "--baseline-commit",
                "base111",
                "--baseline-description",
                "baseline loss",
                cwd=repo,
            )

            missing_metrics = self.run_script_completed(
                "autoresearch_record_iteration.py",
                "--status",
                "keep",
                "--metric",
                "0.8",
                "--commit",
                "keep222",
                "--guard",
                "pass",
                "--description",
                "lower loss",
                cwd=repo,
            )
            self.assertNotEqual(missing_metrics.returncode, 0)
            self.assertIn("--metrics-json is required", missing_metrics.stderr)

            mismatch = self.run_script_completed(
                "autoresearch_record_iteration.py",
                "--status",
                "keep",
                "--metric",
                "0.8",
                "--metrics-json",
                json.dumps({"loss": 0.75, "accuracy": 0.95}),
                "--commit",
                "keep222",
                "--guard",
                "pass",
                "--description",
                "lower loss",
                cwd=repo,
            )
            self.assertNotEqual(mismatch.returncode, 0)
            self.assertIn("Primary metric mismatch", mismatch.stderr)

            trailing_text = self.run_script_completed(
                "autoresearch_record_iteration.py",
                "--status",
                "keep",
                "--metric",
                "0.8",
                "--metrics-json",
                json.dumps({"loss": 0.8, "accuracy": 0.95}) + "\ntrailing text",
                "--commit",
                "keep222",
                "--guard",
                "pass",
                "--description",
                "lower loss",
                cwd=repo,
            )
            self.assertNotEqual(trailing_text.returncode, 0)
            self.assertIn("final non-empty verify output line", trailing_text.stderr)

            kept = self.run_script(
                "autoresearch_record_iteration.py",
                "--status",
                "keep",
                "--metric",
                "0.8",
                "--metrics-json",
                "verify log line\n" + json.dumps({"loss": 0.8, "accuracy": 0.95}),
                "--commit",
                "keep222",
                "--guard",
                "pass",
                "--description",
                "lower loss",
                cwd=repo,
            )
            self.assertEqual(kept["status"], "keep")
            self.assertTrue(kept["retained_acceptance"])

            kept_from_metrics = self.run_script(
                "autoresearch_record_iteration.py",
                "--status",
                "keep",
                "--metrics-json",
                json.dumps({"loss": 0.7, "accuracy": 0.96}),
                "--commit",
                "keep333",
                "--guard",
                "pass",
                "--description",
                "lower loss from metrics json",
                cwd=repo,
            )
            self.assertEqual(kept_from_metrics["status"], "keep")
            self.assertEqual(kept_from_metrics["trial_metric"], 0.7)
            self.assertEqual(kept_from_metrics["retained_metric"], 0.7)

    def test_metrics_json_non_measured_status_does_not_require_trial_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self.init_git_repo(repo)
            criteria = json.dumps([{"metric_key": "accuracy", "operator": ">=", "target": 0.9}])

            self.run_script(
                "autoresearch_init_run.py",
                "--repo",
                str(repo),
                "--mode",
                "loop",
                "--goal",
                "Improve accuracy",
                "--scope",
                "src/**/*.py",
                "--metric-name",
                "loss",
                "--direction",
                "lower",
                "--verify",
                "python3 -c pass",
                "--verify-format",
                "metrics_json",
                "--primary-metric-key",
                "loss",
                "--acceptance-criteria",
                criteria,
                "--baseline-metric",
                "1.2",
                "--baseline-metrics-json",
                json.dumps({"loss": 1.2, "accuracy": 0.7}),
                "--baseline-commit",
                "base111",
                "--baseline-description",
                "baseline loss",
                cwd=repo,
            )

            blocked = self.run_script(
                "autoresearch_record_iteration.py",
                "--status",
                "blocked",
                "--description",
                "external dependency unavailable",
                cwd=repo,
            )

            self.assertEqual(blocked["status"], "blocked")
            self.assertEqual(blocked["retained_metric"], 1.2)
            self.assertFalse(blocked["retained_acceptance"])
            state = json.loads(self.managed_state_path(repo).read_text(encoding="utf-8"))
            self.assertEqual(state["state"]["current_metrics"], {"accuracy": 0.7, "loss": 1.2})
            self.assertEqual(state["state"]["last_trial_metrics"], {"accuracy": 0.7, "loss": 1.2})

    def test_supervisor_requires_acceptance_and_stop_condition_when_both_are_configured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self.init_git_repo(repo)

            self.run_script(
                "autoresearch_init_run.py",
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
                "--acceptance-criteria",
                json.dumps([{"metric_key": "failure count", "operator": "<=", "target": 5}]),
                "--stop-condition",
                "stop when metric reaches 0",
                "--baseline-metric",
                "10",
                "--baseline-commit",
                "base111",
                "--baseline-description",
                "baseline failures",
                cwd=repo,
            )
            self.run_script(
                "autoresearch_record_iteration.py",
                "--status",
                "keep",
                "--metric",
                "4",
                "--commit",
                "keep222",
                "--guard",
                "pass",
                "--description",
                "accepted but not stopped",
                cwd=repo,
            )

            not_done = self.run_script("autoresearch_supervisor_status.py", "--repo", str(repo), cwd=repo)
            self.assertEqual(not_done["decision"], "relaunch")
            self.assertTrue(
                any("stop condition is not yet satisfied" in reason for reason in not_done["reasons"])
            )

            self.run_script(
                "autoresearch_record_iteration.py",
                "--status",
                "keep",
                "--metric",
                "0",
                "--commit",
                "keep333",
                "--guard",
                "pass",
                "--description",
                "accepted and stopped",
                cwd=repo,
            )
            done = self.run_script("autoresearch_supervisor_status.py", "--repo", str(repo), cwd=repo)
            self.assertEqual(done["decision"], "stop")
            self.assertEqual(done["reason"], "goal_reached")
