#!/usr/bin/env python3
"""Unit tests for RQ6 candidate-test selection helpers."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "05_select_candidate_human_tests.py"
spec = importlib.util.spec_from_file_location("candidate_selection_script", SCRIPT)
assert spec and spec.loader
candidate_selection_script = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate_selection_script)


class TestCandidateSelection(unittest.TestCase):
    def test_playwright_test_dir_mismatch_is_advisory(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "playwright.config.ts").write_text(
                "export default { testDir: 'tests' };\n",
                encoding="utf-8",
            )
            spec_path = root / "e2e" / "outside.spec.ts"
            spec_path.parent.mkdir(parents=True)
            spec_path.write_text("test('works', async () => {});\n", encoding="utf-8")
            scope = candidate_selection_script.runner_scope(
                {"framework": "playwright", "file_path": "e2e/outside.spec.ts"},
                {"workdir_path": str(root), "runner_config": "playwright.config.ts"},
            )
            self.assertEqual(scope["runner_scope_status"], "in_scope_config_test_dir_mismatch_advisory")
            self.assertEqual(scope["runner_scope_warning"], "config_text_test_dir_mismatch")


if __name__ == "__main__":
    unittest.main()
