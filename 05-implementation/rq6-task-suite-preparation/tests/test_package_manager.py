#!/usr/bin/env python3
"""Unit tests for RQ6 package-manager helpers."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import sys

LIB = Path(__file__).resolve().parents[1] / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

from package_manager import candidate_app_scripts, detect_package_manager, install_command  # noqa: E402


class TestPackageManager(unittest.TestCase):
    def test_detect_pnpm_lockfile(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "package.json").write_text(json.dumps({"scripts": {}}), encoding="utf-8")
            (root / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n", encoding="utf-8")
            detected = detect_package_manager(root)
            self.assertEqual(detected["package_manager"], "pnpm")
            self.assertEqual(install_command("pnpm"), ["pnpm", "install", "--frozen-lockfile"])

    def test_yarn_berry_immutable(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "package.json").write_text(
                json.dumps({"packageManager": "yarn@4.0.0"}), encoding="utf-8"
            )
            (root / "yarn.lock").write_text("", encoding="utf-8")
            detected = detect_package_manager(root)
            self.assertEqual(detected["yarn_variant"], "berry")
            self.assertEqual(install_command("yarn", "berry"), ["yarn", "install", "--immutable"])

    def test_bun_is_unsupported_for_v1(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "package.json").write_text("{}", encoding="utf-8")
            (root / "bun.lockb").write_text("", encoding="utf-8")
            detected = detect_package_manager(root)
            self.assertEqual(detected["package_manager"], "bun")
            self.assertEqual(detected["unsupported_reason"], "unsupported_package_manager")

    def test_candidate_app_scripts_include_ci_start_scripts(self) -> None:
        scripts = {
            "dev": "vite",
            "start:ci": "next start -p 3000",
            "cy:run": "cypress run",
            "start:e2e": "start-server-and-test dev http://localhost:3000 cypress run",
        }
        candidates = candidate_app_scripts(scripts)
        self.assertIn("dev", candidates)
        self.assertIn("start:ci", candidates)
        self.assertNotIn("cy:run", candidates)
        self.assertNotIn("start:e2e", candidates)


if __name__ == "__main__":
    unittest.main()
