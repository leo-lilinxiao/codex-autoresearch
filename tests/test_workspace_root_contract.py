from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WIZARD = REPO_ROOT / "references" / "interaction-wizard.md"
SKILL = REPO_ROOT / "SKILL.md"
GUIDE = REPO_ROOT / "docs" / "GUIDE.md"
README = REPO_ROOT / "README.md"


class WorkspaceRootContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.wizard = WIZARD.read_text(encoding="utf-8")
        cls.skill = SKILL.read_text(encoding="utf-8")
        cls.guide = GUIDE.read_text(encoding="utf-8")
        cls.readme = README.read_text(encoding="utf-8")

    def test_wizard_defaults_workspace_root_to_launch_context(self) -> None:
        self.assertIn("Default the `workspace_root` candidate from the launch context.", self.wizard)
        self.assertIn("use that repo root as the default candidate", self.wizard)
        self.assertIn("use the current launch directory as the default candidate", self.wizard)
        self.assertIn("Do not silently widen `workspace_root` to a parent directory", self.wizard)

    def test_wizard_confirmation_surfaces_results_directory(self) -> None:
        self.assertIn("- Results directory: `./autoresearch-results/`", self.wizard)
        self.assertIn("Always show the `Results directory`.", self.wizard)

    def test_skill_and_guide_match_launch_context_rule(self) -> None:
        self.assertIn("default the `workspace_root` from the launch context", self.skill)
        self.assertIn("Do not silently widen to a parent workspace", self.skill)
        self.assertIn("default workspace root comes from the launch context", self.guide)
        self.assertIn("should not silently widen the workspace root to a parent directory", self.guide)

    def test_readme_surfaces_launch_context_results_directory_rule(self) -> None:
        self.assertIn("Results directory stays in the launch context", self.readme)
        self.assertIn("Results directory: ./autoresearch-results/", self.readme)
        self.assertIn("default workspace root", self.readme)
        self.assertIn("should not silently widen", self.readme)
        self.assertIn("confirmation summary should always show the chosen Results directory", self.readme)


if __name__ == "__main__":
    unittest.main()
