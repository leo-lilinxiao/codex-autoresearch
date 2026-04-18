from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from .base import AutoresearchScriptsTestBase


class AutoresearchHooksCtlTest(AutoresearchScriptsTestBase):
    maxDiff = None

    def hook_env(self, home: Path) -> dict[str, str]:
        env = dict(os.environ)
        env["HOME"] = str(home)
        env["CODEX_HOME"] = str(home / ".codex")
        return env

    def installed_hook_path(self, home: Path, name: str) -> Path:
        return home / ".codex" / "autoresearch-hooks" / name

    def repo_hook_context_path(self, repo: Path) -> Path:
        return self.managed_context_path(repo)

    def run_installed_hook(
        self,
        hook_path: Path,
        *,
        cwd: Path,
        payload: dict[str, object],
        env: dict[str, str],
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(hook_path)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            cwd=cwd,
            env=env,
        )

    def write_transcript_marker(self, path: Path, text: str = "$codex-autoresearch\nResume the current run.\n") -> None:
        payload = {
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": text,
                    }
                ],
            },
        }
        path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    def test_install_merges_existing_config_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            codex_home = home / ".codex"
            codex_home.mkdir(parents=True)
            env = self.hook_env(home)

            (codex_home / "config.toml").write_text(
                "[features]\nother_feature = true\n",
                encoding="utf-8",
            )
            (codex_home / "hooks.json").write_text(
                json.dumps(
                    {
                        "hooks": {
                            "UserPromptSubmit": [
                                {
                                    "hooks": [
                                        {
                                            "type": "command",
                                            "command": "python3 /tmp/existing.py",
                                            "statusMessage": "existing",
                                        }
                                    ]
                                }
                            ]
                        }
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            installed = self.run_script("autoresearch_hooks_ctl.py", "install", env=env)
            self.assertTrue(installed["ready_for_future_sessions"])
            self.assertTrue(installed["feature_enabled"])
            self.assertTrue(installed["managed_scripts_present"])
            self.assertTrue(self.installed_hook_path(home, "autoresearch_supervisor_status.py").exists())

            hooks_payload = json.loads((codex_home / "hooks.json").read_text(encoding="utf-8"))
            self.assertIn("UserPromptSubmit", hooks_payload["hooks"])
            self.assertEqual(len(hooks_payload["hooks"]["SessionStart"]), 1)
            self.assertEqual(len(hooks_payload["hooks"]["Stop"]), 1)
            session_command = hooks_payload["hooks"]["SessionStart"][0]["hooks"][0]["command"]
            stop_command = hooks_payload["hooks"]["Stop"][0]["hooks"][0]["command"]
            self.assertIn(str(self.installed_hook_path(home, "session_start.py")), session_command)
            self.assertIn(str(self.installed_hook_path(home, "stop.py")), stop_command)

            reinstalled = self.run_script("autoresearch_hooks_ctl.py", "install", env=env)
            self.assertTrue(reinstalled["ready_for_future_sessions"])
            hooks_payload = json.loads((codex_home / "hooks.json").read_text(encoding="utf-8"))
            self.assertEqual(len(hooks_payload["hooks"]["SessionStart"]), 1)
            self.assertEqual(len(hooks_payload["hooks"]["Stop"]), 1)

            removed = self.run_script("autoresearch_hooks_ctl.py", "uninstall", env=env)
            self.assertEqual(removed["managed_groups_removed"], 2)
            hooks_payload = json.loads((codex_home / "hooks.json").read_text(encoding="utf-8"))
            self.assertNotIn("SessionStart", hooks_payload["hooks"])
            self.assertNotIn("Stop", hooks_payload["hooks"])
            self.assertIn("UserPromptSubmit", hooks_payload["hooks"])
            config_text = (codex_home / "config.toml").read_text(encoding="utf-8")
            self.assertIn("codex_hooks = true", config_text)

    def test_repo_flag_is_accepted_and_ignored_for_all_subcommands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            repo = root / "repo"
            repo.mkdir(parents=True)
            env = self.hook_env(home)

            installed = self.run_script(
                "autoresearch_hooks_ctl.py",
                "install",
                "--repo",
                str(repo),
                env=env,
            )
            self.assertTrue(installed["ready_for_future_sessions"])

            status = self.run_script(
                "autoresearch_hooks_ctl.py",
                "status",
                "--repo",
                str(repo),
                env=env,
            )
            self.assertTrue(status["ready_for_future_sessions"])

            removed = self.run_script(
                "autoresearch_hooks_ctl.py",
                "uninstall",
                "--repo",
                str(repo),
                env=env,
            )
            self.assertIn("managed_groups_removed", removed)

    def test_uninstall_turns_feature_off_when_installer_enabled_it_and_no_other_hooks_remain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            env = self.hook_env(home)

            self.run_script("autoresearch_hooks_ctl.py", "install", env=env)
            removed = self.run_script("autoresearch_hooks_ctl.py", "uninstall", env=env)
            self.assertFalse(removed["ready_for_future_sessions"])

            config_text = (home / ".codex" / "config.toml").read_text(encoding="utf-8")
            self.assertIn("codex_hooks = false", config_text)
            self.assertFalse(self.installed_hook_path(home, "autoresearch_hook_common.py").exists())
            self.assertFalse(self.installed_hook_path(home, "autoresearch_hook_context.py").exists())
            self.assertFalse(self.installed_hook_path(home, "session_start.py").exists())
            self.assertFalse(self.installed_hook_path(home, "stop.py").exists())
            self.assertFalse(self.installed_hook_path(home, "autoresearch_supervisor_status.py").exists())

    def test_session_start_hook_requires_an_autoresearch_session_signal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            env = self.hook_env(home)
            self.run_script("autoresearch_hooks_ctl.py", "install", env=env)

            empty_repo = root / "empty-repo"
            empty_repo.mkdir()
            hook_path = self.installed_hook_path(home, "session_start.py")
            completed = self.run_installed_hook(
                hook_path,
                cwd=empty_repo,
                payload={"cwd": str(empty_repo), "source": "startup"},
                env=env,
            )
            completed.check_returncode()
            self.assertEqual(completed.stdout, "")

            repo = root / "active-repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            self.run_script(
                "autoresearch_init_run.py",
                "--repo",
                str(repo),
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
                "pytest -q",
                "--baseline-metric",
                "10",
                "--baseline-commit",
                "base111",
                "--baseline-description",
                "baseline failures",
                env=env,
            )
            completed = self.run_installed_hook(
                hook_path,
                cwd=repo,
                payload={"cwd": str(repo), "source": "resume"},
                env=env,
            )
            completed.check_returncode()
            self.assertEqual(completed.stdout, "")

            transcript_path = root / "resume-rollout.jsonl"
            self.write_transcript_marker(transcript_path)
            completed = self.run_installed_hook(
                hook_path,
                cwd=repo,
                payload={
                    "cwd": str(repo),
                    "source": "resume",
                    "transcript_path": str(transcript_path),
                },
                env=env,
            )
            completed.check_returncode()
            payload = json.loads(completed.stdout)
            context = payload["hookSpecificOutput"]["additionalContext"]
            self.assertIn("Record every completed experiment before starting the next one.", context)
            self.assertIn("Do not rerun the wizard after launch is already confirmed.", context)

    def test_session_start_hook_respects_background_opt_in_and_custom_artifact_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            env = self.hook_env(home)
            self.run_script("autoresearch_hooks_ctl.py", "install", env=env)
            hook_path = self.installed_hook_path(home, "session_start.py")

            repo = root / "background-repo"
            artifacts = repo / "artifacts"
            artifacts.mkdir(parents=True)
            custom_launch = artifacts / "launch.json"
            custom_launch.write_text(json.dumps({"config": {"goal": "x"}}), encoding="utf-8")

            hook_env = dict(env)
            hook_env["AUTORESEARCH_HOOK_ACTIVE"] = "1"
            hook_env["AUTORESEARCH_HOOK_LAUNCH_PATH"] = str(custom_launch)
            hook_env["AUTORESEARCH_HOOK_RESULTS_PATH"] = str(artifacts / "custom-results.tsv")
            hook_env["AUTORESEARCH_HOOK_STATE_PATH"] = str(artifacts / "custom-state.json")
            hook_env["AUTORESEARCH_HOOK_RUNTIME_PATH"] = str(artifacts / "custom-runtime.json")

            completed = self.run_installed_hook(
                hook_path,
                cwd=repo,
                payload={"cwd": str(repo), "source": "startup"},
                env=hook_env,
            )
            completed.check_returncode()
            payload = json.loads(completed.stdout)
            context = payload["hookSpecificOutput"]["additionalContext"]
            self.assertIn("baseline first", context.lower())

    def test_foreground_pointer_file_restores_custom_paths_for_future_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            env = self.hook_env(home)
            self.run_script("autoresearch_hooks_ctl.py", "install", env=env)
            hook_path = self.installed_hook_path(home, "session_start.py")

            repo = root / "foreground-repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            artifacts = repo / "artifacts"
            artifacts.mkdir(parents=True)
            custom_results = artifacts / "custom-results.tsv"
            custom_state = artifacts / "custom-state.json"

            self.run_script(
                "autoresearch_init_run.py",
                "--repo",
                str(repo),
                "--results-path",
                str(custom_results),
                "--state-path",
                str(custom_state),
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
                "pytest -q",
                "--baseline-metric",
                "10",
                "--baseline-commit",
                "base111",
                "--baseline-description",
                "baseline failures",
                env=env,
            )

            pointer_payload = json.loads(
                self.repo_hook_context_path(repo).read_text(encoding="utf-8")
            )
            self.assertEqual(pointer_payload["version"], 2)
            self.assertTrue(pointer_payload["active"])
            self.assertEqual(pointer_payload["session_mode"], "foreground")
            self.assertEqual(Path(pointer_payload["results_path"]).resolve(), custom_results.resolve())
            self.assertEqual(Path(pointer_payload["state_path"]).resolve(), custom_state.resolve())
            self.assertIsNone(pointer_payload["launch_path"])
            self.assertIsNone(pointer_payload["runtime_path"])

            transcript_path = root / "foreground-rollout.jsonl"
            self.write_transcript_marker(transcript_path)
            completed = self.run_installed_hook(
                hook_path,
                cwd=repo,
                payload={
                    "cwd": str(repo),
                    "source": "resume",
                    "transcript_path": str(transcript_path),
                },
                env=env,
            )
            completed.check_returncode()
            payload = json.loads(completed.stdout)
            context = payload["hookSpecificOutput"]["additionalContext"]
            self.assertIn("Record every completed experiment before starting the next one.", context)

    def test_foreground_terminal_stop_marks_pointer_inactive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            env = self.hook_env(home)
            self.run_script("autoresearch_hooks_ctl.py", "install", env=env)
            stop_hook = self.installed_hook_path(home, "stop.py")
            session_hook = self.installed_hook_path(home, "session_start.py")

            repo = root / "terminal-foreground"
            repo.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            artifacts = repo / "artifacts"
            artifacts.mkdir(parents=True)
            custom_results = artifacts / "custom-results.tsv"
            custom_state = artifacts / "custom-state.json"

            self.run_script(
                "autoresearch_init_run.py",
                "--repo",
                str(repo),
                "--results-path",
                str(custom_results),
                "--state-path",
                str(custom_state),
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
                "pytest -q",
                "--stop-condition",
                "stop when metric reaches 0",
                "--baseline-metric",
                "0",
                "--baseline-commit",
                "base000",
                "--baseline-description",
                "baseline failures",
                env=env,
            )

            transcript_path = root / "foreground-terminal.jsonl"
            self.write_transcript_marker(transcript_path)
            completed = self.run_installed_hook(
                stop_hook,
                cwd=repo,
                payload={
                    "cwd": str(repo),
                    "stop_hook_active": False,
                    "transcript_path": str(transcript_path),
                },
                env=env,
            )
            completed.check_returncode()
            self.assertEqual(completed.stdout, "")

            pointer_payload = json.loads(
                self.repo_hook_context_path(repo).read_text(encoding="utf-8")
            )
            self.assertFalse(pointer_payload["active"])

            completed = self.run_installed_hook(
                session_hook,
                cwd=repo,
                payload={
                    "cwd": str(repo),
                    "source": "resume",
                    "transcript_path": str(transcript_path),
                },
                env=env,
            )
            completed.check_returncode()
            self.assertEqual(completed.stdout, "")

    def test_foreground_symbolic_stop_condition_does_not_block_stop_hook(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            env = self.hook_env(home)
            self.run_script("autoresearch_hooks_ctl.py", "install", env=env)
            stop_hook = self.installed_hook_path(home, "stop.py")

            repo = root / "symbolic-terminal-foreground"
            repo.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            results_path = self.managed_results_path(repo)
            state_path = self.managed_state_path(repo)

            self.run_script(
                "autoresearch_init_run.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
                "--mode",
                "fix",
                "--session-mode",
                "foreground",
                "--goal",
                "Fix all errors",
                "--scope",
                "src/**/*.py",
                "--metric-name",
                "failure count",
                "--direction",
                "lower",
                "--verify",
                "pytest -q",
                "--stop-condition",
                "metric == 0",
                "--baseline-metric",
                "1",
                "--baseline-commit",
                "base111",
                "--baseline-description",
                "baseline failures",
                env=env,
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
                env=env,
            )

            transcript_path = root / "foreground-symbolic-terminal.jsonl"
            self.write_transcript_marker(transcript_path)
            completed = self.run_installed_hook(
                stop_hook,
                cwd=repo,
                payload={
                    "cwd": str(repo),
                    "stop_hook_active": False,
                    "transcript_path": str(transcript_path),
                },
                env=env,
            )
            completed.check_returncode()
            self.assertEqual(completed.stdout, "")

            pointer_payload = json.loads(
                self.repo_hook_context_path(repo).read_text(encoding="utf-8")
            )
            self.assertFalse(pointer_payload["active"])

    def test_stop_hook_only_blocks_for_autoresearch_sessions_and_uses_followup_prompt_when_active(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            env = self.hook_env(home)
            self.run_script("autoresearch_hooks_ctl.py", "install", env=env)
            hook_path = self.installed_hook_path(home, "stop.py")

            repo = root / "active-repo"
            repo.mkdir()
            self.run_script(
                "autoresearch_init_run.py",
                "--results-path",
                str(repo / "autoresearch-results/results.tsv"),
                "--state-path",
                str(repo / "autoresearch-results/state.json"),
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
                "base111",
                "--baseline-description",
                "baseline failures",
                env=env,
            )

            completed = self.run_installed_hook(
                hook_path,
                cwd=repo,
                payload={"cwd": str(repo), "stop_hook_active": False},
                env=env,
            )
            completed.check_returncode()
            self.assertEqual(completed.stdout, "")

            transcript_path = root / "foreground-rollout.jsonl"
            self.write_transcript_marker(transcript_path)
            completed = self.run_installed_hook(
                hook_path,
                cwd=repo,
                payload={
                    "cwd": str(repo),
                    "stop_hook_active": False,
                    "transcript_path": str(transcript_path),
                },
                env=env,
            )
            completed.check_returncode()
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["decision"], "block")
            self.assertIn("Do not rerun the wizard.", payload["reason"])
            self.assertIn("record it before starting the next one", payload["reason"])

            completed = self.run_installed_hook(
                hook_path,
                cwd=repo,
                payload={
                    "cwd": str(repo),
                    "stop_hook_active": True,
                    "transcript_path": str(transcript_path),
                },
                env=env,
            )
            completed.check_returncode()
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["decision"], "block")
            self.assertIn("already inside a stop-hook continuation", payload["reason"])

            terminal_repo = root / "terminal-repo"
            terminal_repo.mkdir()
            self.run_script(
                "autoresearch_init_run.py",
                "--results-path",
                str(terminal_repo / "autoresearch-results/results.tsv"),
                "--state-path",
                str(terminal_repo / "autoresearch-results/state.json"),
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
                "base000",
                "--baseline-description",
                "baseline failures",
                env=env,
            )

            completed = self.run_installed_hook(
                hook_path,
                cwd=terminal_repo,
                payload={
                    "cwd": str(terminal_repo),
                    "stop_hook_active": False,
                    "transcript_path": str(transcript_path),
                },
                env=env,
            )
            completed.check_returncode()
            self.assertEqual(completed.stdout, "")

    def test_stop_hook_uses_background_opt_in_and_workspace_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            env = self.hook_env(home)
            self.run_script("autoresearch_hooks_ctl.py", "install", env=env)
            hook_path = self.installed_hook_path(home, "stop.py")

            repo = root / "background-repo"
            repo.mkdir()
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
                "base111",
                "--baseline-description",
                "baseline failures",
                env=env,
            )

            hook_env = dict(env)
            hook_env["AUTORESEARCH_HOOK_ACTIVE"] = "1"
            hook_env["AUTORESEARCH_HOOK_RESULTS_PATH"] = str(results_path)
            hook_env["AUTORESEARCH_HOOK_STATE_PATH"] = str(state_path)
            hook_env["AUTORESEARCH_HOOK_LAUNCH_PATH"] = str(self.managed_launch_path(repo))
            hook_env["AUTORESEARCH_HOOK_RUNTIME_PATH"] = str(self.managed_runtime_path(repo))

            completed = self.run_installed_hook(
                hook_path,
                cwd=repo,
                payload={"cwd": str(repo), "stop_hook_active": False},
                env=hook_env,
            )
            completed.check_returncode()
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["decision"], "block")

    def test_installed_stop_hook_uses_managed_helper_bundle_without_source_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            env = self.hook_env(home)
            self.run_script("autoresearch_hooks_ctl.py", "install", env=env)

            manifest = self.installed_hook_path(home, "manifest.json")
            manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
            manifest_payload["helper_root_fallback"] = "/nonexistent/autoresearch-hooks"
            manifest_payload["skill_root_fallback"] = "/nonexistent/codex-autoresearch"
            manifest.write_text(json.dumps(manifest_payload, indent=2) + "\n", encoding="utf-8")

            hook_path = self.installed_hook_path(home, "stop.py")
            repo = root / "active-repo"
            repo.mkdir()
            self.run_script(
                "autoresearch_init_run.py",
                "--results-path",
                str(repo / "autoresearch-results/results.tsv"),
                "--state-path",
                str(repo / "autoresearch-results/state.json"),
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
                "base111",
                "--baseline-description",
                "baseline failures",
                env=env,
            )

            transcript_path = root / "foreground-rollout.jsonl"
            self.write_transcript_marker(transcript_path)
            completed = self.run_installed_hook(
                hook_path,
                cwd=repo,
                payload={
                    "cwd": str(repo),
                    "stop_hook_active": False,
                    "transcript_path": str(transcript_path),
                },
                env=env,
            )
            completed.check_returncode()
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["decision"], "block")
            self.assertIn("Do not rerun the wizard.", payload["reason"])
