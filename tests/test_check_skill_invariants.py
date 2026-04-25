from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "check_skill_invariants.py"


class CheckSkillInvariantsTest(unittest.TestCase):
    def run_invariant_check(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            capture_output=True,
            text=True,
        )

    def test_openai_manifest_disables_implicit_invocation(self) -> None:
        manifest = (REPO_ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertRegex(manifest, r"(?m)^\s*allow_implicit_invocation:\s*false\s*$")

    def write_exec_repo(self, repo: Path) -> None:
        (repo / "autoresearch-results").mkdir(parents=True, exist_ok=True)
        (repo / "autoresearch-results/results.tsv").write_text(
            "\n".join(
                [
                    "# metric_direction: lower",
                    "iteration\tcommit\tmetric\tdelta\tguard\tstatus\tdescription",
                    "0\tbase123\t10\t0\t-\tbaseline\tbaseline score",
                    "1\tkeep123\t8\t-2\tpass\tkeep\timproved score",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        (repo / "autoresearch-results/context.json").write_text("{}\n", encoding="utf-8")
        (repo / "autoresearch-results/lessons.md").write_text("# lessons\n", encoding="utf-8")

    def test_exec_expect_improvement_supports_higher_direction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "autoresearch-results").mkdir(parents=True, exist_ok=True)
            (repo / "autoresearch-results/results.tsv").write_text(
                "\n".join(
                    [
                        "# metric_direction: higher",
                        "iteration\tcommit\tmetric\tdelta\tguard\tstatus\tdescription",
                        "0\tbase123\t10\t0\t-\tbaseline\tbaseline score",
                        "1\tkeep123\t12\t+2\tpass\tkeep\timproved score",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (repo / "autoresearch-results/context.json").write_text("{}\n", encoding="utf-8")
            (repo / "autoresearch-results/lessons.md").write_text("# lessons\n", encoding="utf-8")

            completed = self.run_invariant_check(
                "exec",
                "--repo",
                str(repo),
                "--expect-improvement",
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("exec invariants: OK", completed.stdout)

    def test_exec_invariants_reject_keep_rows_without_commit_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "autoresearch-results").mkdir(parents=True, exist_ok=True)
            (repo / "autoresearch-results/results.tsv").write_text(
                "\n".join(
                    [
                        "# metric_direction: lower",
                        "iteration\tcommit\tmetric\tdelta\tguard\tstatus\tdescription",
                        "0\tbase123\t10\t0\t-\tbaseline\tbaseline score",
                        "1\t-\t8\t-2\tpass\tkeep\tinvalid keep row",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (repo / "autoresearch-results/context.json").write_text("{}\n", encoding="utf-8")
            (repo / "autoresearch-results/lessons.md").write_text("# lessons\n", encoding="utf-8")

            completed = self.run_invariant_check("exec", "--repo", str(repo))

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("missing a commit hash", completed.stderr)

    def test_exec_invariants_reject_event_logs_without_bundled_helper_usage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            event_log = repo / "events.jsonl"
            (repo / "autoresearch-results").mkdir(parents=True, exist_ok=True)
            (repo / "autoresearch-results/results.tsv").write_text(
                "\n".join(
                    [
                        "# metric_direction: lower",
                        "iteration\tcommit\tmetric\tdelta\tguard\tstatus\tdescription",
                        "0\tbase123\t10\t0\t-\tbaseline\tbaseline score",
                        "1\tkeep123\t8\t-2\tpass\tkeep\timproved score",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (repo / "autoresearch-results/context.json").write_text("{}\n", encoding="utf-8")
            (repo / "autoresearch-results/lessons.md").write_text("# lessons\n", encoding="utf-8")
            event_log.write_text(
                'command: python3 scripts/autoresearch_init_run.py\n',
                encoding="utf-8",
            )

            completed = self.run_invariant_check(
                "exec",
                "--repo",
                str(repo),
                "--event-log",
                str(event_log),
            )

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("bundled helper scripts", completed.stderr)

    def test_exec_invariants_accept_bundled_helper_usage_in_event_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            event_log = repo / "events.jsonl"
            (repo / "autoresearch-results").mkdir(parents=True, exist_ok=True)
            (repo / "autoresearch-results/results.tsv").write_text(
                "\n".join(
                    [
                        "# metric_direction: lower",
                        "iteration\tcommit\tmetric\tdelta\tguard\tstatus\tdescription",
                        "0\tbase123\t10\t0\t-\tbaseline\tbaseline score",
                        "1\tkeep123\t8\t-2\tpass\tkeep\timproved score",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (repo / "autoresearch-results/context.json").write_text("{}\n", encoding="utf-8")
            (repo / "autoresearch-results/lessons.md").write_text("# lessons\n", encoding="utf-8")
            event_log.write_text(
                "\n".join(
                    [
                        'command: python3 .agents/skills/codex-autoresearch/scripts/autoresearch_init_run.py --mode exec',
                        'command: python3 .agents/skills/codex-autoresearch/scripts/autoresearch_record_iteration.py --status keep',
                        'command: python3 .agents/skills/codex-autoresearch/scripts/autoresearch_exec_state.py --cleanup',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            completed = self.run_invariant_check(
                "exec",
                "--repo",
                str(repo),
                "--event-log",
                str(event_log),
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("exec invariants: OK", completed.stdout)

    def test_exec_invariants_accept_admin_scope_skill_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            event_log = repo / "events.jsonl"
            self.write_exec_repo(repo)
            event_log.write_text(
                "\n".join(
                    [
                        "command: python3 /etc/codex/skills/codex-autoresearch/scripts/autoresearch_init_run.py --mode exec",
                        "command: python3 /etc/codex/skills/codex-autoresearch/scripts/autoresearch_record_iteration.py --status keep",
                        "command: python3 /etc/codex/skills/codex-autoresearch/scripts/autoresearch_exec_state.py --cleanup",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            completed = self.run_invariant_check(
                "exec",
                "--repo",
                str(repo),
                "--event-log",
                str(event_log),
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("exec invariants: OK", completed.stdout)

    def test_exec_invariants_accept_user_scope_skill_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            event_log = repo / "events.jsonl"
            self.write_exec_repo(repo)
            event_log.write_text(
                "\n".join(
                    [
                        "command: python3 /Users/alice/.agents/skills/codex-autoresearch/scripts/autoresearch_init_run.py --mode exec",
                        "command: python3 /Users/alice/.agents/skills/codex-autoresearch/scripts/autoresearch_record_iteration.py --status keep",
                        "command: python3 /Users/alice/.agents/skills/codex-autoresearch/scripts/autoresearch_exec_state.py --cleanup",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            completed = self.run_invariant_check(
                "exec",
                "--repo",
                str(repo),
                "--event-log",
                str(event_log),
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("exec invariants: OK", completed.stdout)

    def test_exec_invariants_accept_absolute_configured_skill_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            event_log = repo / "events.jsonl"
            self.write_exec_repo(repo)
            event_log.write_text(
                "\n".join(
                    [
                        "command: python3 /opt/skills/codex-autoresearch/scripts/autoresearch_init_run.py --mode exec",
                        "command: python3 /opt/skills/codex-autoresearch/scripts/autoresearch_record_iteration.py --status keep",
                        "command: python3 /opt/skills/codex-autoresearch/scripts/autoresearch_exec_state.py --cleanup",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            completed = self.run_invariant_check(
                "exec",
                "--repo",
                str(repo),
                "--event-log",
                str(event_log),
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("exec invariants: OK", completed.stdout)

    def test_exec_invariants_reject_non_json_last_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            last_message = repo / "last-message.txt"
            self.write_exec_repo(repo)
            last_message.write_text("all done\n", encoding="utf-8")

            completed = self.run_invariant_check(
                "exec",
                "--repo",
                str(repo),
                "--last-message-file",
                str(last_message),
            )

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("invalid JSON", completed.stderr)

    def test_exec_invariants_accept_json_completion_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            last_message = repo / "last-message.txt"
            self.write_exec_repo(repo)
            last_message.write_text(
                '{"status":"completed","baseline":10,"best":8,"best_iteration":1,'
                '"total_iterations":1,"keeps":1,"discards":0,"crashes":0,'
                '"improved":true,"exit_code":0}\n',
                encoding="utf-8",
            )

            completed = self.run_invariant_check(
                "exec",
                "--repo",
                str(repo),
                "--last-message-file",
                str(last_message),
                "--expect-improvement",
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("exec invariants: OK", completed.stdout)

    def test_exec_invariants_reject_completion_payload_with_stringified_numbers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            last_message = repo / "last-message.txt"
            self.write_exec_repo(repo)
            last_message.write_text(
                '{"status":"completed","baseline":"10","best":"8","best_iteration":"1",'
                '"total_iterations":"1","keeps":"1","discards":"0","crashes":"0",'
                '"improved":true,"exit_code":0}\n',
                encoding="utf-8",
            )

            completed = self.run_invariant_check(
                "exec",
                "--repo",
                str(repo),
                "--last-message-file",
                str(last_message),
            )

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("field baseline must be a number", completed.stderr)

    def test_exec_invariants_reject_completion_payload_with_boolean_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            last_message = repo / "last-message.txt"
            self.write_exec_repo(repo)
            last_message.write_text(
                '{"status":"completed","baseline":10,"best":8,"best_iteration":1,'
                '"total_iterations":1,"keeps":1,"discards":0,"crashes":0,'
                '"improved":true,"exit_code":false}\n',
                encoding="utf-8",
            )

            completed = self.run_invariant_check(
                "exec",
                "--repo",
                str(repo),
                "--last-message-file",
                str(last_message),
            )

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("field exit_code must be an integer", completed.stderr)

    def test_exec_invariants_accept_ndjson_completion_stream(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            last_message = repo / "last-message.txt"
            self.write_exec_repo(repo)
            last_message.write_text(
                "\n".join(
                    [
                        '{"iteration":1,"commit":"keep123","metric":8,"delta":-2,"guard":"pass","status":"keep","description":"improved score"}',
                        '{"status":"completed","baseline":10,"best":8,"best_iteration":1,"total_iterations":1,"keeps":1,"discards":0,"crashes":0,"improved":true,"exit_code":0}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            completed = self.run_invariant_check(
                "exec",
                "--repo",
                str(repo),
                "--last-message-file",
                str(last_message),
                "--expect-improvement",
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("exec invariants: OK", completed.stdout)

    def test_exec_invariants_reject_ndjson_with_boolean_iteration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            last_message = repo / "last-message.txt"
            self.write_exec_repo(repo)
            last_message.write_text(
                "\n".join(
                    [
                        '{"iteration":true,"commit":"keep123","metric":8,"delta":-2,"guard":"pass","status":"keep","description":"improved score"}',
                        '{"status":"completed","baseline":10,"best":8,"best_iteration":1,"total_iterations":1,"keeps":1,"discards":0,"crashes":0,"improved":true,"exit_code":0}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            completed = self.run_invariant_check(
                "exec",
                "--repo",
                str(repo),
                "--last-message-file",
                str(last_message),
            )

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("field iteration must be an integer", completed.stderr)

    def test_exec_invariants_reject_ndjson_without_completed_final_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            last_message = repo / "last-message.txt"
            self.write_exec_repo(repo)
            last_message.write_text(
                "\n".join(
                    [
                        '{"iteration":1,"commit":"keep123","metric":8,"delta":-2,"guard":"pass","status":"keep","description":"improved score"}',
                        '{"iteration":2,"commit":"keep456","metric":7,"delta":-1,"guard":"pass","status":"keep","description":"improved score again"}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            completed = self.run_invariant_check(
                "exec",
                "--repo",
                str(repo),
                "--last-message-file",
                str(last_message),
            )

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("must report status=completed", completed.stderr)


    def test_exec_invariants_resolve_workspace_via_pointer_when_repo_differs(self) -> None:
        """When workspace_root != repo, the checker must resolve artifacts
        through the git-local pointer instead of assuming repo == workspace."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            repo = Path(tmp) / "primary-repo"
            workspace.mkdir()
            repo.mkdir()

            # init git repo
            subprocess.run(
                ["git", "init", "-b", "main", str(repo)],
                check=True, capture_output=True, text=True,
            )
            subprocess.run(
                ["git", "-C", str(repo), "config", "user.name", "test"],
                check=True, capture_output=True, text=True,
            )
            subprocess.run(
                ["git", "-C", str(repo), "config", "user.email", "t@t.com"],
                check=True, capture_output=True, text=True,
            )
            (repo / "src.py").write_text("x = 1\n", encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(repo), "add", "."],
                check=True, capture_output=True, text=True,
            )
            subprocess.run(
                ["git", "-C", str(repo), "commit", "-m", "init"],
                check=True, capture_output=True, text=True,
            )

            # get a real commit hash from the repo
            result = subprocess.run(
                ["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
                check=True, capture_output=True, text=True,
            )
            commit_hash = result.stdout.strip()

            # write artifacts under workspace, NOT under repo
            artifact_root = workspace / "autoresearch-results"
            artifact_root.mkdir(parents=True, exist_ok=True)
            (artifact_root / "results.tsv").write_text(
                "\n".join([
                    "# metric_direction: lower",
                    "iteration\tcommit\tmetric\tdelta\tguard\tstatus\tdescription",
                    f"0\t{commit_hash}\t10\t0\t-\tbaseline\tbaseline score",
                    f"1\t{commit_hash}\t8\t-2\tpass\tkeep\timproved score",
                ]) + "\n",
                encoding="utf-8",
            )
            (artifact_root / "context.json").write_text(
                json.dumps(
                    {
                        "version": 2,
                        "active": False,
                        "session_mode": None,
                        "workspace_root": str(workspace.resolve()),
                        "artifact_root": str(artifact_root.resolve()),
                        "primary_repo": str(repo.resolve()),
                        "repo_targets": [
                            {
                                "path": str(repo.resolve()),
                                "scope": "src.py",
                                "role": "primary",
                            }
                        ],
                        "verify_cwd": "primary_repo",
                        "results_path": str((artifact_root / "results.tsv").resolve()),
                        "state_path": str((artifact_root / "state.json").resolve()),
                        "launch_path": None,
                        "runtime_path": None,
                        "log_path": None,
                        "updated_at": "2026-04-15T00:00:00Z",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (artifact_root / "lessons.md").write_text("# lessons\n", encoding="utf-8")

            # write git-local pointer: repo -> workspace
            pointer_dir = repo / ".git" / "codex-autoresearch"
            pointer_dir.mkdir(parents=True, exist_ok=True)
            (pointer_dir / "pointer.json").write_text(
                json.dumps({
                    "version": 2,
                    "active": True,
                    "workspace_root": str(workspace.resolve()),
                    "artifact_root": str(artifact_root.resolve()),
                    "primary_repo": str(repo.resolve()),
                    "updated_at": "2026-04-15T00:00:00Z",
                }) + "\n",
                encoding="utf-8",
            )

            completed = self.run_invariant_check(
                "exec",
                "--repo",
                str(repo),
                "--expect-improvement",
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("exec invariants: OK", completed.stdout)

    def test_exec_invariants_require_pointer_for_git_managed_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()

            subprocess.run(
                ["git", "init", "-b", "main", str(repo)],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "-C", str(repo), "config", "user.name", "test"],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "-C", str(repo), "config", "user.email", "t@t.com"],
                check=True,
                capture_output=True,
                text=True,
            )
            self.write_exec_repo(repo)

            completed = self.run_invariant_check("exec", "--repo", str(repo))

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("valid git-local pointer and canonical context", completed.stderr)


if __name__ == "__main__":
    unittest.main()
