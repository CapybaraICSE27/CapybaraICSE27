#!/usr/bin/env python3
"""Unit tests for classify_assertion() matcher coverage."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from assertion_semantics import classify_verification_intent, map_verification_intent
from classify import classify_assertion


class TestClassifyAssertion(unittest.TestCase):
    def test_to_have_value_maps_to_element_state(self):
        cat = classify_assertion("expect", "await expect(input).toHaveValue('foo')")
        self.assertEqual(cat, "element_state_oracle")
        self.assertEqual(
            classify_verification_intent(cat, "expect", "await expect(input).toHaveValue('foo')"),
            "value_or_attribute_correctness",
        )

    def test_to_be_hidden_maps_to_visibility(self):
        cat = classify_assertion("expect", "await expect(el).toBeHidden()")
        self.assertEqual(cat, "visibility_oracle")
        self.assertEqual(map_verification_intent(cat), "element_presence")

    def test_testcafe_exists_ok(self):
        cat = classify_assertion("selector", "await Selector('#x').exists.ok()")
        self.assertEqual(cat, "visibility_oracle")

    def test_testcafe_exists_not_ok(self):
        cat = classify_assertion("selector", "await Selector('#x').exists.notOk()")
        self.assertEqual(cat, "visibility_oracle")

    def test_to_be_null_maps_to_element_state(self):
        cat = classify_assertion("expect", "expect(value).toBeNull()")
        self.assertEqual(cat, "element_state_oracle")

    def test_href_equality_maps_to_url_navigation(self):
        cat = classify_assertion("expect", "expect(loc.href).to.eq('/dashboard')")
        self.assertEqual(cat, "url_navigation_oracle")
        self.assertEqual(map_verification_intent(cat), "navigation_outcome")


if __name__ == "__main__":
    unittest.main()
