#!/usr/bin/env python3
"""Milestone 3 integration: AST-tagged fields flow through aggregation."""

from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from aggregate import Aggregator


class TestMilestone3Integration(unittest.TestCase):
    def test_finalize_emits_m3_metrics(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            tc = {"r::t": {"repo": "r", "test_id": "t", "describe_path": []}}
            agg = Aggregator(tc, out)

            agg.ingest_feature({
                "repo": "r",
                "test_id": "t",
                "feature_type": "ui_action",
                "name": "page.click",
                "raw_code": "await page.click('#btn')",
                "source_kind": "test_body",
                "line": 5,
                "control_flow_enclosure": "loop",
                "control_flow_loop_depth": 1,
                "control_flow_branch_depth": 0,
                "control_flow_branch_kind": "",
                "control_flow_branch_arm": "",
                "action_signature_json": (
                    '{"v":2,"category":"click","terminal_action":"click",'
                    '"locator_strategy":"","input_channel":"","navigation_target":"","source_layer":"test_body"}'
                ),
            })
            agg.ingest_feature({
                "repo": "r",
                "test_id": "t",
                "feature_type": "assertion",
                "name": "expect(...).toBeVisible",
                "raw_code": "await expect(page.locator('#x')).toBeVisible()",
                "source_kind": "test_body",
                "line": 8,
                "assertion_chain_root_id": "f:8:100",
                "assertion_chain_index": 0,
                "assertion_chain_length": 1,
                "assertion_matcher": "toBeVisible",
                "assertion_subject_kind": "locator",
                "assertion_framework": "playwright",
                "is_soft_assertion": False,
                "is_grouped_assertion": False,
                "assertion_group_kind": "none",
            })
            agg.close_event_sinks()
            summary = agg.finalize()

            self.assertIn("milestone3_rq4_control_flow", summary)
            self.assertIn("milestone3_rq5_assertion_chains", summary)
            self.assertIn("milestone3_action_signature_v2", summary)

            with (out / "rq4_interaction_complexity_by_test.csv").open(encoding="utf-8") as f:
                rq4 = list(csv.DictReader(f))[0]
            self.assertEqual(int(rq4["loop_driven_action_count"]), 1)
            self.assertEqual(int(rq4["classified_user_action_loop_driven_action_count"]), 1)
            self.assertEqual(rq4["classified_user_action_conditionalized_action_fraction"], "0.0")
            self.assertEqual(rq4["sequence_signature_version"], "v2")
            self.assertEqual(int(rq4["classified_user_action_event_count"]), 1)
            self.assertEqual(int(rq4["ui_actions_with_control_flow_enclosure_non_none"]), 1)
            self.assertEqual(int(rq4["ui_actions_with_control_flow_field_present"]), 1)
            self.assertEqual(
                int(summary["ui_rows_with_control_flow_field_present"]), 1
            )
            self.assertEqual(
                int(summary["ui_rows_with_control_flow_enclosure_non_none"]), 1
            )

            with (out / "rq5_assertion_complexity_by_test.csv").open(encoding="utf-8") as f:
                rq5 = list(csv.DictReader(f))[0]
            self.assertEqual(int(rq5["assertions_with_chain_fields"]), 1)

    def test_control_flow_provenance_splits_field_present_vs_non_none(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            tc = {"r::t": {"repo": "r", "test_id": "t", "describe_path": []}}
            agg = Aggregator(tc, out)
            agg.ingest_feature({
                "repo": "r",
                "test_id": "t",
                "feature_type": "ui_action",
                "name": "page.click",
                "raw_code": "await page.click('#a')",
                "source_kind": "test_body",
                "line": 1,
                "control_flow_enclosure": "none",
            })
            agg.ingest_feature({
                "repo": "r",
                "test_id": "t",
                "feature_type": "ui_action",
                "name": "page.click",
                "raw_code": "await page.click('#b')",
                "source_kind": "test_body",
                "line": 2,
                "control_flow_enclosure": "branch",
                "control_flow_branch_kind": "if",
            })
            agg.close_event_sinks()
            summary = agg.finalize()
            self.assertEqual(
                int(summary["ui_rows_with_control_flow_field_present"]), 2
            )
            self.assertEqual(
                int(summary["ui_rows_with_control_flow_enclosure_non_none"]), 1
            )


if __name__ == "__main__":
    unittest.main()
