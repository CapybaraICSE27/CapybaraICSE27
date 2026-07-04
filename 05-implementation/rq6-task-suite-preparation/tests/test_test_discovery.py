#!/usr/bin/env python3
"""Unit tests for RQ6 runner-discovery helpers."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

LIB = Path(__file__).resolve().parents[1] / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

from test_discovery import (  # noqa: E402
    DiscoveryCache,
    classify_cypress_verify,
    classify_playwright_discovery,
    discovery_command,
    static_discovery_check,
)


class TestDiscovery(unittest.TestCase):
    def test_playwright_list_command_includes_file_and_title(self) -> None:
        command = discovery_command(
            {"framework": "playwright", "file_path": "tests/a.spec.ts", "test_name": "opens panel"},
            {"list_command": "npx playwright test --list", "framework": "playwright"},
        )
        self.assertEqual(command, ["npx", "playwright", "test", "--list", "tests/a.spec.ts", "-g", "opens panel"])

    def test_playwright_no_tests_found_is_not_discovered(self) -> None:
        result = classify_playwright_discovery(
            {
                "returncode": 1,
                "stdout": '{"errors":[{"message":"Error: No tests found."}]}',
                "stderr": "",
                "timed_out": False,
            }
        )
        self.assertFalse(result["discovered"])
        self.assertEqual(result["discovery_status"], "test_not_discovered")

    def test_cypress_missing_binary_is_not_discovered(self) -> None:
        result = classify_cypress_verify(
            {
                "returncode": 1,
                "stdout": "No version of Cypress is installed in: cache\\14.5.4\\Cypress",
                "stderr": "",
                "timed_out": False,
            }
        )
        self.assertFalse(result["discovered"])
        self.assertEqual(result["discovery_status"], "cypress_binary_missing")

    def test_static_check_rejects_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            result = static_discovery_check(
                {"framework": "cypress", "file_path": "cypress/e2e/missing.cy.ts"},
                {"framework": "cypress", "workdir_path": td},
            )
            self.assertFalse(result["discovered"])
            self.assertEqual(result["discovery_status"], "test_file_missing")

    def test_static_cypress_file_exists_is_accepted_as_unverified_scope(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            spec = root / "cypress" / "e2e" / "ok.cy.ts"
            spec.parent.mkdir(parents=True)
            spec.write_text("it('works', () => {})\n", encoding="utf-8")
            bin_dir = root / "node_modules" / ".bin"
            bin_dir.mkdir(parents=True)
            shim = bin_dir / ("cypress.cmd" if sys.platform.startswith("win") else "cypress")
            shim.write_text("@echo off\r\n" if sys.platform.startswith("win") else "#!/bin/sh\n", encoding="utf-8")
            result = static_discovery_check(
                {"framework": "cypress", "file_path": "cypress/e2e/ok.cy.ts"},
                {"framework": "cypress", "workdir_path": td},
            )
            self.assertTrue(result["discovered"])
            self.assertEqual(result["discovery_status"], "file_exists_unverified_runner_scope")

    def test_cypress_discovery_cache_key_is_repo_level(self) -> None:
        cache = DiscoveryCache()
        repo_ctx = {"framework": "cypress", "workdir_path": "repo"}
        first = {"framework": "cypress", "file_path": "cypress/e2e/a.cy.ts", "test_name": "a"}
        second = {"framework": "cypress", "file_path": "cypress/e2e/b.cy.ts", "test_name": "b"}
        self.assertEqual(cache.key_for(first, repo_ctx), cache.key_for(second, repo_ctx))

    def test_cypress_verify_uses_runner_command_prefix(self) -> None:
        command = discovery_command(
            {"framework": "cypress", "file_path": "cypress/e2e/a.cy.ts"},
            {"framework": "cypress", "runner_command_base": "pnpm exec cypress run"},
        )
        self.assertEqual(command, ["pnpm", "exec", "cypress", "verify"])


if __name__ == "__main__":
    unittest.main()
