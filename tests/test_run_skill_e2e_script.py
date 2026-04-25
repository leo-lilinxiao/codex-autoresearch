from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "run_skill_e2e.sh"
GATE_SCRIPT = REPO_ROOT / "scripts" / "run_contributor_gate.sh"


class RunSkillE2EScriptTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.script = SCRIPT.read_text(encoding="utf-8")
        cls.gate_script = GATE_SCRIPT.read_text(encoding="utf-8")

    def test_runtime_smoke_launch_passes_workspace_root(self) -> None:
        runtime_section = self.script.split("run_runtime_smoke()", 1)[1].split(
            'case "$MODE"', 1
        )[0]

        self.assertIn('--repo "$repo"', runtime_section)
        self.assertIn('--workspace-root "$repo"', runtime_section)

    def test_multi_repo_smoke_exercises_workspace_owned_helper_flow(self) -> None:
        multi_repo_section = self.script.split("run_multi_repo_smoke()", 1)[1].split(
            "run_interactive_smoke()", 1
        )[0]

        self.assertIn('--workspace-root "$workspace"', multi_repo_section)
        self.assertIn('--companion-repo-scope "$companion=pkg/**/*.py"', multi_repo_section)
        self.assertIn('check_skill_invariants.py" exec', multi_repo_section)
        self.assertIn('pointer.json', multi_repo_section)

    def test_exec_smoke_uses_portable_sha256_helper(self) -> None:
        self.assertIn("sha256_file()", self.script)
        self.assertIn("shasum -a 256", self.script)
        self.assertIn("hashlib.sha256", self.script)
        self.assertNotIn('sha256sum "$repo/autoresearch-results/lessons.md"', self.script)

    def test_contributor_gate_runs_multi_repo_smoke(self) -> None:
        self.assertIn('run_skill_e2e.sh" multi-repo-smoke --clean', self.gate_script)

    def test_copied_skill_excludes_local_runtime_and_cache_dirs(self) -> None:
        copy_section = self.script.split("copy_skill()", 1)[1].split("init_git_repo()", 1)[0]

        for path in (
            ".git",
            ".pytest_cache",
            ".venv",
            "autoresearch-results",
            "debug",
            "fix",
            "security",
            "ship",
        ):
            self.assertIn(f'$dest_skill_root/{path}', copy_section)
        self.assertIn("-name '__pycache__'", copy_section)


if __name__ == "__main__":
    unittest.main()
