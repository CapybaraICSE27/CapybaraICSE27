#!/usr/bin/env python3
"""Standalone Milestone 1 integration test (runs from review bundle source_mirror)."""

from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from aggregate import Aggregator


class TestMilestone1Integration(unittest.TestCase):
    def test_finalize_emits_sequence_density_and_intent(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            tc = {"r::t": {"repo": "r", "test_id": "t", "describe_path": []}}
            agg = Aggregator(tc, out)
            for line, name in [(1, "page.goto"), (2, "page.click"), (3, "page.click")]:
                agg.ingest_feature(
                    {
                        "repo": "r",
                        "test_id": "t",
                        "feature_type": "ui_action",
                        "name": name,
                        "raw_code": f"await {name}('/x')" if name == "page.goto" else f"await {name}()",
                        "source_kind": "test_body",
                        "line": line,
                    }
                )
            agg.ingest_feature(
                {
                    "repo": "r",
                    "test_id": "t",
                    "feature_type": "assertion",
                    "name": "expect(page).toBeVisible",
                    "raw_code": "await expect(page).toBeVisible()",
                    "source_kind": "test_body",
                    "line": 4,
                }
            )
            agg.close_event_sinks()
            counts = agg.finalize()

            with (out / "rq4_interaction_complexity_by_test.csv").open(encoding="utf-8") as f:
                rq4 = list(csv.DictReader(f))[0]
            self.assertEqual(int(rq4["sequence_event_count"]), 3)
            self.assertEqual(int(rq4["test_body_sequence_event_count"]), 3)
            self.assertEqual(int(rq4["max_consecutive_identical_action"]), 2)
            self.assertEqual(int(rq4["sequence_scope_all_layers_approximate"]), 0)
            self.assertEqual(int(rq4["sequence_all_layers_includes_non_test_body_events"]), 0)

            with (out / "rq4_interaction_events.csv").open(encoding="utf-8") as f:
                rq4_ev = list(csv.DictReader(f))
            nav_rows = [r for r in rq4_ev if r["category"] == "navigation"]
            self.assertEqual(nav_rows[0]["sequence_index"], "0")
            self.assertEqual(nav_rows[0]["navigation_target"], "/x")
            self.assertEqual(nav_rows[0]["navigation_target_evidence_basis"], "navigation_api_literal_arg")

            with (out / "rq5_assertion_complexity_by_test.csv").open(encoding="utf-8") as f:
                rq5 = list(csv.DictReader(f))[0]
            cols = list(rq5.keys())
            self.assertLess(cols.index("direct_assertion_count"), cols.index("test_body_assertion_count"))
            self.assertLess(cols.index("assertion_density_all_actions"), cols.index("test_body_assertion_count"))
            self.assertLess(cols.index("test_body_assertion_count"), cols.index("verification_intent_counts"))
            self.assertEqual(rq5["assertion_density_all_actions"], "0.333333")
            self.assertEqual(int(rq5["test_body_assertion_count"]), 1)
            intents = json.loads(rq5["verification_intent_counts"])
            self.assertEqual(intents.get("element_presence"), 1)

            with (out / "rq5_assertion_events.csv").open(encoding="utf-8") as f:
                ev = list(csv.DictReader(f))[0]
            self.assertEqual(ev["verification_intent"], "element_presence")
            self.assertEqual(ev["verification_intent_evidence_basis"], "lexical_oracle_category_fallback")
            self.assertEqual(ev["verification_intent_confidence"], "medium")
            self.assertEqual(ev["assertion_execution_scope"], "test_body")

            self.assertIn("milestone1_rq4_sequence", counts)
            self.assertIn("milestone1_rq5_density", counts)

    def test_non_numeric_line_does_not_crash(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            tc = {"r::t": {"repo": "r", "test_id": "t", "describe_path": []}}
            agg = Aggregator(tc, out)
            agg.ingest_feature(
                {
                    "repo": "r",
                    "test_id": "t",
                    "feature_type": "ui_action",
                    "name": "page.click",
                    "raw_code": "await page.click()",
                    "source_kind": "test_body",
                    "line": "unknown",
                }
            )
            agg.close_event_sinks()
            agg.finalize()
            self.assertEqual(agg.by_key["r::t"].rq4_count, 1)


if __name__ == "__main__":
    unittest.main()
