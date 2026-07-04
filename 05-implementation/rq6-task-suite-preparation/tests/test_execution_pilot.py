#!/usr/bin/env python3
"""Unit tests for RQ6 execution-pilot sampling helpers."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "00_build_execution_pilot.py"
spec = importlib.util.spec_from_file_location("execution_pilot_script", SCRIPT)
assert spec and spec.loader
execution_pilot_script = importlib.util.module_from_spec(spec)
spec.loader.exec_module(execution_pilot_script)


class TestExecutionPilot(unittest.TestCase):
    def test_load_install_results_merges_multiple_files_and_marks_current_pass(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            first = root / "first.jsonl"
            second = root / "second.jsonl"
            first.write_text(
                json.dumps({"repo_full_name": "owner/repo", "repo_cache_key": "owner__repo", "install_ok": False, "status": "install_timeout"})
                + "\n",
                encoding="utf-8",
            )
            second.write_text(
                json.dumps(
                    {
                        "repo_full_name": "owner/repo",
                        "repo_cache_key": "owner__repo",
                        "install_ok": True,
                        "dependency_tree_present": True,
                        "install_validation_schema": execution_pilot_script.INSTALL_VALIDATION_SCHEMA,
                        "status": "pass",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            history = execution_pilot_script.load_install_results([first, second])
            row = history["owner/repo"]
            self.assertTrue(row["install_ok"])
            self.assertTrue(row["current_install_ok"])
            self.assertIn("install_timeout", row["statuses"])
            self.assertIn("pass", row["statuses"])
            self.assertEqual(row["durations"], [])

    def test_load_install_results_keeps_duration_history(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            results = root / "results.jsonl"
            results.write_text(
                json.dumps({"repo_full_name": "owner/repo", "repo_cache_key": "owner__repo", "duration_sec": 12.5, "status": "pass"})
                + "\n",
                encoding="utf-8",
            )
            history = execution_pilot_script.load_install_results([results])
            self.assertEqual(history["owner/repo"]["durations"], [12.5])

    def test_package_weight_reads_root_manifest_and_largest_lockfile(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo = root / "repo"
            repo.mkdir()
            (repo / "package.json").write_text(
                json.dumps(
                    {
                        "dependencies": {"a": "1.0.0"},
                        "devDependencies": {"b": "1.0.0", "c": "1.0.0"},
                    }
                ),
                encoding="utf-8",
            )
            (repo / "package-lock.json").write_text("x" * 1024, encoding="utf-8")
            (repo / "yarn.lock").write_text("x" * 2048, encoding="utf-8")

            weight = execution_pilot_script.package_weight({"repo_cache_path": str(repo)})

            self.assertEqual(weight["package_dependency_count"], 3)
            self.assertEqual(weight["largest_lockfile_kb"], 2.0)

    def test_lightweight_score_penalizes_timeout_and_heavy_dependency_graph(self) -> None:
        light = {
            "candidate_tests": 8,
            "previous_install_ok": False,
            "previous_current_install_ok": False,
            "previous_install_statuses": [],
            "local_base_url": True,
            "supports_file_filter": True,
            "supports_test_title_filter": True,
            "package_dependency_count": 10,
            "largest_lockfile_kb": 100.0,
            "package_manager": "npm",
            "app_start_command": "npm run dev",
        }
        heavy = dict(light)
        heavy.update(
            {
                "previous_install_statuses": ["install_timeout"],
                "package_dependency_count": 300,
                "largest_lockfile_kb": 1200.0,
                "package_manager": "pnpm",
            }
        )

        self.assertGreater(execution_pilot_script.lightweight_score(light), execution_pilot_script.lightweight_score(heavy))

    def test_repo_is_excluded_matches_repo_name_and_cache_key(self) -> None:
        excluded = {"owner/repo", "other__repo"}

        self.assertTrue(execution_pilot_script.repo_is_excluded({"repo_full_name": "owner/repo"}, excluded))
        self.assertTrue(execution_pilot_script.repo_is_excluded({"repo_cache_key": "other__repo"}, excluded))
        self.assertFalse(execution_pilot_script.repo_is_excluded({"repo_full_name": "keep/repo"}, excluded))
        self.assertFalse(execution_pilot_script.repo_is_excluded({"repo_full_name": "owner/repo"}, None))


if __name__ == "__main__":
    unittest.main()
