from __future__ import annotations

import sys
import unittest

from .base import SCRIPTS_DIR

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from autoresearch_paths import path_is_in_scope


class AutoresearchPathsTest(unittest.TestCase):
    def test_hidden_file_scope_does_not_alias_plain_name(self) -> None:
        self.assertTrue(path_is_in_scope(".env", [".env"]))
        self.assertFalse(path_is_in_scope("env", [".env"]))

    def test_hidden_directory_glob_matches_hidden_directory(self) -> None:
        self.assertTrue(path_is_in_scope(".github/workflows/ci.yml", [".github/**"]))
        self.assertFalse(path_is_in_scope("github/workflows/ci.yml", [".github/**"]))

    def test_dot_slash_prefix_is_stripped_without_mutating_hidden_names(self) -> None:
        self.assertTrue(path_is_in_scope("./src/x.py", ["./src/**"]))
        self.assertTrue(path_is_in_scope("./.env", ["./.env"]))
