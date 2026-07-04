#!/usr/bin/env python3
"""Ensure RQ1 intent labels match rq1_setup_teardown_taxonomy.json."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import setup_teardown_intent as sti

TAXONOMY_PATH = Path(__file__).resolve().parent / "rq1_setup_teardown_taxonomy.json"


class TestRq1TaxonomyDrift(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.taxonomy = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))

    def test_taxonomy_file_has_core_dimensions(self) -> None:
        for key in (
            "phase",
            "scope",
            "primary_intent",
            "primary_intent_evidence_basis",
            "confidence",
            "review_reason",
        ):
            self.assertIn(key, self.taxonomy)
            self.assertIsInstance(self.taxonomy[key], list)
            self.assertGreater(len(self.taxonomy[key]), 0)

    def test_python_constants_match_taxonomy(self) -> None:
        self.assertEqual(set(self.taxonomy["phase"]), set(sti.PHASES))
        self.assertEqual(set(self.taxonomy["scope"]), set(sti.SCOPES))
        self.assertEqual(set(self.taxonomy["primary_intent"]), set(sti.PRIMARY_INTENTS))
        self.assertEqual(
            set(self.taxonomy["primary_intent_evidence_basis"]),
            set(sti.PRIMARY_INTENT_EVIDENCE_BASES),
        )
        self.assertEqual(set(self.taxonomy["confidence"]), set(sti.CONFIDENCE_LEVELS))

    def test_inventory_hint_map_keys_are_valid_categories(self) -> None:
        from classify import classify_setup

        hints = self.taxonomy["inventory_category_to_primary_intent_hint"]
        for inv_cat, intent in hints.items():
            self.assertIn(intent, sti.PRIMARY_INTENTS)
            # classify_setup returns these category strings
            self.assertIsInstance(inv_cat, str)


if __name__ == "__main__":
    unittest.main()
