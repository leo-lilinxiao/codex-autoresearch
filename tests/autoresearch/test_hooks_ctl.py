from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from unittest import mock
from pathlib import Path

from .base import AutoresearchScriptsTestBase, SCRIPTS_DIR

sys.path.insert(0, str(SCRIPTS_DIR))
import autoresearch_hooks_ctl as hooks_ctl  # noqa: E402


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
            self.assertTrue(installed["persistent_setup_ready"])
            self.assertTrue(installed["hooks_feature_enabled"])
            self.assertTrue(installed["goals_feature_enabled"])
            self.assertTrue(installed["managed_session_start_trusted"])
            self.assertTrue(installed["managed_stop_trusted"])
            self.assertTrue(installed["managed_scripts_present"])
            self.assertTrue(self.installed_hook_path(home, "autoresearch_supervisor_status.py").exists())

            config_text = (codex_home / "config.toml").read_text(encoding="utf-8")
            self.assertIn("hooks = true", config_text)
            self.assertIn("goals = true", config_text)
            self.assertNotIn("# BEGIN codex-autoresearch hook trust", config_text)
            self.assertIn("trusted_hash = \"sha256:", config_text)
            hooks_payload = json.loads((codex_home / "hooks.json").read_text(encoding="utf-8"))
            self.assertIn("UserPromptSubmit", hooks_payload["hooks"])
            self.assertEqual(len(hooks_payload["hooks"]["SessionStart"]), 1)
            self.assertEqual(len(hooks_payload["hooks"]["Stop"]), 1)
            session_command = hooks_payload["hooks"]["SessionStart"][0]["hooks"][0]["command"]
            stop_command = hooks_payload["hooks"]["Stop"][0]["hooks"][0]["command"]
            self.assertIn(str(self.installed_hook_path(home, "session_start.py")), session_command)
            self.assertIn(str(self.installed_hook_path(home, "stop.py")), stop_command)

            reinstalled = self.run_script("autoresearch_hooks_ctl.py", "install", env=env)
            self.assertTrue(reinstalled["persistent_setup_ready"])
            self.assertTrue(reinstalled["managed_session_start_trusted"])
            self.assertTrue(reinstalled["managed_stop_trusted"])
            self.assertTrue(reinstalled["goals_feature_enabled_by_installer"])
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
            self.assertIn("hooks = true", config_text)
            self.assertIn("goals = true", config_text)
            self.assertNotIn("# BEGIN codex-autoresearch hook trust", config_text)
            self.assertNotIn("trusted_hash = \"sha256:", config_text)

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
            self.assertTrue(installed["persistent_setup_ready"])

            status = self.run_script(
                "autoresearch_hooks_ctl.py",
                "status",
                "--repo",
                str(repo),
                env=env,
            )
            self.assertTrue(status["persistent_setup_ready"])

            removed = self.run_script(
                "autoresearch_hooks_ctl.py",
                "uninstall",
                "--repo",
                str(repo),
                env=env,
            )
            self.assertIn("managed_groups_removed", removed)

    def test_status_reports_setup_gaps_and_recommended_launch_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            env = self.hook_env(home)

            status = self.run_script("autoresearch_hooks_ctl.py", "status", env=env)

            self.assertFalse(status["persistent_setup_ready"])
            self.assertTrue(status["startup_tip_needed"])
            self.assertIn("goals_not_enabled", status["startup_tip_reasons"])
            self.assertIn("hooks_not_enabled", status["startup_tip_reasons"])
            self.assertIn("full_access_not_enabled", status["startup_tip_reasons"])
            self.assertIn("goals_feature", status["persistent_setup_missing"])
            self.assertIn("hooks_feature", status["persistent_setup_missing"])
            self.assertIn("session_start_hook", status["persistent_setup_missing"])
            self.assertIn("stop_hook", status["persistent_setup_missing"])
            self.assertEqual(
                status["recommended_launch_command"],
                "codex --enable goals --enable hooks --dangerously-bypass-approvals-and-sandbox",
            )

    def test_status_treats_current_launch_flags_as_session_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            env = self.hook_env(home)

            with mock.patch.dict(os.environ, env, clear=False), mock.patch.object(
                hooks_ctl,
                "parent_process_commands",
                return_value=[
                    "python3 /tmp/status.py",
                    "codex --enable goals --enable hooks --dangerously-bypass-approvals-and-sandbox",
                ],
            ):
                status = hooks_ctl.status()

            self.assertFalse(status["persistent_setup_ready"])
            self.assertFalse(status["startup_tip_needed"])
            self.assertTrue(status["current_session_goals_feature_enabled"])
            self.assertTrue(status["current_session_hooks_feature_enabled"])
            self.assertTrue(status["current_session_full_access"])
            self.assertIn("goals_feature", status["persistent_setup_missing"])
            self.assertIn("hooks_feature", status["persistent_setup_missing"])

    def test_status_reminds_when_current_launch_omits_goal_flags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            env = self.hook_env(home)

            with mock.patch.dict(os.environ, env, clear=False), mock.patch.object(
                hooks_ctl,
                "parent_process_commands",
                return_value=[
                    "python3 /tmp/status.py",
                    "codex exec --dangerously-bypass-approvals-and-sandbox",
                ],
            ):
                status = hooks_ctl.status()

            self.assertTrue(status["startup_tip_needed"])
            self.assertIn("goals_not_enabled", status["startup_tip_reasons"])
            self.assertIn("hooks_not_enabled", status["startup_tip_reasons"])
            self.assertNotIn("full_access_not_enabled", status["startup_tip_reasons"])

    def test_install_trusts_managed_hooks_at_actual_group_indices(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            codex_home = home / ".codex"
            codex_home.mkdir(parents=True)
            env = self.hook_env(home)

            (codex_home / "hooks.json").write_text(
                json.dumps(
                    {
                        "hooks": {
                            "SessionStart": [
                                {
                                    "hooks": [
                                        {
                                            "type": "command",
                                            "command": "python3 /tmp/existing-session.py",
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
            self.assertTrue(installed["persistent_setup_ready"])
            self.assertTrue(installed["managed_session_start_trusted"])
            self.assertTrue(installed["managed_stop_trusted"])

            config_text = (codex_home / "config.toml").read_text(encoding="utf-8")
            self.assertIn(":session_start:1:0", config_text)
            self.assertIn(":stop:0:0", config_text)

    def test_install_replaces_moved_managed_hooks_by_status_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            codex_home = home / ".codex"
            codex_home.mkdir(parents=True)
            env = self.hook_env(home)

            (codex_home / "hooks.json").write_text(
                json.dumps(
                    {
                        "hooks": {
                            "SessionStart": [
                                {
                                    "matcher": "startup|resume",
                                    "hooks": [
                                        {
                                            "type": "command",
                                            "command": "python3 /old/home/.codex/autoresearch-hooks/session_start.py",
                                            "timeout": 5,
                                            "statusMessage": "codex-autoresearch SessionStart hook",
                                        }
                                    ],
                                }
                            ],
                            "Stop": [
                                {
                                    "hooks": [
                                        {
                                            "type": "command",
                                            "command": "python3 /old/home/.codex/autoresearch-hooks/stop.py",
                                            "timeout": 10,
                                            "statusMessage": "codex-autoresearch Stop hook",
                                        }
                                    ],
                                }
                            ],
                        }
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            installed = self.run_script("autoresearch_hooks_ctl.py", "install", env=env)
            self.assertTrue(installed["persistent_setup_ready"])
            self.assertEqual(installed["other_hook_groups_present"], 0)

            hooks_payload = json.loads((codex_home / "hooks.json").read_text(encoding="utf-8"))
            self.assertEqual(len(hooks_payload["hooks"]["SessionStart"]), 1)
            self.assertEqual(len(hooks_payload["hooks"]["Stop"]), 1)
            self.assertIn(
                str(self.installed_hook_path(home, "session_start.py")),
                hooks_payload["hooks"]["SessionStart"][0]["hooks"][0]["command"],
            )
            self.assertIn(
                str(self.installed_hook_path(home, "stop.py")),
                hooks_payload["hooks"]["Stop"][0]["hooks"][0]["command"],
            )

    def test_status_reads_hook_trust_with_toml_parser(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            codex_home = home / ".codex"
            codex_home.mkdir(parents=True)
            env = self.hook_env(home)

            installed = self.run_script("autoresearch_hooks_ctl.py", "install", env=env)
            self.assertTrue(installed["persistent_setup_ready"])

            config_path = codex_home / "config.toml"
            config_text = config_path.read_text(encoding="utf-8")
            config_text = config_text.replace("[hooks.state.", "[hooks.\"state\".")
            config_path.write_text(config_text, encoding="utf-8")

            status = self.run_script("autoresearch_hooks_ctl.py", "status", env=env)
            self.assertTrue(status["persistent_setup_ready"])
            self.assertTrue(status["managed_session_start_trusted"])
            self.assertTrue(status["managed_stop_trusted"])

    def test_uninstall_turns_hooks_off_but_preserves_goals_when_no_other_hooks_remain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            env = self.hook_env(home)

            self.run_script("autoresearch_hooks_ctl.py", "install", env=env)
            removed = self.run_script("autoresearch_hooks_ctl.py", "uninstall", env=env)
            self.assertFalse(removed["persistent_setup_ready"])

            config_text = (home / ".codex" / "config.toml").read_text(encoding="utf-8")
            self.assertIn("hooks = false", config_text)
            self.assertIn("goals = true", config_text)
            self.assertNotIn("# BEGIN codex-autoresearch hook trust", config_text)
            self.assertNotIn("trusted_hash = \"sha256:", config_text)
            self.assertFalse(self.installed_hook_path(home, "autoresearch_hook_common.py").exists())
            self.assertFalse(self.installed_hook_path(home, "autoresearch_hook_context.py").exists())
            self.assertFalse(self.installed_hook_path(home, "session_start.py").exists())
            self.assertFalse(self.installed_hook_path(home, "stop.py").exists())
            self.assertFalse(self.installed_hook_path(home, "autoresearch_supervisor_status.py").exists())

    def test_uninstall_preserves_user_enabled_goals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            codex_home = home / ".codex"
            codex_home.mkdir(parents=True)
            env = self.hook_env(home)
            (codex_home / "config.toml").write_text(
                "[features]\ngoals = true\n",
                encoding="utf-8",
            )

            installed = self.run_script("autoresearch_hooks_ctl.py", "install", env=env)
            self.assertTrue(installed["persistent_setup_ready"])
            self.assertFalse(installed["goals_feature_enabled_by_installer"])

            removed = self.run_script("autoresearch_hooks_ctl.py", "uninstall", env=env)
            self.assertFalse(removed["persistent_setup_ready"])

            config_text = (codex_home / "config.toml").read_text(encoding="utf-8")
            self.assertIn("hooks = false", config_text)
            self.assertIn("goals = true", config_text)

    def test_reinstall_and_uninstall_preserve_foreign_tables_inside_legacy_trust_markers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            codex_home = home / ".codex"
            codex_home.mkdir(parents=True)
            env = self.hook_env(home)

            self.run_script("autoresearch_hooks_ctl.py", "install", env=env)
            config_path = codex_home / "config.toml"
            config_text = config_path.read_text(encoding="utf-8")
            trust_start = config_text.index("[hooks.state.")
            before_trust = config_text[:trust_start].rstrip()
            trust_tables = config_text[trust_start:].rstrip()
            config_path.write_text(
                before_trust
                + "\n\n# BEGIN codex-autoresearch hook trust\n"
                + trust_tables
                + "\n\n[tui.model_availability_nux]\n"
                + '"gpt-5.5" = 1\n'
                + "# END codex-autoresearch hook trust\n",
                encoding="utf-8",
            )

            reinstalled = self.run_script("autoresearch_hooks_ctl.py", "install", env=env)
            self.assertTrue(reinstalled["persistent_setup_ready"])
            config_text = config_path.read_text(encoding="utf-8")
            self.assertIn("[tui.model_availability_nux]", config_text)
            self.assertIn('"gpt-5.5" = 1', config_text)
            self.assertNotIn("# BEGIN codex-autoresearch hook trust", config_text)
            self.assertIn("trusted_hash = \"sha256:", config_text)

            self.run_script("autoresearch_hooks_ctl.py", "uninstall", env=env)
            config_text = config_path.read_text(encoding="utf-8")
            self.assertIn("[tui.model_availability_nux]", config_text)
            self.assertIn('"gpt-5.5" = 1', config_text)
            self.assertNotIn("trusted_hash = \"sha256:", config_text)

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
            self.assertIn("Do not emit a placeholder status update", payload["reason"])

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
            self.assertIn("keep working instead of repeating a no-op status message", payload["reason"])

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

    def test_foreground_stop_hook_escalates_repeated_same_signature_to_needs_human(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            env = self.hook_env(home)
            self.run_script("autoresearch_hooks_ctl.py", "install", env=env)
            hook_path = self.installed_hook_path(home, "stop.py")

            repo = root / "stagnated-foreground"
            repo.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            self.run_script(
                "autoresearch_init_run.py",
                "--results-path",
                str(repo / "autoresearch-results/results.tsv"),
                "--state-path",
                str(repo / "autoresearch-results/state.json"),
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

            transcript_path = root / "foreground-stagnated.jsonl"
            self.write_transcript_marker(transcript_path)

            first = self.run_installed_hook(
                hook_path,
                cwd=repo,
                payload={
                    "cwd": str(repo),
                    "stop_hook_active": False,
                    "transcript_path": str(transcript_path),
                },
                env=env,
            )
            first.check_returncode()
            self.assertEqual(json.loads(first.stdout)["decision"], "block")

            second = self.run_installed_hook(
                hook_path,
                cwd=repo,
                payload={
                    "cwd": str(repo),
                    "stop_hook_active": True,
                    "transcript_path": str(transcript_path),
                },
                env=env,
            )
            second.check_returncode()
            self.assertEqual(json.loads(second.stdout)["decision"], "block")

            third = self.run_installed_hook(
                hook_path,
                cwd=repo,
                payload={
                    "cwd": str(repo),
                    "stop_hook_active": True,
                    "transcript_path": str(transcript_path),
                },
                env=env,
            )
            third.check_returncode()
            self.assertEqual(json.loads(third.stdout)["decision"], "block")

            fourth = self.run_installed_hook(
                hook_path,
                cwd=repo,
                payload={
                    "cwd": str(repo),
                    "stop_hook_active": True,
                    "transcript_path": str(transcript_path),
                },
                env=env,
            )
            fourth.check_returncode()
            self.assertEqual(fourth.stdout, "")

            pointer_payload = json.loads(
                self.repo_hook_context_path(repo).read_text(encoding="utf-8")
            )
            self.assertFalse(pointer_payload["active"])

            state_payload = json.loads(
                (repo / "autoresearch-results" / "state.json").read_text(encoding="utf-8")
            )
            self.assertEqual(state_payload["supervisor"]["recommended_action"], "needs_human")
            self.assertEqual(state_payload["supervisor"]["last_exit_kind"], "stagnated")
            self.assertEqual(state_payload["supervisor"]["stagnation_count"], 3)

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
