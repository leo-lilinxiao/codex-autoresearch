from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
TEST_GIT_USER_NAME = "Autoresearch Tests"
TEST_GIT_USER_EMAIL = "autoresearch-tests@example.com"


# Keep temporary test repos hermetic even on fresh machines without global git identity.
for env_name, env_value in (
    ("GIT_AUTHOR_NAME", TEST_GIT_USER_NAME),
    ("GIT_AUTHOR_EMAIL", TEST_GIT_USER_EMAIL),
    ("GIT_COMMITTER_NAME", TEST_GIT_USER_NAME),
    ("GIT_COMMITTER_EMAIL", TEST_GIT_USER_EMAIL),
):
    os.environ.setdefault(env_name, env_value)



class AutoresearchScriptsTestBase(unittest.TestCase):
    maxDiff = None

    def init_git_repo(self, path: Path) -> Path:
        path.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init", str(path)], check=True, capture_output=True, text=True)
        self.configure_git_identity(path)
        return path

    def configure_git_identity(self, path: Path) -> None:
        subprocess.run(
            ["git", "-C", str(path), "config", "user.email", TEST_GIT_USER_EMAIL],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "-C", str(path), "config", "user.name", TEST_GIT_USER_NAME],
            check=True,
            capture_output=True,
            text=True,
        )

    def _path_in_tempdir(self, path: Path) -> bool:
        try:
            return os.path.commonpath(
                [os.path.realpath(path), os.path.realpath(tempfile.gettempdir())]
            ) == os.path.realpath(tempfile.gettempdir())
        except ValueError:
            return False

    def _init_temp_git_repo_if_needed(self, path: Path) -> None:
        resolved = path.resolve()
        if not self._path_in_tempdir(resolved) or (resolved / ".git").exists():
            return
        existing = subprocess.run(
            ["git", "-C", str(resolved), "rev-parse", "--show-toplevel"],
            check=False,
            capture_output=True,
            text=True,
        )
        if existing.returncode == 0:
            self.configure_git_identity(resolved)
            return
        self.init_git_repo(resolved)

    def _git_toplevel_or_path(self, path: Path) -> Path:
        completed = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode == 0 and completed.stdout.strip():
            return Path(completed.stdout.strip())
        return path

    def _arg_value(self, args: tuple[str, ...], flag: str) -> str | None:
        try:
            index = args.index(flag)
        except ValueError:
            return None
        if index + 1 >= len(args):
            return None
        return args[index + 1]

    def _arg_values(self, args: tuple[str, ...], flag: str) -> list[str]:
        values: list[str] = []
        for index, value in enumerate(args):
            if value == flag and index + 1 < len(args):
                values.append(args[index + 1])
        return values

    def _prepare_init_run_repos(self, args: tuple[str, ...], cwd: Path | None) -> None:
        repo_arg = self._arg_value(args, "--repo")
        if repo_arg:
            self._init_temp_git_repo_if_needed(Path(repo_arg))
        else:
            results_arg = self._arg_value(args, "--results-path")
            workspace_root: Path | None = None
            if results_arg:
                results_path = Path(results_arg)
                if not results_path.is_absolute() and cwd is not None:
                    results_path = cwd / results_path
                if (
                    results_path.is_absolute()
                    and results_path.name == "results.tsv"
                    and results_path.parent.name == "autoresearch-results"
                ):
                    workspace_root = results_path.parent.parent
            if workspace_root is None and cwd is not None:
                workspace_root = cwd
            if workspace_root is not None:
                self._init_temp_git_repo_if_needed(workspace_root)

        for companion in self._arg_values(args, "--companion-repo-scope"):
            if "=" not in companion:
                continue
            path, _scope = companion.split("=", 1)
            self._init_temp_git_repo_if_needed(Path(path))

    def _repo_arg_from_results_or_cwd(self, args: tuple[str, ...], cwd: Path | None) -> Path | None:
        repo_arg = self._arg_value(args, "--repo")
        if repo_arg:
            return Path(repo_arg)

        results_arg = self._arg_value(args, "--results-path")
        if results_arg:
            results_path = Path(results_arg)
            if not results_path.is_absolute() and cwd is not None:
                results_path = cwd / results_path
            if results_path.name == "results.tsv" and results_path.parent.name == "autoresearch-results":
                return results_path.parent.parent

        return cwd

    def _workspace_root_from_results_repo_or_cwd(
        self,
        args: tuple[str, ...],
        cwd: Path | None,
    ) -> Path | None:
        workspace_arg = self._arg_value(args, "--workspace-root")
        if workspace_arg:
            return Path(workspace_arg)

        results_arg = self._arg_value(args, "--results-path")
        if results_arg:
            results_path = Path(results_arg)
            if not results_path.is_absolute() and cwd is not None:
                results_path = cwd / results_path
            if results_path.name == "results.tsv" and results_path.parent.name == "autoresearch-results":
                return results_path.parent.parent

        repo_arg = self._arg_value(args, "--repo")
        if repo_arg:
            return self._git_toplevel_or_path(Path(repo_arg))

        return self._git_toplevel_or_path(cwd) if cwd is not None else None

    def _with_required_repo_arg(
        self,
        script_name: str,
        args: tuple[str, ...],
        cwd: Path | None,
    ) -> tuple[str, ...]:
        updated_args = args
        if "--repo" not in updated_args and script_name in {
            "autoresearch_init_run.py",
            "autoresearch_resume_check.py",
            "autoresearch_supervisor_status.py",
        }:
            repo = self._repo_arg_from_results_or_cwd(updated_args, cwd)
            if repo is not None:
                self._init_temp_git_repo_if_needed(repo)
                updated_args = ("--repo", str(repo), *updated_args)

        if script_name == "autoresearch_init_run.py" and "--workspace-root" not in updated_args:
            workspace_root = self._workspace_root_from_results_repo_or_cwd(updated_args, cwd)
            if workspace_root is not None:
                updated_args = ("--workspace-root", str(workspace_root), *updated_args)

        if (
            script_name == "autoresearch_runtime_ctl.py"
            and updated_args
            and updated_args[0] in {"create-launch", "launch"}
            and "--workspace-root" not in updated_args
        ):
            workspace_root = self._workspace_root_from_results_repo_or_cwd(updated_args, cwd)
            if workspace_root is not None:
                updated_args = (
                    updated_args[0],
                    "--workspace-root",
                    str(workspace_root),
                    *updated_args[1:],
                )

        return updated_args

    def _prepare_runtime_ctl_repos(self, args: tuple[str, ...]) -> None:
        if not args or args[0] not in {"create-launch", "launch", "start", "status", "stop"}:
            return
        repo_arg = self._arg_value(args, "--repo")
        if repo_arg:
            self._init_temp_git_repo_if_needed(Path(repo_arg))
        codex_bin = self._arg_value(args, "--codex-bin")
        if codex_bin:
            self._exclude_test_path_if_in_git_repo(Path(codex_bin))
        for companion in self._arg_values(args, "--companion-repo-scope"):
            if "=" not in companion:
                continue
            path, _scope = companion.split("=", 1)
            self._init_temp_git_repo_if_needed(Path(path))

    def _exclude_test_path_if_in_git_repo(self, path: Path) -> None:
        repo = subprocess.run(
            ["git", "-C", str(path.parent), "rev-parse", "--show-toplevel"],
            check=False,
            capture_output=True,
            text=True,
        )
        if repo.returncode != 0:
            return
        repo_root = Path(repo.stdout.strip()).resolve()
        try:
            relative = path.resolve().relative_to(repo_root).as_posix()
        except ValueError:
            return
        exclude_path = repo_root / ".git" / "info" / "exclude"
        existing = exclude_path.read_text(encoding="utf-8") if exclude_path.exists() else ""
        if relative not in {line.strip() for line in existing.splitlines()}:
            if existing and not existing.endswith("\n"):
                existing += "\n"
            exclude_path.write_text(existing + relative + "\n", encoding="utf-8")

    def artifact_root(self, repo: Path) -> Path:
        return repo / "autoresearch-results"

    def managed_results_path(self, repo: Path) -> Path:
        return self.artifact_root(repo) / "results.tsv"

    def managed_state_path(self, repo: Path) -> Path:
        return self.artifact_root(repo) / "state.json"

    def managed_launch_path(self, repo: Path) -> Path:
        return self.artifact_root(repo) / "launch.json"

    def managed_runtime_path(self, repo: Path) -> Path:
        return self.artifact_root(repo) / "runtime.json"

    def managed_runtime_log_path(self, repo: Path) -> Path:
        return self.artifact_root(repo) / "runtime.log"

    def managed_lessons_path(self, repo: Path) -> Path:
        return self.artifact_root(repo) / "lessons.md"

    def managed_context_path(self, repo: Path) -> Path:
        return self.artifact_root(repo) / "context.json"

    def run_script_completed(
        self,
        script_name: str,
        *args: str,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        args = self._with_required_repo_arg(script_name, args, cwd)
        if script_name == "autoresearch_init_run.py":
            self._prepare_init_run_repos(args, cwd)
        if script_name == "autoresearch_runtime_ctl.py":
            self._prepare_runtime_ctl_repos(args)
        return subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / script_name), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=cwd,
            env=env,
        )

    def run_script(
        self,
        script_name: str,
        *args: str,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> dict[str, object]:
        completed = self.run_script_completed(script_name, *args, cwd=cwd, env=env)
        completed.check_returncode()
        return json.loads(completed.stdout)

    def run_script_text(
        self,
        script_name: str,
        *args: str,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> str:
        completed = self.run_script_completed(script_name, *args, cwd=cwd, env=env)
        completed.check_returncode()
        return completed.stdout.strip()

    def write_fake_codex(self, path: Path, *, body_lines: list[str]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "#!/usr/bin/env bash\nset -euo pipefail\n" + "\n".join(body_lines) + "\n",
            encoding="utf-8",
        )
        path.chmod(0o755)
        self._exclude_test_path_if_in_git_repo(path)

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
        verify: str = "python3 -c pass",
        guard: str | None = "python -m py_compile src",
        execution_policy: str = "danger_full_access",
        stop_condition: str | None = None,
        required_stop_labels: list[str] | None = None,
        required_keep_labels: list[str] | None = None,
        companion_repo_scopes: list[str] | None = None,
    ) -> dict[str, object]:
        self._init_temp_git_repo_if_needed(repo)
        for value in companion_repo_scopes or []:
            if "=" in value:
                companion_path, _scope = value.split("=", 1)
                self._init_temp_git_repo_if_needed(Path(companion_path))
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
            "--execution-policy",
            execution_policy,
        ]
        if guard is not None:
            args.extend(["--guard", guard])
        if stop_condition is not None:
            args.extend(["--stop-condition", stop_condition])
        for label in required_stop_labels or []:
            args.extend(["--required-stop-label", label])
        for label in required_keep_labels or []:
            args.extend(["--required-keep-label", label])
        for value in companion_repo_scopes or []:
            args.extend(["--companion-repo-scope", value])
        return self.run_script(*args)

    def write_sleeping_fake_codex(self, path: Path) -> None:
        self.write_fake_codex(
            path,
            body_lines=[
                'if [[ "${1:-}" != "exec" ]]; then',
                '  echo "expected codex exec" >&2',
                "  exit 64",
                "fi",
                "shift",
                'repo=""',
                "prompt_from_stdin=0",
                'while [[ $# -gt 0 ]]; do',
                '  case "$1" in',
                '    -C) repo="$2"; shift 2 ;;',
                '    -) prompt_from_stdin=1; shift ;;',
                '    *) shift ;;',
                '  esac',
                'done',
                'if [[ "$prompt_from_stdin" -ne 1 ]]; then',
                '  echo "expected prompt from stdin" >&2',
                "  exit 65",
                "fi",
                "cat >/dev/null",
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
        verify: str = "python3 -c pass",
        guard: str = "python -m py_compile src",
        execution_policy: str = "danger_full_access",
        fresh_start: bool = False,
        required_stop_labels: list[str] | None = None,
        required_keep_labels: list[str] | None = None,
        companion_repo_scopes: list[str] | None = None,
    ) -> dict[str, object]:
        self._init_temp_git_repo_if_needed(repo)
        for value in companion_repo_scopes or []:
            if "=" in value:
                companion_path, _scope = value.split("=", 1)
                self._init_temp_git_repo_if_needed(Path(companion_path))
        args = [
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
            "--execution-policy",
            execution_policy,
            "--codex-bin",
            str(fake_codex_path),
        ]
        for value in companion_repo_scopes or []:
            args.extend(["--companion-repo-scope", value])
        for label in required_stop_labels or []:
            args.extend(["--required-stop-label", label])
        for label in required_keep_labels or []:
            args.extend(["--required-keep-label", label])
        if fresh_start:
            args.append("--fresh-start")
        return self.run_script(*args)
