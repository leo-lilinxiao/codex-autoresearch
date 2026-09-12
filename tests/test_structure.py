from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class StructureTest(unittest.TestCase):
    def test_skill_fits_codex_initial_injection_limit(self) -> None:
        self.assertLessEqual((ROOT / "SKILL.md").stat().st_size, 8000)

    def test_skill_entrypoints_and_metadata(self) -> None:
        self.assertTrue((ROOT / "scripts" / "autoresearch.py").is_file())
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(skill.startswith("---\nname: codex-autoresearch\n"))
        self.assertRegex(skill, r"(?m)^description: .+")
        metadata = (ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertIn('display_name: "Codex Autoresearch"', metadata)
        self.assertIn("allow_implicit_invocation: false", metadata)

    def test_bundled_python_compiles(self) -> None:
        for source in (ROOT / "scripts").rglob("*.py"):
            with self.subTest(source=source.relative_to(ROOT)):
                compile(source.read_text(encoding="utf-8"), str(source), "exec")

    def test_local_markdown_links_resolve(self) -> None:
        markdown_files = [
            ROOT / "SKILL.md",
            ROOT / "README.md",
            ROOT / "CONTRIBUTING.md",
            *(ROOT / "references").rglob("*.md"),
            *(ROOT / "docs").rglob("*.md"),
        ]
        pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
        missing: list[str] = []
        for source in markdown_files:
            for target in pattern.findall(source.read_text(encoding="utf-8")):
                if target.startswith(("http://", "https://", "#")):
                    continue
                clean = target.split("#", 1)[0]
                if clean and not (source.parent / clean).resolve().exists():
                    missing.append(f"{source.relative_to(ROOT)} -> {target}")
        self.assertEqual([], missing)


if __name__ == "__main__":
    unittest.main()
