from __future__ import annotations

import csv
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "autoresearch.py"
sys.path.insert(0, str(ROOT / "scripts"))
import autoresearch as autoresearch_runtime


class AutoresearchTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name) / "repo"
        (self.repo / "src").mkdir(parents=True)
        (self.repo / "src" / "value.txt").write_text("3\n", encoding="utf-8")
        (self.repo / "score.py").write_text(
            "from pathlib import Path\n"
            "print(int(Path('src/value.txt').read_text(encoding='utf-8').strip()))\n",
            encoding="utf-8",
        )
        (self.repo / "guard.py").write_text(
            "from pathlib import Path\n"
            "value = int(Path('src/value.txt').read_text(encoding='utf-8').strip())\n"
            "raise SystemExit(0 if value != 2 else 9)\n",
            encoding="utf-8",
        )
        self.git("init", "-b", "main")
        self.git("config", "user.name", "test")
        self.git("config", "user.email", "test@example.com")
        self.git("add", ".")
        self.git("commit", "-m", "baseline")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", str(self.repo), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=check,
        )

    def cli(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=self.repo,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=check,
        )

    def init(self, *extra: str, mode: str = "init") -> dict:
        completed = self.cli(
            mode,
            "--repo",
            str(self.repo),
            "--goal",
            "Reduce the value to zero",
            "--scope",
            "src",
            "--metric-name",
            "value",
            "--direction",
            "lower",
            "--verify",
            "python3 score.py",
            "--target",
            "0",
            *extra,
        )
        return json.loads(completed.stdout)

    def status(self) -> dict:
        return json.loads(self.cli("status", "--repo", str(self.repo)).stdout)

    def set_value(self, value: int) -> None:
        (self.repo / "src" / "value.txt").write_text(f"{value}\n", encoding="utf-8")

    def wait_for_status(self, expected: str, timeout: float = 10) -> dict:
        deadline = time.monotonic() + timeout
        last: dict | None = None
        while time.monotonic() < deadline:
            last = self.status()
            if last["status"] == expected:
                return last
            time.sleep(0.05)
        self.fail(f"Timed out waiting for {expected}; last status: {last}")

    def test_keep_reaches_target_and_commits(self) -> None:
        self.assertEqual("not_initialized", self.status()["status"])
        self.init()
        self.set_value(0)
        result = json.loads(
            self.cli(
                "finish",
                "--repo",
                str(self.repo),
                "--description",
                "set value to target",
            ).stdout
        )
        self.assertEqual("keep", result["outcome"])
        self.assertEqual("complete", result["status"])
        self.assertNotIn("continue", result["instruction"].lower())
        status = self.status()
        self.assertEqual(0, status["metric"]["current"])
        self.assertEqual(3, status["event_count"])
        self.assertEqual("0\n", (self.repo / "src" / "value.txt").read_text(encoding="utf-8"))
        self.assertIn("autoresearch: set value to target", self.git("log", "-1", "--format=%s").stdout)

    def test_non_improving_trial_is_reverted_and_recorded(self) -> None:
        self.init()
        self.set_value(4)
        result = json.loads(
            self.cli(
                "finish",
                "--repo",
                str(self.repo),
                "--description",
                "try a larger value",
            ).stdout
        )
        self.assertEqual("discard", result["outcome"])
        self.assertIn("continue", result["instruction"].lower())
        self.assertEqual(3, result["retained_metric"])
        self.assertEqual("3\n", (self.repo / "src" / "value.txt").read_text(encoding="utf-8"))
        subjects = self.git("log", "-2", "--format=%s").stdout
        self.assertIn('Revert "autoresearch: try a larger value"', subjects)
        self.assertEqual([], [line for line in self.git("status", "--short").stdout.splitlines() if "autoresearch-results" not in line])

    def test_history_table_and_tsv_render_discard_without_changing_events(self) -> None:
        self.init()
        active_report = json.loads(self.cli("report", "--repo", str(self.repo)).stdout)
        self.assertEqual("active", active_report["status"])
        self.assertTrue(Path(active_report["report"]).is_file())
        self.set_value(4)
        self.cli(
            "finish",
            "--repo",
            str(self.repo),
            "--description",
            "=1+1 try a larger value",
        )
        events_path = self.repo / "autoresearch-results" / "events.jsonl"
        events_before = events_path.read_bytes()

        table = self.cli("history", "--repo", str(self.repo)).stdout
        self.assertIn("Run:", table)
        self.assertIn("Metric: value  3 -> 3", table)
        self.assertIn("discard", table)
        self.assertIn("=1+1 try a larger value", table)

        tsv = self.cli(
            "history",
            "--repo",
            str(self.repo),
            "--format",
            "tsv",
        ).stdout
        rows = list(csv.DictReader(io.StringIO(tsv), delimiter="\t"))
        self.assertEqual(["baseline", "discard"], [row["event"] for row in rows])
        self.assertEqual("4", rows[1]["trial_metric"])
        self.assertEqual("3", rows[1]["retained_metric"])
        self.assertEqual("'=1+1 try a larger value", rows[1]["description"])
        self.assertTrue(rows[1]["trial_commit"])
        self.assertTrue(rows[1]["revert_commit"])
        self.assertEqual("not_run", rows[1]["guard"])
        self.assertEqual(events_before, events_path.read_bytes())

    def test_html_report_is_self_contained_escaped_and_read_only(self) -> None:
        self.init()
        self.set_value(4)
        self.cli(
            "finish",
            "--repo",
            str(self.repo),
            "--description",
            "discard <script>alert(1)</script>",
        )
        self.set_value(0)
        self.cli(
            "finish",
            "--repo",
            str(self.repo),
            "--description",
            "reach target & finish",
        )
        events_path = self.repo / "autoresearch-results" / "events.jsonl"
        events_before = events_path.read_bytes()

        receipt = json.loads(self.cli("report", "--repo", str(self.repo)).stdout)
        report_path = Path(receipt["report"])
        report = report_path.read_text(encoding="utf-8")
        self.assertEqual("complete", receipt["status"])
        self.assertEqual(2, receipt["iterations"])
        self.assertEqual(
            (self.repo / "autoresearch-results" / "report.html").resolve(),
            report_path.resolve(),
        )
        self.assertIn("<!doctype html>", report)
        self.assertIn('http-equiv="Content-Security-Policy"', report)
        self.assertIn("Metric trajectory", report)
        self.assertIn("Experiment history", report)
        self.assertIn('<svg class="metric-chart"', report)
        self.assertIn('href="logs/0000-baseline-verify.json"', report)
        self.assertIn('class="event-label discard"', report)
        self.assertIn('class="event-label keep"', report)
        self.assertIn("discard &lt;script&gt;alert(1)&lt;/script&gt;", report)
        self.assertNotIn("<script>alert(1)</script>", report)
        self.assertNotIn("<script", report)
        self.assertNotIn("http://", report)
        self.assertNotIn("https://", report)
        self.assertEqual(events_before, events_path.read_bytes())
        self.assertTrue(self.status()["repository"]["consistent"])

    def test_guard_failure_discards_improvement(self) -> None:
        self.init("--guard", "python3 guard.py")
        self.set_value(2)
        result = json.loads(
            self.cli(
                "finish",
                "--repo",
                str(self.repo),
                "--description",
                "guarded improvement",
            ).stdout
        )
        self.assertEqual("discard", result["outcome"])
        self.assertEqual("fail", self.status()["last_event"]["guard"])
        self.assertEqual("3\n", (self.repo / "src" / "value.txt").read_text(encoding="utf-8"))

    def test_metric_command_failure_records_error_and_reverts(self) -> None:
        (self.repo / "score.py").write_text(
            "from pathlib import Path\n"
            "value = int(Path('src/value.txt').read_text(encoding='utf-8').strip())\n"
            "print(value)\n"
            "raise SystemExit(7 if value == 2 else 0)\n",
            encoding="utf-8",
        )
        self.git("add", "score.py")
        self.git("commit", "-m", "conditional score")
        self.init()
        self.set_value(2)
        completed = self.cli(
            "finish",
            "--repo",
            str(self.repo),
            "--description",
            "trigger score failure",
            check=False,
        )
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("Metric command exited 7", completed.stderr)
        status = self.status()
        self.assertEqual("error", status["status"])
        self.assertIsNotNone(status["last_event"]["revert_commit"])
        self.assertEqual("3\n", (self.repo / "src" / "value.txt").read_text(encoding="utf-8"))

    def test_non_utf8_metric_output_is_preserved_in_diagnostic_log(self) -> None:
        (self.repo / "score.py").write_text(
            "from pathlib import Path\n"
            "import sys\n"
            "value = int(Path('src/value.txt').read_text(encoding='utf-8').strip())\n"
            "if value == 2:\n"
            "    sys.stdout.buffer.write(b'\\xff\\n')\n"
            "else:\n"
            "    print(value)\n",
            encoding="utf-8",
        )
        self.git("add", "score.py")
        self.git("commit", "-m", "non-utf8 score")
        self.init()
        self.set_value(2)
        completed = self.cli(
            "finish",
            "--repo",
            str(self.repo),
            "--description",
            "emit invalid metric bytes",
            check=False,
        )
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("Raw output is base64-encoded", completed.stderr)
        status = self.status()
        self.assertEqual("error", status["status"])
        log_path = self.repo / "autoresearch-results" / status["last_event"]["log"]
        diagnostic = json.loads(log_path.read_text(encoding="utf-8"))
        self.assertIsNone(diagnostic["stdout"])
        self.assertEqual("/wo=", diagnostic["stdout_base64"])
        self.assertTrue(diagnostic["encoding_errors"])

    def test_out_of_scope_change_fails_without_commit(self) -> None:
        self.init()
        baseline = self.git("rev-parse", "HEAD").stdout.strip()
        (self.repo / "score.py").write_text("print(0)\n", encoding="utf-8")
        completed = self.cli(
            "finish",
            "--repo",
            str(self.repo),
            "--description",
            "edit verifier",
            check=False,
        )
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("Out-of-scope", completed.stderr)
        self.assertEqual(baseline, self.git("rev-parse", "HEAD").stdout.strip())

    def test_init_rejects_dirty_repo_and_glob_scope(self) -> None:
        self.set_value(2)
        dirty = self.cli(
            "init",
            "--repo",
            str(self.repo),
            "--goal",
            "goal",
            "--scope",
            "src",
            "--metric-name",
            "value",
            "--direction",
            "lower",
            "--verify",
            "python3 score.py",
            "--target",
            "0",
            check=False,
        )
        self.assertIn("uncommitted changes", dirty.stderr)
        self.git("restore", "src/value.txt")
        glob = self.cli(
            "init",
            "--repo",
            str(self.repo),
            "--goal",
            "goal",
            "--scope",
            "src/**/*.py",
            "--metric-name",
            "value",
            "--direction",
            "lower",
            "--verify",
            "python3 score.py",
            "--target",
            "0",
            check=False,
        )
        self.assertIn("uses a glob", glob.stderr)

    def test_foreground_config_omits_background_only_options(self) -> None:
        help_text = self.cli("init", "--help").stdout
        self.assertNotIn("--codex-bin", help_text)
        self.assertNotIn("--execution-policy", help_text)
        self.assertIn("--codex-bin", self.cli("launch", "--help").stdout)
        self.init()
        run = json.loads(
            (self.repo / "autoresearch-results" / "run.json").read_text(encoding="utf-8")
        )
        self.assertIsNone(run["background"])

    def test_baseline_side_effect_stops_before_guard_and_is_diagnostic(self) -> None:
        (self.repo / "score.py").write_text(
            "from pathlib import Path\n"
            "Path('src/generated.txt').write_text('side effect\\n', encoding='utf-8')\n"
            "print(3)\n",
            encoding="utf-8",
        )
        (self.repo / "guard.py").write_text(
            "from pathlib import Path\n"
            "Path('guard-ran.txt').write_text('ran\\n', encoding='utf-8')\n",
            encoding="utf-8",
        )
        self.git("add", "score.py", "guard.py")
        self.git("commit", "-m", "side-effect baseline")
        completed = self.cli(
            "init",
            "--repo",
            str(self.repo),
            "--goal",
            "goal",
            "--scope",
            "src",
            "--metric-name",
            "value",
            "--direction",
            "lower",
            "--verify",
            "python3 score.py",
            "--target",
            "0",
            "--guard",
            "python3 guard.py",
            check=False,
        )
        self.assertIn("Baseline metric command modified", completed.stderr)
        self.assertFalse((self.repo / "guard-ran.txt").exists())
        diagnostic_path = self.repo / "autoresearch-results" / "init-error.json"
        diagnostic = json.loads(diagnostic_path.read_text(encoding="utf-8"))
        self.assertIn("Baseline metric command modified", diagnostic["message"])
        self.assertIn("AutoresearchError", diagnostic["traceback"])
        failed_status = self.status()
        self.assertEqual("initialization_failed", failed_status["status"])
        self.assertEqual(diagnostic_path.resolve(), Path(failed_status["diagnostic"]).resolve())
        archived = json.loads(self.cli("archive", "--repo", str(self.repo)).stdout)
        self.assertTrue(Path(archived["destination"], "init-error.json").is_file())

    def test_json_metric_requires_explicit_key(self) -> None:
        (self.repo / "score.py").write_text(
            "from pathlib import Path\n"
            "import json\n"
            "value = int(Path('src/value.txt').read_text(encoding='utf-8').strip())\n"
            "print(json.dumps({'value': value, 'other': 99}))\n",
            encoding="utf-8",
        )
        self.git("add", "score.py")
        self.git("commit", "-m", "json score")
        result = self.init("--metric-key", "value")
        self.assertEqual(3, result["baseline"])

    def test_corrupt_event_log_fails_instead_of_reconstructing(self) -> None:
        self.init()
        events = self.repo / "autoresearch-results" / "events.jsonl"
        events.write_text(events.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        completed = self.cli("status", "--repo", str(self.repo), check=False)
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("Blank event record", completed.stderr)

    def test_unknown_run_field_fails(self) -> None:
        self.init()
        run_path = self.repo / "autoresearch-results" / "run.json"
        run = json.loads(run_path.read_text(encoding="utf-8"))
        run["unexpected"] = True
        run_path.write_text(json.dumps(run), encoding="utf-8")
        completed = self.cli("status", "--repo", str(self.repo), check=False)
        self.assertIn("unknown unexpected", completed.stderr)

    def test_tampered_keep_semantics_fail_validation(self) -> None:
        self.init()
        self.set_value(0)
        self.cli(
            "finish",
            "--repo",
            str(self.repo),
            "--description",
            "reach target",
        )
        events_path = self.repo / "autoresearch-results" / "events.jsonl"
        events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]
        events[1]["trial_metric"] = 9
        events_path.write_text(
            "".join(json.dumps(event, sort_keys=True) + "\n" for event in events),
            encoding="utf-8",
        )
        completed = self.cli("status", "--repo", str(self.repo), check=False)
        self.assertIn("keeps a metric that did not improve", completed.stderr)

    def test_tampered_terminal_and_baseline_semantics_fail_validation(self) -> None:
        self.init("--guard", "python3 -c 'raise SystemExit(0)'")
        events_path = self.repo / "autoresearch-results" / "events.jsonl"
        events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]
        events[0]["guard_log"] = None
        events_path.write_text(
            "".join(json.dumps(event, sort_keys=True) + "\n" for event in events),
            encoding="utf-8",
        )
        missing_guard = self.cli("status", "--repo", str(self.repo), check=False)
        self.assertIn("missing its configured guard log", missing_guard.stderr)

        events[0]["guard_log"] = "logs/0000-baseline-guard.json"
        events.append(
            {
                "schema_version": 1,
                "run_id": events[0]["run_id"],
                "seq": 1,
                "time": "2026-01-01T00:00:00Z",
                "event": "complete",
                "reason": "forged completion",
                "head": events[0]["head"],
                "metric": 3,
            }
        )
        events_path.write_text(
            "".join(json.dumps(event, sort_keys=True) + "\n" for event in events),
            encoding="utf-8",
        )
        forged_complete = self.cli("status", "--repo", str(self.repo), check=False)
        self.assertIn("does not satisfy the configured target", forged_complete.stderr)

    def test_tracked_or_unknown_artifacts_block_initialization(self) -> None:
        artifact_root = self.repo / "autoresearch-results"
        artifact_root.mkdir()
        (artifact_root / "unexpected.json").write_text("{}\n", encoding="utf-8")
        unknown = self.cli(
            "init",
            "--repo",
            str(self.repo),
            "--goal",
            "goal",
            "--scope",
            "src",
            "--metric-name",
            "value",
            "--direction",
            "lower",
            "--verify",
            "python3 score.py",
            "--target",
            "0",
            check=False,
        )
        self.assertIn("unexpected.json", unknown.stderr)
        self.git("add", "-f", "autoresearch-results/unexpected.json")
        self.git("commit", "-m", "track bad artifact")
        tracked = self.cli(
            "init",
            "--repo",
            str(self.repo),
            "--goal",
            "goal",
            "--scope",
            "src",
            "--metric-name",
            "value",
            "--direction",
            "lower",
            "--verify",
            "python3 score.py",
            "--target",
            "0",
            check=False,
        )
        self.assertIn("must remain untracked", tracked.stderr)

    def test_unrepresentable_metric_precision_fails_before_running_commands(self) -> None:
        completed = self.cli(
            "init",
            "--repo",
            str(self.repo),
            "--goal",
            "goal",
            "--scope",
            "src",
            "--metric-name",
            "value",
            "--direction",
            "lower",
            "--verify",
            "python3 score.py",
            "--target",
            "0.1234567890123456789",
            check=False,
        )
        self.assertIn("would lose precision", completed.stderr)
        self.assertFalse((self.repo / "autoresearch-results").exists())

    def test_block_resume_and_archive_are_explicit(self) -> None:
        self.init()
        blocked = json.loads(
            self.cli(
                "block",
                "--repo",
                str(self.repo),
                "--reason",
                "missing external fixture",
            ).stdout
        )
        self.assertEqual("blocked", blocked["status"])
        resumed = json.loads(
            self.cli(
                "resume",
                "--repo",
                str(self.repo),
                "--note",
                "fixture is now available",
            ).stdout
        )
        self.assertEqual("active", resumed["status"])
        history = self.cli("history", "--repo", str(self.repo)).stdout
        self.assertIn("blocked", history)
        self.assertIn("resumed", history)
        archived = json.loads(self.cli("archive", "--repo", str(self.repo)).stdout)
        self.assertEqual("archived", archived["status"])
        self.assertFalse((self.repo / "autoresearch-results" / "run.json").exists())
        self.assertTrue(Path(archived["destination"]).is_dir())
        self.assertEqual("active", self.init()["status"])

    def test_iteration_limit_stops_without_claiming_completion(self) -> None:
        self.init("--max-iterations", "1")
        self.set_value(2)
        result = json.loads(
            self.cli(
                "finish",
                "--repo",
                str(self.repo),
                "--description",
                "one bounded improvement",
            ).stdout
        )
        self.assertEqual("stopped", result["status"])
        self.assertNotIn("continue", result["instruction"].lower())
        self.assertEqual(2, self.status()["metric"]["current"])
        self.assertIn("stopped", self.cli("history", "--repo", str(self.repo)).stdout)

    def test_resume_defaults_to_existing_experiment_and_rejects_empty_note(self) -> None:
        self.init()
        self.cli("block", "--repo", str(self.repo), "--reason", "test data unavailable")
        invalid = self.cli("resume", "--repo", str(self.repo), "--note", " ", check=False)
        self.assertNotEqual(0, invalid.returncode)
        self.assertEqual("blocked", self.status()["status"])
        resumed = json.loads(self.cli("resume", "--repo", str(self.repo)).stdout)
        self.assertEqual("active", resumed["status"])
        self.assertTrue(resumed["note"])
        self.assertEqual(resumed["note"], self.status()["last_event"]["note"])

    def test_background_controller_runs_multiple_real_helper_iterations(self) -> None:
        fake = Path(self.temp.name) / "fake-codex"
        fake.write_text(
            "#!/usr/bin/env python3\n"
            "import json, pathlib, subprocess, sys\n"
            "args = sys.argv[1:]\n"
            "repo = pathlib.Path(args[args.index('-C') + 1])\n"
            "sys.stdin.read()\n"
            f"script = {str(SCRIPT)!r}\n"
            "status = json.loads(subprocess.check_output([sys.executable, script, 'status', '--repo', str(repo)], text=True))\n"
            "value = int(status['metric']['current'])\n"
            "next_value = 2 if value == 3 else 0\n"
            "(repo / 'src' / 'value.txt').write_text(f'{next_value}\\n', encoding='utf-8')\n"
            "subprocess.check_call([sys.executable, script, 'finish', '--repo', str(repo), '--description', f'reduce value to {next_value}'])\n",
            encoding="utf-8",
        )
        fake.chmod(0o755)
        launched = self.init("--codex-bin", str(fake), mode="launch")
        self.assertIn(launched["status"], {"running", "complete"})
        status = self.wait_for_status("complete")
        self.assertEqual(2, status["iterations"])
        runtime_log = Path(status["runtime_log"]).read_text(encoding="utf-8")
        self.assertEqual(2, runtime_log.count('"event":"worker_started"'))
        self.assertIn('"--ephemeral"', runtime_log)

    def test_background_worker_without_event_fails_fast(self) -> None:
        fake = Path(self.temp.name) / "fake-codex-no-event"
        fake.write_text(
            "#!/usr/bin/env python3\n"
            "import sys\n"
            "sys.stdin.read()\n",
            encoding="utf-8",
        )
        fake.chmod(0o755)
        self.init("--codex-bin", str(fake), mode="launch")
        status = self.wait_for_status("error")
        self.assertIn("one-iteration contract", status["last_event"]["reason"])

    def test_background_launch_surfaces_missing_codex_binary(self) -> None:
        completed = self.cli(
            "launch",
            "--repo",
            str(self.repo),
            "--goal",
            "Reduce the value to zero",
            "--scope",
            "src",
            "--metric-name",
            "value",
            "--direction",
            "lower",
            "--verify",
            "python3 score.py",
            "--target",
            "0",
            "--codex-bin",
            str(Path(self.temp.name) / "missing-codex"),
            check=False,
        )
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("executable was not found", completed.stderr)
        self.assertFalse((self.repo / "autoresearch-results").exists())

    def test_unresolved_trial_error_cannot_resume(self) -> None:
        (self.repo / "score.py").write_text(
            "from pathlib import Path\n"
            "value = int(Path('src/value.txt').read_text(encoding='utf-8').strip())\n"
            "if value == 2:\n"
            "    Path('src/generated.txt').write_text('side effect\\n', encoding='utf-8')\n"
            "print(value)\n",
            encoding="utf-8",
        )
        self.git("add", "score.py")
        self.git("commit", "-m", "side-effect score")
        self.init()
        self.set_value(2)
        failed = self.cli(
            "finish",
            "--repo",
            str(self.repo),
            "--description",
            "trigger side effect",
            check=False,
        )
        self.assertIn("Metric command modified", failed.stderr)
        resumed = self.cli(
            "resume",
            "--repo",
            str(self.repo),
            "--note",
            "try again",
            check=False,
        )
        self.assertIn("was not rolled back", resumed.stderr)

    def test_metric_command_cannot_hide_git_head_changes(self) -> None:
        (self.repo / "score.py").write_text(
            "from pathlib import Path\n"
            "import subprocess\n"
            "value = int(Path('src/value.txt').read_text(encoding='utf-8').strip())\n"
            "if value == 2:\n"
            "    subprocess.check_call(['git', 'commit', '--allow-empty', '-m', 'metric side effect'])\n"
            "print(value)\n",
            encoding="utf-8",
        )
        self.git("add", "score.py")
        self.git("commit", "-m", "git-mutating metric")
        self.init()
        self.set_value(2)
        failed = self.cli(
            "finish",
            "--repo",
            str(self.repo),
            "--description",
            "trigger hidden commit",
            check=False,
        )
        self.assertIn("Metric command modified the repository", failed.stderr)
        self.assertIn("moved HEAD", failed.stderr)
        status = self.status()
        self.assertEqual("error", status["status"])
        self.assertIn("automatic rollback was not attempted", status["last_event"]["reason"])
        self.assertEqual(status["last_event"]["trial_commit"], status["head"])
        self.assertFalse(status["repository"]["consistent"])
        self.assertNotEqual(
            status["repository"]["expected_head"],
            status["repository"]["current_head"],
        )

    def test_background_stop_terminates_sleeping_worker(self) -> None:
        fake = Path(self.temp.name) / "fake-codex-sleep"
        ready = Path(self.temp.name) / "worker-ready"
        fake.write_text(
            "#!/usr/bin/env python3\n"
            "import pathlib, signal, sys, time\n"
            "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
            f"pathlib.Path({str(ready)!r}).write_text('ready', encoding='utf-8')\n"
            "sys.stdin.read()\n"
            "time.sleep(30)\n",
            encoding="utf-8",
        )
        fake.chmod(0o755)
        self.init("--codex-bin", str(fake), mode="launch")
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            status = self.status()
            if status["runtime"]["child_pid"]:
                if ready.exists():
                    break
            time.sleep(0.05)
        else:
            self.fail("background worker never started")
        stopped = json.loads(self.cli("stop", "--repo", str(self.repo)).stdout)
        self.assertEqual("stopped", stopped["status"])
        self.assertEqual("stopped", self.status()["status"])

    def test_controller_error_terminates_active_worker(self) -> None:
        fake = Path(self.temp.name) / "fake-codex-controller-error"
        ready = Path(self.temp.name) / "controller-error-worker-ready"
        fake.write_text(
            "#!/usr/bin/env python3\n"
            "import pathlib, signal, sys, time\n"
            "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
            f"pathlib.Path({str(ready)!r}).write_text('ready', encoding='utf-8')\n"
            "sys.stdin.read()\n"
            "time.sleep(30)\n",
            encoding="utf-8",
        )
        fake.chmod(0o755)
        self.init("--codex-bin", str(fake), mode="launch")
        deadline = time.monotonic() + 5
        child_pid = None
        while time.monotonic() < deadline:
            status = self.status()
            child_pid = status["runtime"]["child_pid"]
            if child_pid and ready.exists():
                break
            time.sleep(0.05)
        else:
            self.fail("background worker never started")
        stop_request = self.repo / "autoresearch-results" / "stop-request.json"
        stop_request.write_text("{", encoding="utf-8")
        status = self.wait_for_status("error", timeout=15)
        self.assertFalse(status["runtime"]["child_alive"])
        runtime_log = Path(status["runtime_log"]).read_text(encoding="utf-8")
        self.assertIn("worker_cleanup_after_controller_error", runtime_log)
        self.assertIn("Invalid JSON", status["last_event"]["reason"])

    def test_controller_start_failure_terminates_before_state_diagnostics(self) -> None:
        self.init()
        paths, run, _, _ = autoresearch_runtime.load_context(self.repo)
        paths.events.write_text("{", encoding="utf-8")
        process_kwargs: dict[str, object] = {}
        if os.name == "nt":
            process_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            process_kwargs["start_new_session"] = True
        process = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            **process_kwargs,
        )
        try:
            with self.assertRaises(autoresearch_runtime.AutoresearchError) as raised:
                autoresearch_runtime.fail_controller_start(
                    paths,
                    run,
                    process,
                    "2026-01-01T00:00:00Z",
                    "startup validation failed",
                )
            process.wait(timeout=5)
            self.assertIn("event error record failed", str(raised.exception))
            runtime = json.loads(paths.runtime.read_text(encoding="utf-8"))
            self.assertEqual("error", runtime["state"])
            self.assertFalse(autoresearch_runtime.process_alive(process.pid))
        finally:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)

    def test_controller_spawn_failure_records_terminal_error(self) -> None:
        self.init()
        run_path = self.repo / "autoresearch-results" / "run.json"
        run = json.loads(run_path.read_text(encoding="utf-8"))
        run["mode"] = "background"
        run["background"] = {
            "execution_policy": "danger-full-access",
            "codex_bin": sys.executable,
            "model": None,
        }
        run_path.write_text(json.dumps(run), encoding="utf-8")
        real_popen = subprocess.Popen

        def fail_controller_only(command: object, *args: object, **kwargs: object) -> subprocess.Popen:
            if (
                isinstance(command, list)
                and len(command) >= 3
                and command[0] == sys.executable
                and command[1] == str(SCRIPT)
                and command[2] == "_controller"
            ):
                raise OSError("process limit reached")
            return real_popen(command, *args, **kwargs)

        with mock.patch.object(
            autoresearch_runtime.subprocess,
            "Popen",
            side_effect=fail_controller_only,
        ):
            with self.assertRaises(autoresearch_runtime.AutoresearchError) as raised:
                autoresearch_runtime.spawn_controller(self.repo)
        self.assertIn("process limit reached", str(raised.exception))
        status = self.status()
        self.assertEqual("error", status["status"])
        self.assertIn("Failed to start background controller", status["last_event"]["reason"])
        runtime_log = Path(status["runtime_log"]).read_text(encoding="utf-8")
        self.assertIn("controller_spawn_failed", runtime_log)

    def test_stop_accepts_run_that_completes_during_stop_race(self) -> None:
        self.init()
        run_path = self.repo / "autoresearch-results" / "run.json"
        run = json.loads(run_path.read_text(encoding="utf-8"))
        run["mode"] = "background"
        run["background"] = {
            "execution_policy": "danger-full-access",
            "codex_bin": sys.executable,
            "model": None,
        }
        run_path.write_text(json.dumps(run), encoding="utf-8")
        controller = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        runtime = {
            "run_id": run["run_id"],
            "controller_pid": controller.pid,
            "child_pid": None,
            "state": "running",
            "started_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        }
        (self.repo / "autoresearch-results" / "runtime.json").write_text(
            json.dumps(runtime), encoding="utf-8"
        )
        thread_errors: list[BaseException] = []

        def complete_after_stop_request() -> None:
            try:
                request = self.repo / "autoresearch-results" / "stop-request.json"
                deadline = time.monotonic() + 5
                while not request.exists() and time.monotonic() < deadline:
                    time.sleep(0.01)
                if not request.exists():
                    raise RuntimeError("stop request was not created")
                self.set_value(0)
                self.cli(
                    "finish",
                    "--repo",
                    str(self.repo),
                    "--description",
                    "complete during stop",
                )
                request.unlink()
                controller.terminate()
                controller.wait(timeout=5)
            except BaseException as exc:
                thread_errors.append(exc)

        helper = threading.Thread(target=complete_after_stop_request)
        helper.start()
        try:
            result = json.loads(self.cli("stop", "--repo", str(self.repo)).stdout)
        finally:
            helper.join(timeout=10)
            if controller.poll() is None:
                controller.kill()
            controller.wait(timeout=5)
        self.assertFalse(helper.is_alive())
        self.assertEqual([], thread_errors)
        self.assertEqual("complete", result["status"])
        self.assertEqual("complete", self.status()["status"])

    def test_live_orphaned_worker_blocks_control_transitions(self) -> None:
        self.init()
        run_path = self.repo / "autoresearch-results" / "run.json"
        run = json.loads(run_path.read_text(encoding="utf-8"))
        run["mode"] = "background"
        run["background"] = {
            "execution_policy": "danger-full-access",
            "codex_bin": sys.executable,
            "model": None,
        }
        run_path.write_text(json.dumps(run), encoding="utf-8")
        child = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            start_new_session=True,
        )
        try:
            runtime = {
                "run_id": run["run_id"],
                "controller_pid": 2_147_483_647,
                "child_pid": child.pid,
                "state": "running",
                "started_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
            }
            (self.repo / "autoresearch-results" / "runtime.json").write_text(
                json.dumps(runtime), encoding="utf-8"
            )
            status = self.status()
            self.assertEqual("orphaned", status["runtime"]["state"])
            self.assertFalse(status["runtime"]["controller_alive"])
            self.assertTrue(status["runtime"]["child_alive"])
            for command in (
                ("stop", "--repo", str(self.repo)),
                ("resume", "--repo", str(self.repo), "--note", "retry"),
                ("archive", "--repo", str(self.repo)),
            ):
                completed = self.cli(*command, check=False)
                self.assertNotEqual(0, completed.returncode)
                self.assertIn(str(child.pid), completed.stderr)
        finally:
            child.kill()
            child.wait(timeout=5)
        orphan_resume = self.cli(
            "resume",
            "--repo",
            str(self.repo),
            "--note",
            "retry",
            check=False,
        )
        self.assertIn("Run stop to close the orphaned state", orphan_resume.stderr)
        self.assertEqual("active", self.status()["status"])
        stopped = json.loads(self.cli("stop", "--repo", str(self.repo)).stdout)
        self.assertEqual("stopped", stopped["status"])


if __name__ == "__main__":
    unittest.main()
