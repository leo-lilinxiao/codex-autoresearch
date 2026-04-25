from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from .base import AutoresearchScriptsTestBase, REPO_ROOT, SCRIPTS_DIR


class AutoresearchPreflightLessonsTest(AutoresearchScriptsTestBase):
    maxDiff = None

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
            (repo / "autoresearch-results").mkdir(parents=True, exist_ok=True)
            (repo / "autoresearch-results/results.tsv").write_text("artifact\n", encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(repo), "add", "autoresearch-results/results.tsv"],
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

    def test_commit_gate_blocks_dirty_precommit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
            (repo / "notes.txt").write_text("user change\n", encoding="utf-8")

            result = self.run_script(
                "autoresearch_commit_gate.py",
                "--repo",
                str(repo),
                "--phase",
                "precommit",
            )
            self.assertEqual(result["decision"], "block")
            self.assertTrue(
                any("unexpected worktree changes before commit" in blocker for blocker in result["blockers"])
            )

    def test_commit_gate_ignores_nested_autoresearch_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
            nested = repo / "sub"
            nested.mkdir()
            (nested / "autoresearch-results").mkdir(parents=True, exist_ok=True)
            (nested / "autoresearch-results/results.tsv").write_text("artifact\n", encoding="utf-8")

            result = self.run_script(
                "autoresearch_commit_gate.py",
                "--repo",
                str(repo),
                "--phase",
                "prelaunch",
                "--scope",
                "src/**/*.py",
            )
            self.assertEqual(result["decision"], "allow")
            self.assertEqual(result["unexpected_worktree"], [])

    def test_commit_gate_treats_directory_scope_as_in_scope_subtree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
            src = repo / "src"
            src.mkdir()
            (src / "foo.py").write_text("print('ok')\n", encoding="utf-8")

            result = self.run_script(
                "autoresearch_commit_gate.py",
                "--repo",
                str(repo),
                "--phase",
                "prelaunch",
                "--scope",
                "src/",
            )
            self.assertEqual(result["decision"], "allow")
            self.assertEqual(result["unexpected_worktree"], [])

    def test_commit_gate_treats_nested_directory_scope_as_in_scope_subtree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
            nested = repo / "src" / "pkg"
            nested.mkdir(parents=True)
            (nested / "a.py").write_text("print('ok')\n", encoding="utf-8")

            result = self.run_script(
                "autoresearch_commit_gate.py",
                "--repo",
                str(repo),
                "--phase",
                "prelaunch",
                "--scope",
                "src/",
            )
            self.assertEqual(result["decision"], "allow")
            self.assertEqual(result["unexpected_worktree"], [])

    def test_commit_gate_blocks_rename_from_out_of_scope_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
            docs = repo / "docs"
            src = repo / "src"
            docs.mkdir()
            src.mkdir()
            (docs / "old.txt").write_text("tracked\n", encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(repo), "add", "docs/old.txt"],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "-C", str(repo), "commit", "-m", "init"],
                check=True,
                capture_output=True,
                text=True,
            )
            (docs / "old.txt").rename(src / "new.py")
            subprocess.run(
                ["git", "-C", str(repo), "add", "-A"],
                check=True,
                capture_output=True,
                text=True,
            )

            result = self.run_script(
                "autoresearch_commit_gate.py",
                "--repo",
                str(repo),
                "--phase",
                "precommit",
                "--scope",
                "src/**/*.py",
            )
            self.assertEqual(result["decision"], "block")
            self.assertIn("docs/old.txt", result["unexpected_worktree"])

    def test_commit_gate_blocks_rename_from_artifact_source_into_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
            artifact = repo / "autoresearch-results/state.json"
            src = repo / "src"
            src.mkdir()
            artifact.parent.mkdir(parents=True, exist_ok=True)
            artifact.write_text("{}\n", encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(repo), "add", "autoresearch-results/state.json"],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "-C", str(repo), "commit", "-m", "tracked artifact"],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "-C", str(repo), "mv", "autoresearch-results/state.json", "src/state.py"],
                check=True,
                capture_output=True,
                text=True,
            )

            result = self.run_script(
                "autoresearch_commit_gate.py",
                "--repo",
                str(repo),
                "--phase",
                "precommit",
                "--scope",
                "src/**/*.py",
            )
            self.assertEqual(result["decision"], "block")
            self.assertIn("autoresearch-results/state.json", result["staged_artifacts"])

    def test_commit_gate_allows_in_scope_changes_in_companion_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            primary = root / "primary"
            companion = root / "companion"
            primary.mkdir()
            companion.mkdir()
            subprocess.run(["git", "init", str(primary)], check=True, capture_output=True, text=True)
            subprocess.run(["git", "init", str(companion)], check=True, capture_output=True, text=True)
            nested = companion / "pkg"
            nested.mkdir(parents=True)
            (nested / "a.py").write_text("print('ok')\n", encoding="utf-8")

            result = self.run_script(
                "autoresearch_commit_gate.py",
                "--repo",
                str(primary),
                "--phase",
                "precommit",
                "--scope",
                "src/**/*.py",
                "--companion-repo-scope",
                f"{companion}=pkg/",
            )
            self.assertEqual(result["decision"], "allow")
            self.assertEqual(len(result["repo_gates"]), 2)
            companion_gate = next(g for g in result["repo_gates"] if g["role"] == "companion")
            self.assertEqual(companion_gate["unexpected_worktree"], [])

    def test_commit_gate_blocks_out_of_scope_changes_in_companion_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            primary = root / "primary"
            companion = root / "companion"
            primary.mkdir()
            companion.mkdir()
            subprocess.run(["git", "init", str(primary)], check=True, capture_output=True, text=True)
            subprocess.run(["git", "init", str(companion)], check=True, capture_output=True, text=True)
            (companion / "notes.txt").write_text("drift\n", encoding="utf-8")

            result = self.run_script(
                "autoresearch_commit_gate.py",
                "--repo",
                str(primary),
                "--phase",
                "precommit",
                "--scope",
                "src/**/*.py",
                "--companion-repo-scope",
                f"{companion}=pkg/",
            )
            self.assertEqual(result["decision"], "block")
            self.assertTrue(any(f"[{companion.resolve()}]" in blocker for blocker in result["blockers"]))

    def test_health_check_reports_warning_for_unexpected_worktree_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
            results_path = repo / "autoresearch-results/results.tsv"
            state_path = repo / "autoresearch-results/state.json"
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
                "--results-path",
                str(results_path),
                "--verify-cmd",
                "python3 -c pass",
                "--min-free-mb",
                "1",
            )
            self.assertEqual(result["decision"], "warn")
            self.assertTrue(any("unexpected worktree changes" in warning for warning in result["warnings"]))
            self.assertEqual(result["main_rows"], 1)

    def test_health_check_ignores_nested_autoresearch_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
            nested = repo / "sub"
            nested.mkdir()
            results_path = nested / "autoresearch-results/results.tsv"
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

            result = self.run_script(
                "autoresearch_health_check.py",
                "--repo",
                str(repo),
                "--results-path",
                str(results_path),
                "--verify-cmd",
                "python3 -c pass",
                "--min-free-mb",
                "1",
            )
            self.assertEqual(result["decision"], "warn")
            self.assertFalse(any("unexpected worktree changes" in warning for warning in result["warnings"]))
            self.assertTrue(any("TSV fallback" in warning for warning in result["warnings"]))

    def test_health_check_reports_rename_from_out_of_scope_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
            results_path = repo / "autoresearch-results/results.tsv"
            state_path = repo / "autoresearch-results/state.json"
            docs = repo / "docs"
            src = repo / "src"
            docs.mkdir()
            src.mkdir()
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
            (docs / "old.txt").write_text("tracked\n", encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(repo), "add", "docs/old.txt"],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "-C", str(repo), "commit", "-m", "tracked docs"],
                check=True,
                capture_output=True,
                text=True,
            )
            (docs / "old.txt").rename(src / "new.py")
            subprocess.run(
                ["git", "-C", str(repo), "add", "-A"],
                check=True,
                capture_output=True,
                text=True,
            )

            result = self.run_script(
                "autoresearch_health_check.py",
                "--repo",
                str(repo),
                "--results-path",
                str(results_path),
                "--verify-cmd",
                "python3 -c pass",
                "--min-free-mb",
                "1",
            )
            self.assertEqual(result["decision"], "warn")
            self.assertTrue(any("docs/old.txt" in warning for warning in result["warnings"]))

    def test_health_check_ignores_in_scope_directory_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
            src = repo / "src"
            src.mkdir()
            (src / "foo.py").write_text("print('ok')\n", encoding="utf-8")

            result = self.run_script(
                "autoresearch_health_check.py",
                "--repo",
                str(repo),
                "--results-path",
                str(repo / "autoresearch-results/results.tsv"),
                "--verify-cmd",
                "python3 -c pass",
                "--scope",
                "src/",
                "--min-free-mb",
                "1",
            )
            self.assertEqual(result["decision"], "ok")
            self.assertFalse(any("unexpected worktree changes" in warning for warning in result["warnings"]))

    def test_health_check_ignores_nested_in_scope_directory_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
            nested = repo / "src" / "pkg"
            nested.mkdir(parents=True)
            (nested / "a.py").write_text("print('ok')\n", encoding="utf-8")

            result = self.run_script(
                "autoresearch_health_check.py",
                "--repo",
                str(repo),
                "--results-path",
                str(repo / "autoresearch-results/results.tsv"),
                "--verify-cmd",
                "python3 -c pass",
                "--scope",
                "src/",
                "--min-free-mb",
                "1",
            )
            self.assertEqual(result["decision"], "ok")
            self.assertFalse(any("unexpected worktree changes" in warning for warning in result["warnings"]))

    def test_health_check_warns_for_companion_repo_out_of_scope_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            primary = root / "primary"
            companion = root / "companion"
            primary.mkdir()
            companion.mkdir()
            subprocess.run(["git", "init", str(primary)], check=True, capture_output=True, text=True)
            subprocess.run(["git", "init", str(companion)], check=True, capture_output=True, text=True)
            (companion / "notes.txt").write_text("surprise\n", encoding="utf-8")

            result = self.run_script(
                "autoresearch_health_check.py",
                "--repo",
                str(primary),
                "--results-path",
                str(primary / "autoresearch-results/results.tsv"),
                "--verify-cmd",
                "python3 -c pass",
                "--scope",
                "src/**/*.py",
                "--companion-repo-scope",
                f"{companion}=pkg/",
                "--min-free-mb",
                "1",
            )
            self.assertEqual(result["decision"], "warn")
            self.assertTrue(any(f"[{companion.resolve()}]" in warning for warning in result["warnings"]))
            self.assertEqual(len(result["repo_worktree_checks"]), 2)

    def test_health_check_requires_repo_when_pointer_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = base / "target"
            repo.mkdir()
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
            (repo / "notes.txt").write_text("surprise\n", encoding="utf-8")

            completed = self.run_script_completed(
                "autoresearch_health_check.py",
                "--results-path",
                str(repo / "autoresearch-results/results.tsv"),
                "--state-path",
                str(repo / "autoresearch-results/state.json"),
                "--verify-cmd",
                "python3 -c pass",
                "--min-free-mb",
                "1",
                cwd=base,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("the following arguments are required: --repo", completed.stderr)

    def test_health_check_blocks_when_verify_command_is_missing_from_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            env = dict(os.environ)
            env["PATH"] = "/nonexistent"

            result = self.run_script(
                "autoresearch_health_check.py",
                "--repo",
                str(repo),
                "--results-path",
                str(repo / "autoresearch-results/results.tsv"),
                "--state-path",
                str(repo / "autoresearch-results/state.json"),
                "--verify-cmd",
                "python -V",
                "--min-free-mb",
                "1",
                env=env,
            )
            self.assertEqual(result["decision"], "block")
            self.assertTrue(
                any("verify command is not executable" in blocker for blocker in result["blockers"])
            )

    def test_health_check_accepts_verify_command_with_env_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)

            result = self.run_script(
                "autoresearch_health_check.py",
                "--repo",
                str(repo),
                "--results-path",
                str(repo / "autoresearch-results/results.tsv"),
                "--state-path",
                str(repo / "autoresearch-results/state.json"),
                "--verify-cmd",
                f"FOO=1 {sys.executable} -V",
                "--min-free-mb",
                "1",
            )
            self.assertEqual(result["decision"], "ok")
            self.assertEqual(result["blockers"], [])

    def test_health_check_finds_repo_state_without_explicit_state_path_outside_repo_cwd(self) -> None:
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
                "--results-path",
                str(results_path),
                "--verify-cmd",
                "python3 -c pass",
                "--min-free-mb",
                "1",
                cwd=REPO_ROOT.parent,
            )
            self.assertEqual(result["decision"], "ok")
            self.assertTrue(result["has_state"])
            self.assertEqual(Path(str(result["state_path"])).resolve(), state_path.resolve())
            self.assertFalse(
                any("results log exists without state JSON" in warning for warning in result["warnings"])
            )

    def test_health_check_blocks_when_results_log_is_missing_but_state_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
            results_path = repo / "autoresearch-results/results.tsv"
            state_path = repo / "autoresearch-results/state.json"
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

    def test_health_check_warns_when_state_diverges_from_tsv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
            results_path = repo / "autoresearch-results/results.tsv"
            state_path = repo / "autoresearch-results/state.json"
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

            result = self.run_script(
                "autoresearch_health_check.py",
                "--repo",
                str(repo),
                "--results-path",
                str(results_path),
                "--verify-cmd",
                "python3 -c pass",
                "--min-free-mb",
                "1",
            )
            self.assertEqual(result["decision"], "warn")
            self.assertEqual(result["resume_detail"], "state_tsv_diverged")
            self.assertTrue(
                any("diverges from the reconstructed TSV state" in warning for warning in result["warnings"])
            )

    def test_health_check_corrupt_exec_log_still_uses_exec_scratch_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
            results_path = repo / "autoresearch-results/results.tsv"
            scratch_state_path = Path(
                self.run_script_text(
                    "autoresearch_exec_state.py",
                    "--repo-root",
                    str(repo),
                )
            )
            results_path.parent.mkdir(parents=True, exist_ok=True)
            results_path.write_text(
                "\n".join(
                    [
                        "# mode: exec",
                        f"# workspace_root: {repo}",
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
                "--results-path",
                str(results_path),
                "--verify-cmd",
                "python3 -c pass",
                "--min-free-mb",
                "1",
                cwd=REPO_ROOT.parent,
            )
            self.assertEqual(result["decision"], "block")
            self.assertTrue(result["has_state"])
            self.assertEqual(Path(str(result["state_path"])).resolve(), scratch_state_path.resolve())
            self.assertTrue(any("results log is corrupt" in blocker for blocker in result["blockers"]))

    def test_lessons_script_appends_and_lists_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lessons_path = Path(tmp) / "autoresearch-results/lessons.md"
            self.run_script(
                "autoresearch_lessons.py",
                "append",
                "--lessons-path",
                str(lessons_path),
                "--title",
                "Dispatch v2 is graph-unsafe",
                "--strategy",
                "Directly substitute vendor dispatch_v2 in the live graph.",
                "--outcome",
                "pivot",
                "--insight",
                "Avoid this operator family in the live graph.",
                "--context",
                "goal=Improve Jamba throughput; scope=moe dispatch; metric=avg_mfu; direction=higher",
                "--iteration",
                "run77#77",
            )
            entries = self.run_script(
                "autoresearch_lessons.py",
                "list",
                "--lessons-path",
                str(lessons_path),
            )
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["title"], "Dispatch v2 is graph-unsafe")
            self.assertEqual(entries[0]["outcome"], "pivot")
            self.assertEqual(entries[0]["id"], "L-1")

    def test_lessons_list_backs_up_corrupt_file_and_recovers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lessons_path = Path(tmp) / "autoresearch-results/lessons.md"
            lessons_path.parent.mkdir(parents=True, exist_ok=True)
            lessons_path.write_text("this is not a valid lesson file\n", encoding="utf-8")

            entries = self.run_script(
                "autoresearch_lessons.py",
                "list",
                "--lessons-path",
                str(lessons_path),
            )

            self.assertEqual(entries, [])
            backups = sorted(Path(tmp).glob("autoresearch-results/lessons.md.*.bak"))
            self.assertEqual(len(backups), 1)
            self.assertFalse(lessons_path.exists())
            self.assertIn("this is not a valid lesson file", backups[0].read_text(encoding="utf-8"))

    def test_summary_lesson_is_not_suppressed_across_runs_without_run_tag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lessons_path = Path(tmp) / "autoresearch-results/lessons.md"
            self.run_script(
                "autoresearch_lessons.py",
                "append",
                "--lessons-path",
                str(lessons_path),
                "--title",
                "Previous run summary",
                "--strategy",
                "Runtime completion summary",
                "--outcome",
                "summary",
                "--insight",
                "Previous run ended cleanly.",
                "--context",
                "goal=Reduce failures; scope=src/**/*.py; metric=failure count; direction=lower",
                "--iteration",
                "2",
            )

            if str(SCRIPTS_DIR) not in sys.path:
                sys.path.insert(0, str(SCRIPTS_DIR))
            from autoresearch_lessons import append_summary_lesson_if_needed

            result = append_summary_lesson_if_needed(
                lessons_path=lessons_path,
                state_payload={
                    "mode": "loop",
                    "config": {
                        "goal": "Reduce failures",
                        "scope": "src/**/*.py",
                        "metric": "failure count",
                        "direction": "lower",
                    },
                    "state": {
                        "best_metric": 1,
                        "best_iteration": 2,
                        "iteration": 3,
                        "last_status": "keep",
                    },
                },
                current_iteration=3,
            )

            self.assertIsNotNone(result)
            entries = self.run_script(
                "autoresearch_lessons.py",
                "list",
                "--lessons-path",
                str(lessons_path),
            )
            self.assertEqual(len(entries), 2)
            self.assertEqual(entries[-1]["outcome"], "summary")
            self.assertEqual(entries[-1]["iteration"], "3")

    def test_lessons_capacity_compacts_old_history_and_preserves_current_run_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lessons_path = Path(tmp) / "autoresearch-results/lessons.md"

            if str(SCRIPTS_DIR) not in sys.path:
                sys.path.insert(0, str(SCRIPTS_DIR))
            from autoresearch_lessons import append_lesson, list_entries_with_recovery

            for index in range(50):
                append_lesson(
                    lessons_path=lessons_path,
                    title=f"Dispatch lesson {index}",
                    strategy="Dispatch family tuning",
                    outcome="discard",
                    insight=f"Historical miss {index}",
                    context=(
                        "goal=Improve throughput; scope=dispatch; metric=avg_mfu; "
                        "direction=higher"
                    ),
                    iteration=str(index + 1),
                    timestamp="2026-01-01T00:00:00Z",
                )

            for iteration in range(1, 4):
                append_lesson(
                    lessons_path=lessons_path,
                    title=f"Current run keep {iteration}",
                    strategy="Current run hot-path adjustment",
                    outcome="keep",
                    insight=f"Current run insight {iteration}",
                    context="goal=Improve throughput; scope=hot path; metric=avg_mfu; direction=higher",
                    iteration=f"run77#{iteration}",
                    timestamp="2026-03-26T00:00:00Z",
                )

            entries = list_entries_with_recovery(lessons_path)
            self.assertTrue(any(entry["outcome"] == "summary" for entry in entries))
            self.assertEqual(
                [entry["iteration"] for entry in entries if entry["iteration"].startswith("run77#")],
                ["run77#1", "run77#2", "run77#3"],
            )
            self.assertLessEqual(len(entries), 10)

    def test_lessons_capacity_preserves_untagged_current_run_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lessons_path = Path(tmp) / "autoresearch-results/lessons.md"

            if str(SCRIPTS_DIR) not in sys.path:
                sys.path.insert(0, str(SCRIPTS_DIR))
            from autoresearch_lessons import append_lesson, list_entries_with_recovery

            for iteration in range(1, 52):
                append_lesson(
                    lessons_path=lessons_path,
                    title=f"Current run lesson {iteration}",
                    strategy="Current untagged strategy",
                    outcome="keep",
                    insight=f"Current untagged insight {iteration}",
                    context="goal=Reduce failures; scope=src/**/*.py; metric=failure count; direction=lower",
                    iteration=str(iteration),
                    timestamp="2026-03-26T00:00:00Z",
                )

            entries = list_entries_with_recovery(lessons_path)
            self.assertEqual(len(entries), 51)
            self.assertEqual(entries[0]["iteration"], "1")
            self.assertEqual(entries[-1]["iteration"], "51")
            self.assertFalse(any(entry["outcome"] == "summary" for entry in entries))

    def test_record_iteration_extracts_protocol_lesson_for_keep(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            results_path = tmpdir / "autoresearch-results/results.tsv"
            state_path = tmpdir / "autoresearch-results/state.json"
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
                "deadbee",
                "--description",
                "Chunked dispatch v2 improved the retained metric.",
            )

            entries = self.run_script(
                "autoresearch_lessons.py",
                "list",
                "--lessons-path",
                str(lessons_path),
            )
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["outcome"], "keep")
            self.assertEqual(entries[0]["iteration"], "1")
            self.assertTrue(entries[0]["context"].startswith("goal=Reduce failures"))

    def test_runtime_terminal_appends_summary_lesson(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            results_path = tmpdir / "autoresearch-results/results.tsv"
            state_path = tmpdir / "autoresearch-results/state.json"
            lessons_path = tmpdir / "autoresearch-results/lessons.md"
            fake_codex_path = tmpdir / "fake-codex"
            self.write_fake_codex(fake_codex_path, body_lines=["exit 0"])
            self.create_launch_manifest(
                tmpdir,
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
                "--stop-condition",
                "stop when metric reaches 0",
                "--baseline-metric",
                "0",
                "--baseline-commit",
                "a1b2c3d",
                "--baseline-description",
                "baseline failures",
            )

            started = self.run_script(
                "autoresearch_runtime_ctl.py",
                "start",
                "--repo",
                str(tmpdir),
                "--codex-bin",
                str(fake_codex_path),
            )
            self.assertEqual(started["status"], "running")

            terminal = self.wait_for_runtime_status(tmpdir, {"terminal"})
            self.assertEqual(terminal["status"], "terminal")
            self.assertEqual(terminal["reason"], "goal_reached")

            entries = self.run_script(
                "autoresearch_lessons.py",
                "list",
                "--lessons-path",
                str(lessons_path),
            )
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["outcome"], "summary")
