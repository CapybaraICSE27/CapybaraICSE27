#!/usr/bin/env python3
"""Unit tests for RQ6 runner/app detection script helpers."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "04_detect_runner_and_app.py"
spec = importlib.util.spec_from_file_location("detect_runner_app_script", SCRIPT)
assert spec and spec.loader
detect_runner_app_script = importlib.util.module_from_spec(spec)
spec.loader.exec_module(detect_runner_app_script)


class TestDetectRunnerAndApp(unittest.TestCase):
    def test_playwright_config_managed_app_can_pass_without_parsed_local_url(self) -> None:
        row = {
            "framework": "playwright",
            "runner_identified": True,
            "runner_managed_app_possible": True,
            "app_start_command": "",
            "base_url": "",
            "production_base_url_only": False,
        }
        self.assertEqual(detect_runner_app_script.status_for(row), "pass")


if __name__ == "__main__":
    unittest.main()
