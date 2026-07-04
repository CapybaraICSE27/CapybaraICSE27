#!/usr/bin/env python3
"""Integration test: RQ3 pattern CSV outputs from synthetic features."""

from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from aggregate import Aggregator


class TestRq3PatternIntegration(unittest.TestCase):
    def test_finalize_writes_pattern_csvs(self):
        test_cases = {
            "acme/repo::t1": {
                "repo": "acme/repo",
                "test_id": "t1",
                "framework": "Playwright",
                "phase1_confidence": "high",
                "describe_path": ["Login"],
                "is_parameterized": False,
                "has_direct_ui_actions": True,
            }
        }
        features = [
            {
                "repo": "acme/repo",
                "test_id": "t1",
                "feature_type": "ui_action",
                "source_kind": "test_body",
                "name": "click",
                "raw_code": "await page.getByRole('button').click()",
                "line": 10,
                "helper_depth": 0,
                "locator_strategy_ast": "test_id",
                "locator_composition_ast": "direct_chain",
                "selector_literal_kind_ast": "unknown",
                "ast_confidence": "high",
            },
            {
                "repo": "acme/repo",
                "test_id": "t1",
                "feature_type": "ui_action",
                "source_kind": "test_body",
                "name": "click",
                "raw_code": "await page.locator('#submit').click()",
                "line": 11,
                "helper_depth": 0,
            },
            {
                "repo": "acme/repo",
                "test_id": "t1",
                "feature_type": "wait_synchronization",
                "source_kind": "test_body",
                "name": "page.waitForURL",
                "raw_code": "await page.waitForURL('**/home')",
                "line": 12,
                "helper_depth": 0,
            },
            {
                "repo": "acme/repo",
                "test_id": "t1",
                "feature_type": "assertion",
                "source_kind": "test_body",
                "name": "expect",
                "raw_code": "await expect(locator).toBeVisible()",
                "line": 13,
                "helper_depth": 0,
            },
            {
                "repo": "acme/repo",
                "test_id": "t1",
                "feature_type": "assertion",
                "source_kind": "test_body",
                "name": "expect",
                "raw_code": "await expect(locator).toBeEnabled()",
                "line": 14,
                "helper_depth": 0,
                "wait_subtype_ast": "assertion_retry_wait",
                "ast_confidence": "high",
            },
            {
                "repo": "acme/repo",
                "test_id": "t1",
                "feature_type": "helper_call",
                "source_kind": "test_body",
                "name": "LoginPage.open",
                "raw_code": "await LoginPage.open()",
                "line": 5,
                "helper_depth": 0,
            },
        ]

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            agg = Aggregator(test_cases, out)
            for f in features:
                agg.ingest_feature(f)
            agg.close_event_sinks()
            result = agg.finalize()

            self.assertEqual(result["rq3_locator_events"], 2)
            self.assertGreaterEqual(result["rq3_locator_ui_action_rows"], 2)
            self.assertGreaterEqual(result["rq3_sync_events"], 2)

            loc_path = out / "rq3_locator_pattern_events.csv"
            self.assertTrue(loc_path.exists())
            with loc_path.open(encoding="utf-8", newline="") as f:
                loc_rows = list(csv.DictReader(f))
            self.assertEqual(len(loc_rows), 2)
            compositions = {r["locator_composition"] for r in loc_rows}
            self.assertIn("direct_chain", compositions)

            pat_path = out / "rq3_patterns_by_test.csv"
            self.assertTrue(pat_path.exists())
            with pat_path.open(encoding="utf-8", newline="") as f:
                pat = list(csv.DictReader(f))[0]
            self.assertEqual(int(pat["locator_event_count"]), 2)
            self.assertEqual(int(pat["sync_event_count"]), result["rq3_sync_events"])
            self.assertGreaterEqual(int(pat["sync_event_count"]), 2)
            strat = json.loads(pat["locator_strategy_counts_json"])
            self.assertIn("test_id", strat)

            audit_path = out / "rq3_ast_vs_regex_locator_audit.csv"
            self.assertTrue(audit_path.exists())
            with audit_path.open(encoding="utf-8", newline="") as f:
                audit_rows = list(csv.DictReader(f))
            self.assertGreaterEqual(len(audit_rows), 1)
            self.assertIn("mismatch_type", audit_rows[0])
            self.assertNotEqual(audit_rows[0]["mismatch_type"], "match")
            self.assertEqual(result["rq3_ast_locator_audit_rows"], len(audit_rows))
            self.assertGreaterEqual(result["rq3_ast_regex_locator_mismatches"], 1)
            self.assertGreaterEqual(result["rq3_ast_locator_audit_nonmatch_rows"], 1)
            self.assertGreaterEqual(
                int(pat["assertion_retry_sync_count"]) + int(pat["condition_based_sync_count"]),
                2,
            )

    def test_page_object_call_count_excludes_expanded_ui_actions(self):
        """PO calls split by UI vs setup; expanded PO ui_actions do not inflate call count."""
        test_cases = {
            "acme/repo::t2": {
                "repo": "acme/repo",
                "test_id": "t2",
                "framework": "Playwright",
                "phase1_confidence": "high",
            }
        }
        features = [
            {
                "repo": "acme/repo",
                "test_id": "t2",
                "feature_type": "helper_call",
                "source_kind": "test_body",
                "name": "loginPage.open",
                "raw_code": "await loginPage.open()",
                "line": 5,
                "helper_depth": 0,
                "workflow_kind_ast": "page_object",
            },
            {
                "repo": "acme/repo",
                "test_id": "t2",
                "feature_type": "helper_call",
                "source_kind": "test_body",
                "name": "loginPage.submit",
                "raw_code": "await loginPage.submit()",
                "line": 6,
                "helper_depth": 0,
                "workflow_kind_ast": "page_object",
            },
            {
                "repo": "acme/repo",
                "test_id": "t2",
                "feature_type": "ui_action",
                "source_kind": "page_object",
                "name": "click",
                "raw_code": "await this.submitBtn.click()",
                "line": 20,
                "helper_depth": 1,
            },
            {
                "repo": "acme/repo",
                "test_id": "t2",
                "feature_type": "ui_action",
                "source_kind": "page_object",
                "name": "fill",
                "raw_code": "await this.userField.fill('x')",
                "line": 21,
                "helper_depth": 1,
            },
        ]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            agg = Aggregator(test_cases, out)
            for f in features:
                agg.ingest_feature(f)
            agg.close_event_sinks()
            agg.finalize()
            with (out / "rq3_patterns_by_test.csv").open(encoding="utf-8", newline="") as f:
                pat = list(csv.DictReader(f))[0]
            self.assertEqual(int(pat["page_object_call_count"]), 1)
            self.assertEqual(int(pat["page_object_setup_or_utility_call_count"]), 1)
            self.assertGreaterEqual(int(pat["page_object_ui_call_count"]), 3)
            self.assertGreaterEqual(int(pat["page_object_expanded_ui_count"]), 2)

    def test_workflow_archetype_row_exposes_dominance_evidence_columns(self):
        test_cases = {
            "acme/repo::t3": {
                "repo": "acme/repo",
                "test_id": "t3",
                "framework": "Cypress",
                "phase1_confidence": "high",
            }
        }
        features = [
            {
                "repo": "acme/repo",
                "test_id": "t3",
                "feature_type": "ui_action",
                "source_kind": "cypress_command",
                "name": "click",
                "raw_code": "cy.clickByTestId('save')",
                "line": 20,
                "helper_depth": 1,
            },
            {
                "repo": "acme/repo",
                "test_id": "t3",
                "feature_type": "ui_action",
                "source_kind": "cypress_command",
                "name": "type",
                "raw_code": "cy.typeByTestId('name', user.name)",
                "line": 21,
                "helper_depth": 1,
            },
            {
                "repo": "acme/repo",
                "test_id": "t3",
                "feature_type": "ui_action",
                "source_kind": "test_body",
                "name": "click",
                "raw_code": "cy.get('#done').click()",
                "line": 30,
                "helper_depth": 0,
            },
        ]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            agg = Aggregator(test_cases, out)
            for f in features:
                agg.ingest_feature(f)
            agg.close_event_sinks()
            agg.finalize()
            with (out / "rq3_patterns_by_test.csv").open(encoding="utf-8", newline="") as f:
                pat = list(csv.DictReader(f))[0]

            self.assertEqual(pat["workflow_archetype"], "framework_extension_centric")
            self.assertEqual(pat["dominant_workflow_source"], "cypress_command_ui")
            self.assertEqual(pat["workflow_dominant_source"], "cypress_command_ui")
            self.assertIn("workflow_source_count_json", pat)
            self.assertIn("workflow_top_two_sources_json", pat)
            top_two = json.loads(pat["workflow_top_two_sources_json"])
            self.assertEqual(top_two[0]["source"], "cypress_command_ui")
            self.assertIn("dominant_source", pat["workflow_archetype_basis"])


if __name__ == "__main__":
    unittest.main()
