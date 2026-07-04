#!/usr/bin/env python3
"""Unit tests for RQ6 install-stage helpers."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "03_install_repos.py"
spec = importlib.util.spec_from_file_location("install_repos_script", SCRIPT)
assert spec and spec.loader
install_repos_script = importlib.util.module_from_spec(spec)
spec.loader.exec_module(install_repos_script)


class TestInstallRepos(unittest.TestCase):
    def test_dependency_tree_present_accepts_node_modules_or_pnp(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.assertFalse(install_repos_script.dependency_tree_present(root))
            (root / "node_modules").mkdir()
            self.assertTrue(install_repos_script.dependency_tree_present(root))
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".pnp.cjs").write_text("", encoding="utf-8")
            self.assertTrue(install_repos_script.dependency_tree_present(root))

    def test_resume_rejects_stale_install_pass_without_current_schema(self) -> None:
        class Args:
            resume = True
            rerun_failed = True

        self.assertFalse(install_repos_script.should_keep_existing({"install_ok": True}, Args()))
        self.assertTrue(
            install_repos_script.should_keep_existing(
                {
                    "install_ok": True,
                    "dependency_tree_present": True,
                    "install_validation_schema": install_repos_script.INSTALL_VALIDATION_SCHEMA,
                },
                Args(),
            )
        )


if __name__ == "__main__":
    unittest.main()
