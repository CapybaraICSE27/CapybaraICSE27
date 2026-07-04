#!/usr/bin/env python3
"""Ensure RQ3 emitted labels match rq3_taxonomy.json (drift gate for CI)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pattern_classify as pc

TAXONOMY_PATH = Path(__file__).resolve().parent / "rq3_taxonomy.json"


def load_taxonomy() -> dict:
    return json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))


class TestTaxonomyDrift(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.taxonomy = load_taxonomy()

    def test_taxonomy_file_has_core_dimensions(self) -> None:
        for key in (
            "locator_strategy",
            "locator_composition",
            "sync_pattern",
            "workflow_abstraction",
            "workflow_archetype",
            "robustness_signal",
            "interaction_ownership",
            "reuse_scope",
        ):
            self.assertIn(key, self.taxonomy)
            self.assertIsInstance(self.taxonomy[key], list)
            self.assertGreater(len(self.taxonomy[key]), 0)

    def test_classifier_constants_subset_of_taxonomy(self) -> None:
        tax = self.taxonomy
        self.assertTrue(set(pc.LOCATOR_STRATEGIES) <= set(tax["locator_strategy"]))
        self.assertTrue(set(pc.LOCATOR_COMPOSITIONS) <= set(tax["locator_composition"]))
        self.assertTrue(set(pc.SYNC_PATTERNS) <= set(tax["sync_pattern"]))
        self.assertTrue(set(pc.ABSTRACTION_KINDS) <= set(tax["workflow_abstraction"]))
        self.assertTrue(set(pc.WORKFLOW_ARCHETYPES) <= set(tax["workflow_archetype"]))
        self.assertTrue(set(pc.INTERACTION_OWNERSHIP) <= set(tax["interaction_ownership"]))
        self.assertTrue(set(pc.REUSE_SCOPE) <= set(tax["reuse_scope"]))
        self.assertTrue(set(pc.ROBUSTNESS_SIGNALS) <= set(tax["robustness_signal"]))
        self.assertTrue(set(pc.EVIDENCE_BASIS) <= set(tax["evidence_basis"]))
        self.assertTrue(set(pc.SYNC_EVIDENCE_BASIS) <= set(tax["evidence_basis"]))

    def test_sync_ast_subtypes_not_emitted_as_primary_sync(self) -> None:
        """AST delay subtypes are documented separately from emitted sync_pattern labels."""
        primary = set(self.taxonomy["sync_pattern"])
        subtypes = set(self.taxonomy.get("sync_pattern_ast_subtype", []))
        self.assertTrue(subtypes.isdisjoint(primary))
        self.assertTrue(subtypes.isdisjoint(set(pc.SYNC_PATTERNS)))

    def test_workflow_archetypes_in_infer(self) -> None:
        allowed = set(self.taxonomy["workflow_archetype"])
        arch = pc.infer_workflow_archetype(
            ui_action_count=5,
            test_body_ui=5,
            hook_ui=0,
            helper_ui=0,
            po_ui=0,
            cypress_cmd_ui=0,
            page_object_signal=False,
            helper_call_count=0,
            unresolved_helper_calls=0,
            expanded_ui_count=0,
        )
        self.assertIn(arch, allowed)

    def test_resolve_locator_emits_taxonomy_labels(self) -> None:
        allowed_strategy = set(self.taxonomy["locator_strategy"])
        allowed_comp = set(self.taxonomy["locator_composition"])
        r = pc.resolve_locator_pattern(
            "page.getByRole",
            "await page.getByRole('button').click()",
            "Playwright",
            "test_body",
            0,
            "ui_action",
            "click",
            {},
        )
        self.assertIn(r["locator_strategy"], allowed_strategy)
        self.assertIn(r["locator_composition"], allowed_comp)

    def test_resolve_workflow_emits_taxonomy_ownership_labels(self) -> None:
        allowed_ownership = set(self.taxonomy["interaction_ownership"])
        allowed_reuse = set(self.taxonomy["reuse_scope"])
        r = pc.resolve_workflow_pattern(
            "authenticatedPage",
            "async ({ authenticatedPage }) => {}",
            "Playwright",
            "test_body",
            0,
            "ui_action",
            "",
            True,
            attached_hook=False,
            feature={
                "fixture_param_name": "authenticatedPage",
                "workflow_kind_ast": "playwright_fixture",
            },
        )
        self.assertIn(r["interaction_ownership"], allowed_ownership)
        self.assertIn(r["reuse_scope"], allowed_reuse)

    def test_cypress_command_roles_defined(self) -> None:
        self.assertIn("workflow_abstraction", self.taxonomy["cypress_command_role"])
        self.assertIn("session_setup", self.taxonomy["cypress_command_role"])


if __name__ == "__main__":
    unittest.main()
