#!/usr/bin/env python3
"""Unit tests for Milestone 3 aggregation metrics."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from assertion_chain_metrics import build_assertion_chain_fields
from interaction_control_flow_metrics import (
    build_control_flow_fields,
    compute_dual_scope_control_flow_metrics,
)
from interaction_sequence_metrics import action_signature_from_event


class TestControlFlowMetrics(unittest.TestCase):
    def test_loop_and_branch_counts(self):
        events = [
            {"control_flow_enclosure": "loop", "control_flow_loop_depth": 1, "helper_depth": 0},
            {"control_flow_enclosure": "branch", "control_flow_branch_kind": "if", "helper_depth": 0},
            {"control_flow_enclosure": "loop_and_branch", "control_flow_branch_kind": "if", "helper_depth": 1},
            {"control_flow_enclosure": "branch", "control_flow_branch_kind": "try_catch", "helper_depth": 0},
        ]
        out = build_control_flow_fields(events)
        self.assertEqual(out["loop_driven_action_count"], 2)
        self.assertEqual(out["branch_driven_action_count"], 3)
        self.assertEqual(out["non_error_branch_driven_action_count"], 2)
        self.assertEqual(out["helper_loop_driven_action_count"], 1)
        self.assertEqual(out["conditionalized_action_count"], 2)
        self.assertEqual(out["try_catch_enclosed_action_count"], 1)

    def test_none_enclosure_not_counted_as_tagged(self):
        events = [
            {"control_flow_enclosure": "none", "helper_depth": 0},
            {"control_flow_enclosure": "loop", "helper_depth": 0},
        ]
        out = build_control_flow_fields(events)
        self.assertEqual(out["ui_actions_with_control_flow_field_present"], 2)
        self.assertEqual(out["ui_actions_with_control_flow_enclosure_non_none"], 1)

    def test_conditionalized_fraction_uses_all_ui_actions(self):
        events = [
            {"control_flow_enclosure": "none", "helper_depth": 0},
            {"control_flow_enclosure": "none", "helper_depth": 0},
            {"control_flow_enclosure": "branch", "control_flow_branch_kind": "if", "helper_depth": 0},
        ]
        out = build_control_flow_fields(events)
        self.assertEqual(out["conditionalized_action_count"], 1)
        self.assertEqual(out["conditionalized_action_fraction"], round(1 / 3, 6))

    def test_dual_scope_control_flow_metrics(self):
        all_events = [
            {"control_flow_enclosure": "none", "helper_depth": 0},
            {"control_flow_enclosure": "branch", "control_flow_branch_kind": "if", "helper_depth": 0},
            {"control_flow_enclosure": "branch", "control_flow_branch_kind": "if", "helper_depth": 1},
        ]
        tb_events = all_events[:2]
        out = compute_dual_scope_control_flow_metrics(all_events, tb_events)
        self.assertEqual(out["all_layer_conditionalized_action_fraction"], round(2 / 3, 6))
        self.assertEqual(out["test_body_conditionalized_action_fraction"], round(1 / 2, 6))
        self.assertEqual(out["control_flow_scope_all_layers_includes_non_test_body_events"], 1)

    def test_paper_facing_control_flow_excludes_locator_wait_and_unknown(self):
        all_events = [
            {"category": "locator_query", "control_flow_enclosure": "branch", "control_flow_branch_kind": "if"},
            {"category": "wait_synchronization", "control_flow_enclosure": "branch", "control_flow_branch_kind": "if"},
            {"category": "unknown_action", "control_flow_enclosure": "loop"},
            {"category": "click", "control_flow_enclosure": "loop_and_branch", "control_flow_branch_kind": "if"},
        ]
        out = compute_dual_scope_control_flow_metrics(all_events, all_events)
        self.assertEqual(out["conditionalized_action_count"], 3)
        self.assertEqual(out["loop_driven_action_count"], 2)
        self.assertEqual(out["classified_user_action_conditionalized_action_count"], 1)
        self.assertEqual(out["classified_user_action_loop_driven_action_count"], 1)
        self.assertEqual(out["classified_user_action_conditionalized_action_fraction"], 1.0)


class TestAssertionChainMetrics(unittest.TestCase):
    def test_chained_vs_standalone(self):
        events = [
            {"assertion_chain_root_id": "f:1:0", "assertion_chain_length": 3, "assertion_chain_index": 0},
            {"assertion_chain_root_id": "f:1:0", "assertion_chain_length": 3, "assertion_chain_index": 1},
            {"assertion_chain_root_id": "f:2:0", "assertion_chain_length": 1, "assertion_chain_index": 0},
        ]
        out = build_assertion_chain_fields(events)
        self.assertEqual(out["chained_assertion_count"], 2)
        self.assertEqual(out["standalone_assertion_count"], 1)
        self.assertEqual(out["max_assertion_chain_length"], 3)
        self.assertEqual(out["assertions_missing_chain_metadata_count"], 0)

    def test_soft_and_grouped_chain_counts(self):
        events = [
            {
                "assertion_chain_root_id": "f:1:0",
                "assertion_chain_length": 2,
                "assertion_chain_index": 0,
                "is_soft_assertion": True,
                "is_grouped_assertion": True,
            },
            {
                "assertion_chain_root_id": "f:1:0",
                "assertion_chain_length": 2,
                "assertion_chain_index": 1,
                "is_soft_assertion": True,
                "is_grouped_assertion": True,
            },
            {"assertion_chain_root_id": "f:2:0", "assertion_chain_length": 1},
        ]
        out = build_assertion_chain_fields(events)
        self.assertEqual(out["soft_assertion_count"], 2)
        self.assertEqual(out["soft_assertion_chain_count"], 1)
        self.assertEqual(out["grouped_assertion_count"], 2)
        self.assertEqual(out["grouped_assertion_chain_count"], 1)
        events = [
            {"assertion_chain_root_id": "f:1:0", "assertion_chain_length": 2},
            {"category": "generic_assertion"},
        ]
        out = build_assertion_chain_fields(events)
        self.assertEqual(out["chained_assertion_count"], 1)
        self.assertEqual(out["standalone_assertion_count"], 0)
        self.assertEqual(out["assertions_missing_chain_metadata_count"], 1)


class TestActionSignatureV2(unittest.TestCase):
    def test_prefers_v2_json(self):
        sig = action_signature_from_event({
            "category": "click",
            "name": "page.click",
            "action_signature_json": (
                '{"v":2,"category":"click","terminal_action":"click",'
                '"locator_strategy":"css_selector","input_channel":"","navigation_target":""}'
            ),
        })
        self.assertIn("click", sig)
        self.assertIn("css_selector", sig)


if __name__ == "__main__":
    unittest.main()
