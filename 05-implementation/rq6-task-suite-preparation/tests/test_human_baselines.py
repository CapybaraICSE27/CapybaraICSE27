#!/usr/bin/env python3
"""Unit tests for RQ6 human-baseline execution planning."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "06_run_human_baselines.py"
spec = importlib.util.spec_from_file_location("human_baselines_script", SCRIPT)
assert spec and spec.loader
human_baselines_script = importlib.util.module_from_spec(spec)
spec.loader.exec_module(human_baselines_script)


class TestHumanBaselines(unittest.TestCase):
    def test_cypress_execution_targets_are_deduped_by_spec(self) -> None:
        selected = [
            {
                "repo_full_name": "owner/repo",
                "repo_cache_key": "owner__repo",
                "framework": "cypress",
                "file_path": "cypress/e2e/login.cy.ts",
                "test_id": "test-a",
                "test_name": "logs in",
            },
            {
                "repo_full_name": "owner/repo",
                "repo_cache_key": "owner__repo",
                "framework": "cypress",
                "file_path": "cypress/e2e/login.cy.ts",
                "test_id": "test-b",
                "test_name": "logs out",
            },
        ]
        ctx = {"owner/repo": {"framework": "cypress", "supports_test_title_filter": False}}
        targets = human_baselines_script.build_execution_targets(selected, ctx)
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0]["execution_scope"], "spec_file")
        self.assertEqual(targets[0]["test_id"], "spec::cypress/e2e/login.cy.ts")
        self.assertEqual(targets[0]["represented_test_count"], 2)

    def test_playwright_command_uses_title_filter_when_available(self) -> None:
        test = {
            "framework": "playwright",
            "file_path": "tests/example.spec.ts",
            "test_name": "opens settings",
            "execution_scope": "test_title",
        }
        command = human_baselines_script.command_for(
            test,
            {"runner_command_base": "npx playwright test", "supports_test_title_filter": True},
            "chromium",
        )
        self.assertEqual(
            command,
            [
                "npx",
                "playwright",
                "test",
                "tests/example.spec.ts",
                "-g",
                "opens settings",
                "--project",
                "chromium",
                "--reporter=json",
            ],
        )

    def test_playwright_command_can_use_repo_default_projects(self) -> None:
        test = {
            "framework": "playwright",
            "file_path": "tests/example.spec.ts",
            "test_name": "opens settings",
            "execution_scope": "test_title",
        }
        command = human_baselines_script.command_for(
            test,
            {"runner_command_base": "npx playwright test", "supports_test_title_filter": True},
            "",
        )
        self.assertEqual(command, ["npx", "playwright", "test", "tests/example.spec.ts", "-g", "opens settings", "--reporter=json"])

    def test_pretest_setup_jsonl_indexes_repo_and_cache_key(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "setup.jsonl"
            path.write_text(
                json.dumps(
                    {
                        "repo_full_name": "owner/repo",
                        "repo_cache_key": "owner__repo",
                        "setup_id": "build",
                        "command": "node build.js",
                        "cwd_rel": "packages/app",
                        "required_paths_json": json.dumps(["dist/app.js"]),
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            setup = human_baselines_script.load_pretest_setup(path)
            self.assertEqual(setup["owner/repo"][0]["setup_id"], "build")
            self.assertEqual(setup["owner__repo"][0]["required_paths"], ["dist/app.js"])

    def test_pretest_setup_skips_when_required_paths_exist(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "dist").mkdir()
            (root / "dist" / "app.js").write_text("ok", encoding="utf-8")
            args = Namespace(out_dir=root / "out", pretest_setup_timeout_sec=5)
            result = human_baselines_script.run_pretest_setup_for_repo(
                "owner/repo",
                {"repo_cache_key": "owner__repo", "workdir_path": str(root)},
                [
                    {
                        "setup_id": "build",
                        "command": "command-that-should-not-run",
                        "cwd_rel": ".",
                        "required_paths": ["dist/app.js"],
                    }
                ],
                args,
            )
            self.assertEqual(result["_pretest_setup_status"], "pass")
            self.assertIn("skipped_required_paths_present", result["_pretest_setup_logs_json"])

    def test_playwright_browser_setup_installs_requested_browsers(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            out_dir = root / "out"
            captured = {}
            original = human_baselines_script.run_process_capture

            def fake_run_process_capture(command, *, cwd=None, timeout=0):
                captured["command"] = list(command)
                captured["cwd"] = cwd
                captured["timeout"] = timeout
                return {"returncode": 0, "stdout": "installed", "stderr": "", "timed_out": False}

            human_baselines_script.run_process_capture = fake_run_process_capture
            try:
                result = human_baselines_script.run_playwright_browser_setup_for_repo(
                    "owner/repo",
                    {
                        "repo_cache_key": "owner__repo",
                        "framework": "playwright",
                        "workdir_path": str(root),
                    },
                    Namespace(
                        out_dir=out_dir,
                        ensure_playwright_browsers="chromium firefox",
                        ensure_playwright_browsers_timeout_sec=123,
                    ),
                )
            finally:
                human_baselines_script.run_process_capture = original

            self.assertEqual(captured["command"], ["npx", "playwright", "install", "chromium", "firefox"])
            self.assertEqual(captured["cwd"], root)
            self.assertEqual(captured["timeout"], 123)
            self.assertEqual(result["_playwright_browser_setup_status"], "pass")
            logs = json.loads(result["_playwright_browser_setup_logs_json"])
            self.assertEqual(logs[0]["command"], "npx playwright install chromium firefox")
            self.assertTrue(Path(logs[0]["stdout_path"]).exists())

    def test_playwright_browser_setup_failure_blocks_baseline_execution(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            row = human_baselines_script.run_once(
                {
                    "repo_full_name": "owner/repo",
                    "repo_cache_key": "owner__repo",
                    "framework": "playwright",
                    "file_path": "tests/example.spec.ts",
                    "test_name": "opens settings",
                    "execution_scope": "test_title",
                    "test_id": "test-a",
                },
                {
                    "repo_cache_key": "owner__repo",
                    "framework": "playwright",
                    "workdir_path": str(root),
                    "runner_command_base": "npx playwright test",
                    "_playwright_browser_setup_status": "failed_nonzero_exit",
                    "_playwright_browser_setup_error": "exit=1",
                    "_playwright_browser_setup_logs_json": "[]",
                },
                1,
                Namespace(execute=True, playwright_project="chromium"),
            )
            self.assertEqual(row["status"], "playwright_browser_setup_failed")
            self.assertEqual(row["failure_category"], "failed_nonzero_exit")
            self.assertFalse(row["executed"])

    def test_app_start_override_preserves_original_command(self) -> None:
        ctx = {"app_start_command": "npx serve -l 8080 .", "base_url": "http://localhost:8080"}
        human_baselines_script.apply_app_start_override(
            ctx,
            {
                "app_start_command": "python -m http.server 8080 --bind 127.0.0.1",
                "base_url": "http://localhost:8080",
                "app_start_command_correction": "manual_triage_static_python_server",
            },
        )
        self.assertEqual(ctx["app_start_command_original"], "npx serve -l 8080 .")
        self.assertEqual(ctx["app_start_command"], "python -m http.server 8080 --bind 127.0.0.1")
        self.assertEqual(ctx["app_start_command_correction"], "manual_triage_static_python_server")


if __name__ == "__main__":
    unittest.main()
