#!/usr/bin/env python3
"""Unit tests for RQ5-A assertion density metrics (Milestone 1)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from assertion_metrics import build_assertion_density_fields


class TestAssertionDensity(unittest.TestCase):
    def test_null_when_zero_denominator(self):
        row = build_assertion_density_fields(
            assertion_count=5,
            test_body_assertion_count=2,
            direct_assertion_count=2,
            hook_assertion_count=1,
            helper_assertion_count=2,
            ui_action_count=0,
            test_body_ui_action_count=0,
        )
        self.assertEqual(row["assertion_density_all_actions"], "")
        self.assertEqual(row["assertion_density_test_body"], "")

    def test_density_all_actions(self):
        row = build_assertion_density_fields(
            assertion_count=4,
            test_body_assertion_count=2,
            direct_assertion_count=2,
            hook_assertion_count=1,
            helper_assertion_count=1,
            ui_action_count=8,
            test_body_ui_action_count=4,
        )
        self.assertEqual(row["assertion_density_all_actions"], "0.5")
        self.assertEqual(row["assertion_density_test_body"], "0.5")

    def test_test_body_density_uses_test_body_assertion_count(self):
        row = build_assertion_density_fields(
            assertion_count=3,
            test_body_assertion_count=1,
            direct_assertion_count=2,
            hook_assertion_count=0,
            helper_assertion_count=1,
            ui_action_count=6,
            test_body_ui_action_count=2,
        )
        self.assertEqual(row["assertion_density_test_body"], "0.5")


if __name__ == "__main__":
    unittest.main()
