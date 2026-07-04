#!/usr/bin/env python3
"""Unit tests for RQ4-A sequence repetition metrics (Milestone 1)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from interaction_sequence_metrics import (
    compute_dual_scope_sequence_metrics,
    compute_sequence_metrics,
    extract_navigation_target,
    normalize_action_signature,
    resolve_navigation_target_fields,
)


class TestNormalizeActionSignature(unittest.TestCase):
    def test_category_and_name(self):
        sig = normalize_action_signature("click", "page.click")
        self.assertEqual(sig, "click|page.click")


class TestExtractNavigationTarget(unittest.TestCase):
    def test_goto_url(self):
        self.assertEqual(
            extract_navigation_target("await page.goto('/login')"),
            "/login",
        )

    def test_visit_double_quotes(self):
        self.assertEqual(
            extract_navigation_target("cy.visit(\"/dashboard\")"),
            "/dashboard",
        )


class TestComputeSequenceMetrics(unittest.TestCase):
    def test_empty(self):
        m = compute_sequence_metrics([])
        self.assertEqual(m["sequence_event_count"], 0)
        self.assertEqual(m["repeat_action_fraction"], "")

    def test_consecutive_repeat(self):
        events = [
            {"line": 1, "category": "click", "name": "page.click", "_ingest_index": 0},
            {"line": 2, "category": "click", "name": "page.click", "_ingest_index": 1},
            {"line": 3, "category": "click", "name": "page.click", "_ingest_index": 2},
        ]
        m = compute_sequence_metrics(events)
        self.assertEqual(m["max_consecutive_identical_action"], 3)
        self.assertEqual(m["repeat_action_fraction"], 1.0)

    def test_same_line_preserves_ingestion_order(self):
        events = [
            {"line": 10, "category": "click", "name": "z.click", "_ingest_index": 0},
            {"line": 10, "category": "click", "name": "a.click", "_ingest_index": 1},
            {"line": 10, "category": "click", "name": "z.click", "_ingest_index": 2},
        ]
        m = compute_sequence_metrics(events)
        self.assertEqual(m["max_consecutive_identical_action"], 1)
        self.assertEqual(m["repeat_action_fraction"], 0.0)

    def test_missing_line_sorts_after_known_lines(self):
        events = [
            {"line": 5, "category": "click", "name": "a", "_ingest_index": 0},
            {"line": None, "category": "click", "name": "b", "_ingest_index": 1},
            {"line": 10, "category": "click", "name": "c", "_ingest_index": 2},
        ]
        m = compute_sequence_metrics(events)
        self.assertEqual(m["sequence_event_count"], 3)

    def test_navigation_to_different_urls_not_target_revisit(self):
        events = [
            {
                "line": 1,
                "category": "navigation",
                "name": "page.goto",
                "_ingest_index": 0,
                "navigation_target": "/a",
            },
            {
                "line": 2,
                "category": "navigation",
                "name": "page.goto",
                "_ingest_index": 1,
                "navigation_target": "/b",
            },
        ]
        m = compute_sequence_metrics(events)
        self.assertEqual(m["repeated_navigation_api_count"], 1)
        self.assertEqual(m["navigation_target_revisit_count"], 0)

    def test_v2_navigation_api_repeat_is_target_insensitive(self):
        v2_sig = (
            '{"v":2,"category":"navigation","terminal_action":"goto",'
            '"locator_strategy":"","input_channel":"","navigation_target":"/a"}'
        )
        v2_sig_b = v2_sig.replace('"/a"', '"/b"')
        events = [
            {
                "line": 1,
                "category": "navigation",
                "name": "page.goto",
                "_ingest_index": 0,
                "navigation_target": "/a",
                "action_signature_json": v2_sig,
            },
            {
                "line": 2,
                "category": "navigation",
                "name": "page.goto",
                "_ingest_index": 1,
                "navigation_target": "/b",
                "action_signature_json": v2_sig_b,
            },
        ]
        m = compute_sequence_metrics(events)
        self.assertEqual(m["repeated_navigation_api_count"], 1)
        self.assertEqual(m["navigation_target_revisit_count"], 0)

    def test_navigation_target_revisit(self):
        events = [
            {
                "line": 1,
                "category": "navigation",
                "name": "page.goto",
                "_ingest_index": 0,
                "navigation_target": "/home",
            },
            {
                "line": 2,
                "category": "click",
                "name": "page.click",
                "_ingest_index": 1,
            },
            {
                "line": 3,
                "category": "navigation",
                "name": "page.goto",
                "_ingest_index": 2,
                "navigation_target": "/home",
            },
        ]
        m = compute_sequence_metrics(events)
        self.assertEqual(m["navigation_target_revisit_count"], 1)


class TestResolveNavigationTargetFields(unittest.TestCase):
    def test_navigation_api_literal_arg_basis(self):
        target, basis = resolve_navigation_target_fields("await page.goto('/login')")
        self.assertEqual(target, "/login")
        self.assertEqual(basis, "navigation_api_literal_arg")

    def test_dynamic_template_literal_not_extractable(self):
        target, basis = resolve_navigation_target_fields("page.goto(`/users/${id}`)")
        self.assertEqual(target, "")
        self.assertEqual(basis, "dynamic_template_literal")

    def test_path_case_preserved(self):
        target, basis = resolve_navigation_target_fields("page.goto('/Admin')")
        self.assertEqual(target, "/Admin")
        self.assertEqual(basis, "navigation_api_literal_arg")

    def test_not_extractable(self):
        target, basis = resolve_navigation_target_fields("page.goto(baseUrl)")
        self.assertEqual(target, "")
        self.assertEqual(basis, "not_extractable")

    def test_http_method_literal_rejected(self):
        target, basis = resolve_navigation_target_fields("cy.request('POST', '/api/x')")
        self.assertEqual(target, "")
        self.assertEqual(basis, "not_extractable")

    def test_http_method_case_insensitive(self):
        target, basis = resolve_navigation_target_fields('fetch("get", url)')
        self.assertEqual(target, "")
        self.assertEqual(basis, "not_extractable")

    def test_different_case_paths_not_target_revisit(self):
        events = [
            {
                "line": 1,
                "category": "navigation",
                "name": "page.goto",
                "_ingest_index": 0,
                "navigation_target": "/Admin",
                "navigation_target_evidence_basis": "navigation_api_literal_arg",
            },
            {
                "line": 2,
                "category": "navigation",
                "name": "page.goto",
                "_ingest_index": 1,
                "navigation_target": "/admin",
                "navigation_target_evidence_basis": "navigation_api_literal_arg",
            },
        ]
        m = compute_sequence_metrics(events)
        self.assertEqual(m["navigation_target_revisit_count"], 0)


class TestUserActionRepeatMetrics(unittest.TestCase):
    def test_excludes_locator_query_from_user_action_repeat(self):
        events = [
            {"line": 1, "category": "locator_query", "name": "page.locator", "_ingest_index": 0},
            {"line": 2, "category": "locator_query", "name": "page.locator", "_ingest_index": 1},
            {"line": 3, "category": "locator_query", "name": "page.locator", "_ingest_index": 2},
            {"line": 3, "category": "wait_synchronization", "name": "page.waitForTimeout", "_ingest_index": 3},
            {"line": 3, "category": "unknown_action", "name": "page.evaluate", "_ingest_index": 4},
            {"line": 4, "category": "keyboard_input", "name": "page.keyboard.press", "_ingest_index": 5},
            {"line": 5, "category": "click", "name": "page.click", "_ingest_index": 6},
        ]
        m = compute_sequence_metrics(events)
        self.assertEqual(m["repeat_action_fraction"], round(3 / 7, 6))
        self.assertEqual(m["max_consecutive_identical_action"], 3)
        self.assertEqual(m["user_action_event_count"], 4)
        self.assertEqual(m["classified_user_action_event_count"], 2)
        self.assertEqual(m["user_action_repeat_fraction"], 0.0)
        self.assertEqual(m["classified_user_action_repeat_fraction"], 0.0)
        self.assertEqual(m["user_action_max_consecutive_identical_action"], 1)
        self.assertEqual(m["classified_user_action_max_consecutive_identical_action"], 1)

    def test_user_action_repeat_detects_consecutive_clicks(self):
        events = [
            {"line": 1, "category": "locator_query", "name": "cy.get", "_ingest_index": 0},
            {"line": 2, "category": "click", "name": "cy.click", "_ingest_index": 1},
            {"line": 3, "category": "click", "name": "cy.click", "_ingest_index": 2},
        ]
        m = compute_sequence_metrics(events)
        self.assertEqual(m["user_action_repeat_fraction"], 1.0)
        self.assertEqual(m["user_action_max_consecutive_identical_action"], 2)


class TestDualScopeMetrics(unittest.TestCase):
    def test_test_body_prefix(self):
        all_events = [
            {"line": 1, "category": "click", "name": "a", "_ingest_index": 0},
            {"line": 2, "category": "click", "name": "a", "_ingest_index": 1},
        ]
        body_events = [{"line": 1, "category": "click", "name": "a", "_ingest_index": 0}]
        m = compute_dual_scope_sequence_metrics(all_events, body_events)
        self.assertEqual(m["sequence_event_count"], 2)
        self.assertEqual(m["test_body_sequence_event_count"], 1)
        self.assertEqual(m["sequence_all_layers_includes_non_test_body_events"], 1)
        self.assertEqual(m["sequence_scope_all_layers_approximate"], 1)

    def test_test_body_only_not_marked_approximate(self):
        events = [{"line": 1, "category": "click", "name": "a", "_ingest_index": 0}]
        m = compute_dual_scope_sequence_metrics(events, events)
        self.assertEqual(m["sequence_all_layers_includes_non_test_body_events"], 0)
        self.assertEqual(m["sequence_scope_all_layers_approximate"], 0)


if __name__ == "__main__":
    unittest.main()
