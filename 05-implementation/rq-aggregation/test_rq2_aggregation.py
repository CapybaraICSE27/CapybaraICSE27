#!/usr/bin/env python3
"""Integration tests for RQ2 aggregation output."""

from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from aggregate import Aggregator


class TestRq2Aggregation(unittest.TestCase):
    def test_llm_metadata_fields_are_preserved_in_event_schemas(self) -> None:
        for field in ("llm_model", "llm_prompt_version", "llm_input_hash"):
            self.assertIn(field, Aggregator.RQ2_FIELDS)
            self.assertIn(field, Aggregator.RQ5_FIELDS)

    def test_input_event_inherits_structured_context_from_companion_ui_action(self) -> None:
        test_cases = {
            "acme/repo::t1": {
                "repo": "acme/repo",
                "test_id": "t1",
                "framework": "Cypress",
                "phase1_confidence": "high",
            }
        }
        raw = 'cy.get(googleForm.googleClientId).type(Cypress.env("CLIENT_ID"))'
        features = [
            {
                "repo": "acme/repo",
                "test_id": "t1",
                "feature_type": "ui_action",
                "source_kind": "test_body",
                "name": "cy.get(...).type",
                "raw_code": raw,
                "line": 12,
                "helper_depth": 0,
                "input_target_role_ast": "credential_or_config_field",
                "input_target_role_basis_ast": "ast_locator_target_context",
                "input_target_context_ast": "googleForm.googleClientId",
                "input_target_context_normalized_ast": "google Form google Client Id",
                "input_target_context_basis_ast": "get",
                "input_value_expression_kind_ast": "call_expression",
            },
            {
                "repo": "acme/repo",
                "test_id": "t1",
                "feature_type": "input",
                "source_kind": "test_body",
                "name": "input:type:Cypress.env",
                "raw_code": raw,
                "line": 12,
                "helper_depth": 0,
                "linked_action_line": 12,
                "input_source_ast": "environment_input",
                "input_value_redacted": 'Cypress.env("CLIENT_ID")',
                "value_visibility_ast": "opaque",
                "input_channel_ast": "ui_text_entry",
                "input_evidence_basis_ast": "ast_value_argument",
            },
        ]

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            agg = Aggregator(test_cases, out)
            for feature in features:
                agg.ingest_feature(feature)
            agg.close_event_sinks()
            agg.finalize()

            with (out / "rq2_input_events.csv").open(encoding="utf-8", newline="") as f:
                row = list(csv.DictReader(f))[0]

        self.assertEqual(row["input_target_role_ast"], "credential_or_config_field")
        self.assertEqual(row["input_target_context_ast"], "googleForm.googleClientId")
        self.assertEqual(row["input_value_expression_kind_ast"], "call_expression")
        self.assertEqual(row["input_plausibility"], "domain_plausible_input")

    def test_indeterminate_adjudication_rows_are_buffered_even_without_first_pass_trigger(self) -> None:
        class FakeSink:
            def __init__(self):
                self.rows = []

            def write(self, row):
                self.rows.append(row)

        class FakeCorrector:
            enabled = True
            dry_run = False

            def __init__(self):
                self.rows_seen = []

            def correct_many(self, rq, rows):
                self.rows_seen.extend(rows)
                return [
                    {
                        **row,
                        "input_plausibility_final": "domain_plausible_input",
                        "input_plausibility_final_basis": "llm_indeterminate_adjudication",
                    }
                    for row in rows
                ]

        agg = Aggregator({}, Path(tempfile.gettempdir()), llm_corrector=FakeCorrector())
        sink = FakeSink()
        written = []
        row = {
            "input_plausibility": "unclear",
            "input_plausibility_confidence": "medium",
            "input_plausibility_paper_label": "indeterminate_or_insufficient_evidence",
            "input_source_class": "literal_input",
            "input_channel": "ui_text_entry",
            "value_visibility": "visible",
            "value_summary": "Payments",
            "input_target_role_ast": "unknown",
            "input_value_expression_kind_ast": "string_literal",
            "raw_code": "cy.focused().type(`Payments`)",
        }

        agg._write_or_buffer_semantic_event("rq2", row, sink, written.append)
        self.assertEqual(sink.rows, [])
        agg._flush_semantic_event_buffers()

        self.assertEqual(len(agg.llm_corrector.rows_seen), 1)
        self.assertEqual(sink.rows[0]["input_plausibility_final"], "domain_plausible_input")
        self.assertEqual(written[0]["input_plausibility_final_basis"], "llm_indeterminate_adjudication")


if __name__ == "__main__":
    unittest.main()
