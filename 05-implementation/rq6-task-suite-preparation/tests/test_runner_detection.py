#!/usr/bin/env python3
"""Unit tests for RQ6 runner/app detection helpers."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

LIB = Path(__file__).resolve().parents[1] / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

from runner_detection import detect_app, infer_local_base_url, is_local_base_url  # noqa: E402


class TestRunnerDetection(unittest.TestCase):
    def test_ipv6_loopback_is_local_not_production(self) -> None:
        self.assertTrue(is_local_base_url("http://[::1]:3000"))
        self.assertFalse(is_local_base_url("https://example.com"))

    def test_infers_next_port_flag(self) -> None:
        self.assertEqual(infer_local_base_url("next dev --turbopack -p 8887"), "http://localhost:8887")

    def test_infers_common_default_ports(self) -> None:
        self.assertEqual(infer_local_base_url("next dev --turbopack"), "http://localhost:3000")
        self.assertEqual(infer_local_base_url("vite --host 127.0.0.1"), "http://localhost:5173")
        self.assertEqual(infer_local_base_url("nx serve"), "http://localhost:4200")

    def test_app_detection_prefers_ci_start_over_dev(self) -> None:
        package_json = {
            "scripts": {
                "dev": "vite --host 127.0.0.1",
                "start:ci": "next start -p 3100",
                "cy:run": "cypress run",
            }
        }
        app = detect_app(
            Path.cwd(),
            framework="cypress",
            runner_config="",
            package_json=package_json,
            package_manager="npm",
        )
        self.assertEqual(app["app_script_name"], "start:ci")
        self.assertEqual(app["app_start_command"], "npm run start:ci")
        self.assertEqual(app["base_url"], "http://localhost:3100")


if __name__ == "__main__":
    unittest.main()
