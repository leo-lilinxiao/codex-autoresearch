from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"


class AutoresearchScriptsTest(unittest.TestCase):
    maxDiff = None

    def run_script_completed(
        self, script_name: str, *args: str, cwd: Path | None = None
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / script_name), *args],
            capture_output=True,
            text=True,
            cwd=cwd,
        )

    def run_script(
        self, script_name: str, *args: str, cwd: Path | None = None
    ) -> dict[str, object]:
        completed = self.run_script_completed(script_name, *args, cwd=cwd)
        completed.check_returncode()
        return json.loads(completed.stdout)

    def run_script_text(
        self, script_name: str, *args: str, cwd: Path | None = None
    ) -> str:
        completed = self.run_script_completed(script_name, *args, cwd=cwd)
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
        verify: str = "pytest -q",
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
        verify: str = "pytest -q",
        guard: str = "python -m py_compile src",
    ) -> dict[str, object]:
        return self.run_script(
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
        )

    def test_init_and_serial_iteration_state_is_consistent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            results_path = tmpdir / "research-results.tsv"
            state_path = tmpdir / "autoresearch-state.json"

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

    def test_discard_requires_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            results_path = tmpdir / "research-results.tsv"
            state_path = tmpdir / "autoresearch-state.json"

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
            results_path = tmpdir / "research-results.tsv"
            state_path = tmpdir / "autoresearch-state.json"

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
            results_path = tmpdir / "research-results.tsv"
            state_path = tmpdir / "autoresearch-state.json"

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

    def test_parallel_batch_selects_best_worker_and_appends_main_row(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            results_path = tmpdir / "research-results.tsv"
            state_path = tmpdir / "autoresearch-state.json"
            batch_path = tmpdir / "batch.json"

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

    def test_resume_check_can_rebuild_missing_state_from_tsv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            results_path = tmpdir / "research-results.tsv"
            state_path = tmpdir / "autoresearch-state.json"

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
            results_path = tmpdir / "research-results.tsv"
            state_path = tmpdir / "autoresearch-state.json"

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

    def test_resume_check_ignores_stale_exec_scratch_for_fresh_interactive_repo(self) -> None:
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
                            "splits": 0,
                            "consecutive_discards": 0,
                            "pivot_count": 0,
                            "last_status": "keep",
                        },
                    }
                ),
                encoding="utf-8",
            )

            resume = self.run_script("autoresearch_resume_check.py", cwd=repo)
            self.assertEqual(resume["decision"], "fresh_start")
            self.assertEqual(resume["state_path"], "autoresearch-state.json")

    def test_resume_check_treats_incomplete_json_state_as_unusable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            results_path = tmpdir / "research-results.tsv"
            state_path = tmpdir / "autoresearch-state.json"

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
            results_path = tmpdir / "research-results.tsv"
            state_path = tmpdir / "autoresearch-state.json"

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
                            "splits": 0,
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
            results_path = tmpdir / "research-results.tsv"
            state_path = tmpdir / "autoresearch-state.json"

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
            results_path = repo / "research-results.tsv"
            state_path = repo / "autoresearch-state.json"

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
                "pytest -q",
                "--baseline-metric",
                "10",
                "--baseline-commit",
                "a1b2c3d",
                "--baseline-description",
                "baseline failures",
                cwd=REPO_ROOT.parent,
            )
            self.assertEqual(result["state_path"], str(state_path))
            self.assertTrue(state_path.exists())

    def test_resume_check_uses_repo_state_for_absolute_results_path_outside_repo_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
            results_path = repo / "research-results.tsv"
            state_path = repo / "autoresearch-state.json"
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
                "pytest -q",
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
            self.assertEqual(resume["state_path"], str(state_path))

    def test_exec_mode_uses_scratch_state_and_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            results_path = tmpdir / "research-results.tsv"
            repo_state_path = tmpdir / "autoresearch-state.json"
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
                "pytest -q",
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

    def test_resume_check_defaults_to_exec_scratch_when_log_declares_exec_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            results_path = tmpdir / "research-results.tsv"
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
                "pytest -q",
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
            (repo / ".git").mkdir()
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
                "pytest -q",
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
            self.assertFalse(state.get("stale", False))

    def test_record_iteration_does_not_use_exec_scratch_for_loop_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            results_path = tmpdir / "research-results.tsv"
            scratch_state_path = Path(
                self.run_script_text(
                    "autoresearch_exec_state.py",
                    "--repo-root",
                    str(tmpdir),
                )
            )

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
                            "splits": 0,
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
            self.assertIn("Missing JSON file", completed.stderr)

    def test_record_iteration_uses_repo_state_for_absolute_results_path_outside_repo_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
            results_path = repo / "research-results.tsv"
            state_path = repo / "autoresearch-state.json"
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
                "pytest -q",
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
            self.assertEqual(result["state_path"], str(state_path))
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["state"]["iteration"], 1)
            self.assertEqual(state["state"]["current_metric"], 8)

    def test_parallel_batch_uses_best_discarded_attempt_when_nothing_keeps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            results_path = tmpdir / "research-results.tsv"
            state_path = tmpdir / "autoresearch-state.json"
            batch_path = tmpdir / "batch.json"

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
            self.assertIn("1\t-\t11\t+1\tpass\tdiscard", log_text)

            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["state"]["current_metric"], 10)
            self.assertEqual(state["state"]["last_trial_metric"], 11)
            self.assertEqual(state["state"]["last_trial_commit"], "d4e5f6a")

    def test_parallel_batch_keep_requires_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            results_path = tmpdir / "research-results.tsv"
            state_path = tmpdir / "autoresearch-state.json"
            batch_path = tmpdir / "batch.json"

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

    def test_drift_and_later_keep_preserve_historical_best_metric(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            results_path = tmpdir / "research-results.tsv"
            state_path = tmpdir / "autoresearch-state.json"

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
            results_path = tmpdir / "research-results.tsv"
            state_path = tmpdir / "autoresearch-state.json"

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
            results_path = tmpdir / "research-results.tsv"
            state_path = tmpdir / "autoresearch-state.json"

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

    def test_supervisor_status_relaunches_after_non_terminal_turn(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            results_path = tmpdir / "research-results.tsv"
            state_path = tmpdir / "autoresearch-state.json"

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
            results_path = tmpdir / "research-results.tsv"
            state_path = tmpdir / "autoresearch-state.json"

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

    def test_supervisor_status_stops_at_iteration_cap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            results_path = tmpdir / "research-results.tsv"
            state_path = tmpdir / "autoresearch-state.json"

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

    def test_supervisor_status_stops_when_stop_condition_reaches_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            results_path = tmpdir / "research-results.tsv"
            state_path = tmpdir / "autoresearch-state.json"

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

    def test_supervisor_status_stops_when_fix_mode_reaches_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            results_path = tmpdir / "research-results.tsv"
            state_path = tmpdir / "autoresearch-state.json"

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

    def test_supervisor_status_does_not_auto_stop_debug_mode_at_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            results_path = tmpdir / "research-results.tsv"
            state_path = tmpdir / "autoresearch-state.json"

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
            results_path = tmpdir / "research-results.tsv"
            state_path = tmpdir / "autoresearch-state.json"

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
            results_path = tmpdir / "research-results.tsv"
            state_path = tmpdir / "autoresearch-state.json"

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

    def test_supervisor_status_detects_stagnation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            results_path = tmpdir / "research-results.tsv"
            state_path = tmpdir / "autoresearch-state.json"

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
            results_path = tmpdir / "research-results.tsv"

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
                "--results-path",
                str(tmpdir / "research-results.tsv"),
                "--launch-path",
                str(launch_path),
                "--runtime-path",
                str(tmpdir / "autoresearch-runtime.json"),
            )
            self.assertEqual(gate["decision"], "fresh")
            self.assertEqual(gate["reason"], "confirmed_launch_without_artifacts")

            prompt = self.run_script_text(
                "autoresearch_resume_prompt.py",
                "--results-path",
                str(tmpdir / "research-results.tsv"),
                "--launch-path",
                str(launch_path),
                "--runtime-path",
                str(tmpdir / "autoresearch-runtime.json"),
            )
            self.assertIn("$codex-autoresearch", prompt)
            self.assertIn("The human already completed the confirmation phase", prompt)
            self.assertIn(f"Use {launch_path}", prompt)
            self.assertIn("Do not run the interactive wizard again.", prompt)
            self.assertIn("Stop condition: stop when metric reaches 0", prompt)

            status = self.run_script(
                "autoresearch_runtime_ctl.py",
                "status",
                "--repo",
                str(tmpdir),
            )
            self.assertEqual(status["status"], "idle")
            self.assertEqual(status["reason"], "confirmed_launch_without_artifacts")

    def test_launch_gate_requires_human_when_state_and_tsv_diverge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            results_path = tmpdir / "research-results.tsv"
            state_path = tmpdir / "autoresearch-state.json"

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

    def test_runtime_start_requires_confirmed_launch_manifest(self) -> None:
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
            self.assertIn("Missing JSON file", completed.stderr)
            self.assertFalse((tmpdir / "autoresearch-runtime.json").exists())

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
                "--results-path",
                str(tmpdir / "research-results.tsv"),
                "--launch-path",
                str(tmpdir / "autoresearch-launch.json"),
                "--runtime-path",
                str(tmpdir / "autoresearch-runtime.json"),
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
                    '  "$python_bin" "$init_script" --results-path research-results.tsv --state-path autoresearch-state.json --mode loop --goal "Reduce failures" --scope "src/**/*.py" --metric-name "failure count" --direction lower --verify "pytest -q" --baseline-metric 10 --baseline-commit a1b2c3d --baseline-description "baseline failures"',
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
            self.assertEqual(state["supervisor"]["recommended_action"], "needs_human")
            self.assertEqual(state["supervisor"]["terminal_reason"], "blocked")
            self.assertEqual(state["supervisor"]["restart_count"], 2)

            runtime = json.loads((tmpdir / "autoresearch-runtime.json").read_text(encoding="utf-8"))
            self.assertEqual(runtime["status"], "needs_human")
            self.assertEqual(runtime["terminal_reason"], "blocked")
            self.assertTrue(results_path.exists())
            self.assertTrue(state_path.exists())

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

    def test_decision_script_derives_keep_for_improvement(self) -> None:
        result = self.run_script(
            "autoresearch_decision.py",
            "--direction",
            "lower",
            "--current-metric",
            "10",
            "--trial-metric",
            "8",
            "--guard",
            "pass",
        )
        self.assertEqual(result["status"], "keep")
        self.assertTrue(result["improved"])
        self.assertEqual(result["retained_metric"], 8)

    def test_commit_gate_blocks_dirty_prelaunch_and_staged_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
            (repo / "notes.txt").write_text("user change\n", encoding="utf-8")
            (repo / "research-results.tsv").write_text("artifact\n", encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(repo), "add", "research-results.tsv"],
                check=True,
                capture_output=True,
                text=True,
            )

            result = self.run_script(
                "autoresearch_commit_gate.py",
                "--repo",
                str(repo),
                "--phase",
                "prelaunch",
                "--rollback-policy",
                "destructive",
            )
            self.assertEqual(result["decision"], "block")
            self.assertTrue(
                any("unexpected worktree changes before launch" in blocker for blocker in result["blockers"])
            )
            self.assertTrue(
                any("autoresearch-owned artifacts are staged" in blocker for blocker in result["blockers"])
            )
            self.assertTrue(
                any(
                    "destructive rollback requested without prior approval" in blocker
                    for blocker in result["blockers"]
                )
            )

    def test_health_check_reports_warning_for_unexpected_worktree_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
            results_path = repo / "research-results.tsv"
            state_path = repo / "autoresearch-state.json"
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
            (repo / "notes.txt").write_text("surprise\n", encoding="utf-8")

            result = self.run_script(
                "autoresearch_health_check.py",
                "--repo",
                str(repo),
                "--verify-cmd",
                "python3 -c pass",
                "--min-free-mb",
                "1",
            )
            self.assertEqual(result["decision"], "warn")
            self.assertTrue(any("unexpected worktree changes" in warning for warning in result["warnings"]))
            self.assertEqual(result["main_rows"], 1)

    def test_health_check_finds_repo_state_without_explicit_state_path_outside_repo_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
            results_path = repo / "research-results.tsv"
            state_path = repo / "autoresearch-state.json"
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
                "pytest -q",
                "--baseline-metric",
                "10",
                "--baseline-commit",
                "a1b2c3d",
                "--baseline-description",
                "baseline failures",
                cwd=REPO_ROOT.parent,
            )

            result = self.run_script(
                "autoresearch_health_check.py",
                "--repo",
                str(repo),
                "--verify-cmd",
                "python3 -c pass",
                "--min-free-mb",
                "1",
                cwd=REPO_ROOT.parent,
            )
            self.assertEqual(result["decision"], "ok")
            self.assertTrue(result["has_state"])
            self.assertEqual(result["state_path"], str(state_path))
            self.assertFalse(
                any("results log exists without state JSON" in warning for warning in result["warnings"])
            )

    def test_health_check_blocks_when_results_log_is_missing_but_state_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
            results_path = repo / "research-results.tsv"
            state_path = repo / "autoresearch-state.json"
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
            results_path.unlink()

            result = self.run_script(
                "autoresearch_health_check.py",
                "--repo",
                str(repo),
                "--state-path",
                str(state_path),
                "--verify-cmd",
                "python3 -c pass",
                "--min-free-mb",
                "1",
            )
            self.assertEqual(result["decision"], "block")
            self.assertFalse(result["has_results"])
            self.assertTrue(result["has_state"])
            self.assertTrue(
                any(
                    "results log missing while state JSON exists" in blocker
                    for blocker in result["blockers"]
                )
            )

    def test_health_check_corrupt_exec_log_still_uses_exec_scratch_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
            results_path = repo / "research-results.tsv"
            scratch_state_path = Path(
                self.run_script_text(
                    "autoresearch_exec_state.py",
                    "--repo-root",
                    str(repo),
                )
            )
            results_path.write_text(
                "\n".join(
                    [
                        "# mode: exec",
                        "iteration\tcommit\tmetric\tdelta\tguard\tstatus\tdescription",
                        "0\tbase123\t10\t0\t-\tbaseline\tbaseline score",
                        "corrupt",
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
                            "splits": 0,
                            "consecutive_discards": 0,
                            "pivot_count": 0,
                            "last_status": "baseline",
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            result = self.run_script(
                "autoresearch_health_check.py",
                "--repo",
                str(repo),
                "--verify-cmd",
                "python3 -c pass",
                "--min-free-mb",
                "1",
                cwd=REPO_ROOT.parent,
            )
            self.assertEqual(result["decision"], "block")
            self.assertTrue(result["has_state"])
            self.assertEqual(result["state_path"], str(scratch_state_path))
            self.assertTrue(any("results log is corrupt" in blocker for blocker in result["blockers"]))

    def test_lessons_script_appends_and_lists_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lessons_path = Path(tmp) / "autoresearch-lessons.md"
            self.run_script(
                "autoresearch_lessons.py",
                "append",
                "--lessons-path",
                str(lessons_path),
                "--kind",
                "pivot",
                "--title",
                "Dispatch v2 is graph-unsafe",
                "--insight",
                "Avoid this operator family in the live graph.",
                "--context",
                "16-NPU Jamba smoke",
                "--iteration",
                "77",
            )
            entries = self.run_script(
                "autoresearch_lessons.py",
                "list",
                "--lessons-path",
                str(lessons_path),
            )
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["title"], "Dispatch v2 is graph-unsafe")
            self.assertEqual(entries[0]["kind"], "pivot")


if __name__ == "__main__":
    unittest.main()
