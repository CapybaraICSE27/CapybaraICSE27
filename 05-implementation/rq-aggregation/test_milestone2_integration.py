#!/usr/bin/env python3
"""Milestone 2 integration: RQ1 setup/teardown intent outputs."""

from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from aggregate import Aggregator


class TestMilestone2Integration(unittest.TestCase):
    def test_finalize_emits_rq1_intent_outputs(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            tc = {"r::t": {"repo": "r", "test_id": "t", "describe_path": []}}
            agg = Aggregator(tc, out)
            agg.ingest_feature(
                {
                    "repo": "r",
                    "test_id": "t",
                    "feature_type": "network_mock",
                    "name": "cy.intercept",
                    "raw_code": "cy.intercept('GET', '/api/users')",
                    "source_kind": "beforeEach",
                    "line": 2,
                }
            )
            agg.ingest_feature(
                {
                    "repo": "r",
                    "test_id": "t",
                    "feature_type": "ui_action",
                    "name": "page.goto",
                    "raw_code": "await page.goto('/dashboard')",
                    "source_kind": "test_body",
                    "line": 5,
                }
            )
            agg.ingest_feature(
                {
                    "repo": "r",
                    "test_id": "t",
                    "feature_type": "ui_action",
                    "name": "page.click",
                    "raw_code": "await page.click('#save')",
                    "source_kind": "test_body",
                    "line": 8,
                }
            )
            agg.close_event_sinks()
            summary = agg.finalize()

            self.assertIn("milestone2_rq1_intent", summary)
            self.assertIn("partial_coverage_note", summary["milestone2_rq1_intent"])

            with (out / "rq1_setup_teardown_intent_events.csv").open(encoding="utf-8") as f:
                intent_rows = list(csv.DictReader(f))
            self.assertGreaterEqual(len(intent_rows), 1)
            intents = {r["primary_intent"] for r in intent_rows}
            self.assertIn("network_mock_or_spy", intents)
            # Navigation at line 5 excluded: prior setup (intercept) at line 2
            self.assertNotIn("navigation_bootstrap", intents)

            with (out / "rq1_setup_teardown_intent_by_test.csv").open(encoding="utf-8") as f:
                by_test = list(csv.DictReader(f))[0]
            self.assertGreater(int(by_test["setup_teardown_intent_unit_count"]), 0)

            # Inventory layer unchanged
            self.assertTrue((out / "rq1_environment_control_events.csv").exists())


if __name__ == "__main__":
    unittest.main()
