#!/usr/bin/env python3
"""Ensure RQ2 emitted labels match rq2_taxonomy.json."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import input_classify as ic
import input_plausibility as ip

TAXONOMY_PATH = Path(__file__).resolve().parent / "rq2_taxonomy.json"


def load_taxonomy() -> dict:
    return json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))


class TestRq2TaxonomyDrift(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.taxonomy = load_taxonomy()

    def test_taxonomy_has_core_dimensions(self) -> None:
        for key in (
            "input_source_class",
            "input_plausibility",
            "value_visibility",
            "input_channel",
        ):
            self.assertIn(key, self.taxonomy)
            self.assertGreater(len(self.taxonomy[key]), 0)

    def test_classifier_constants_subset_of_taxonomy(self) -> None:
        tax = self.taxonomy
        self.assertTrue(set(ic.INPUT_SOURCE_CLASSES) <= set(tax["input_source_class"]))
        self.assertTrue(set(ip.INPUT_PLAUSIBILITY_LABELS) <= set(tax["input_plausibility"]))
        self.assertTrue(set(ic.VALUE_VISIBILITY) <= set(tax["value_visibility"]))
        self.assertTrue(set(ic.INPUT_CHANNELS) <= set(tax["input_channel"]))
        self.assertIn("missing_input_evidence_basis", tax["input_evidence_basis"])

    def test_resolve_input_emits_taxonomy_labels(self) -> None:
        allowed = set(self.taxonomy["input_source_class"])
        r = ic.resolve_input_pattern(
            "input:fill:alice@example.com",
            "await page.getByLabel('Email').fill('alice@example.com')",
            feature={
                "input_source_ast": "literal_input",
                "value_visibility_ast": "visible",
                "input_value_redacted": "alice@example.com",
                "field_context_ast": "Email",
            },
        )
        self.assertIn(r["input_source_class"], allowed)
        self.assertIn(
            r["input_plausibility"],
            set(self.taxonomy["input_plausibility"]),
        )


if __name__ == "__main__":
    unittest.main()
