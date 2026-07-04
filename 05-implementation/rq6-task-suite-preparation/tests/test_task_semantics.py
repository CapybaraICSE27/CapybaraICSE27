#!/usr/bin/env python3
"""Unit tests for RQ6 source-review semantic enrichment."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from types import ModuleType

LIB = Path(__file__).resolve().parents[1] / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

from task_semantics import extract_source_review_semantics  # noqa: E402

TASK_SUITE_SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "08_build_phase2_task_suite.py"
)
MASKING_SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "09_validate_phase2_masking.py"
)


def load_script(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestTaskSemantics(unittest.TestCase):
    def test_event_bubbling_source_review_produces_prompt_semantics(self) -> None:
        snippet = """
        10: test("custom DOM events bubble to window", async ({ page }) => {
        11:   const events = []
        12:   await page.exposeBinding("eventCallback", (_, eventName) => events.push(eventName))
        13:   await page.evaluate(() => window.addEventListener("swup:any", event => window.eventCallback(event.type)))
        14:   await clickOnLink(page, "/page-2")
        15:   await expect.poll(() => events).toContain("swup:any")
        16: })
        """

        semantics = extract_source_review_semantics(
            snippet,
            "custom DOM events bubble to window",
            ["events"],
        )

        prompt_semantics = semantics["prompt_semantics"]
        self.assertEqual(
            prompt_semantics["scenario_summary"],
            "events: custom DOM events bubble to window",
        )
        self.assertEqual(prompt_semantics["semantic_confidence"], "high")
        self.assertFalse(prompt_semantics["needs_manual_review"])
        self.assertIn(
            "register a page-level or window-level event observer",
            [item["text"] for item in prompt_semantics["preconditions"]],
        )
        self.assertIn(
            "trigger navigation through a visible or internal navigation link",
            [item["text"] for item in prompt_semantics["user_workflow_steps"]],
        )
        self.assertIn(
            "a page-level or window-level observer receives the custom event after the interaction",
            [item["observable_outcome"] for item in prompt_semantics["expected_results"]],
        )
        self.assertIn("custom DOM event", prompt_semantics["prompt_safe_terms"])
        self.assertIn("clickOnLink", prompt_semantics["blocked_terms"])
        self.assertIn("exposeBinding", prompt_semantics["blocked_terms"])

    def test_generic_expected_result_keeps_low_confidence_even_with_clear_action(self) -> None:
        snippet = """
        20: test("updates the visible state", async ({ page }) => {
        21:   await page.click("#toggle")
        22:   expect(await page.evaluate(() => window.__state)).toBeTruthy()
        23: })
        """

        semantics = extract_source_review_semantics(snippet, "updates the visible state", [])

        prompt_semantics = semantics["prompt_semantics"]
        self.assertEqual(prompt_semantics["semantic_confidence"], "low")
        self.assertTrue(prompt_semantics["needs_manual_review"])
        self.assertEqual(
            prompt_semantics["expected_results"][0]["evidence_basis"],
            "source_title_derived_from_generic_assertion",
        )

    def test_masking_validator_blocks_semantic_terms_and_warns_on_low_confidence(self) -> None:
        validator = load_script("rq6_masking_validator", MASKING_SCRIPT)
        task = {
            "task_id": "rq6_0001",
            "prompt_id": "rq6_0001__low",
            "prompt_level": "low",
            "prompt": "Create the test by using clickOnLink for this workflow.",
        }
        packet = {
            "task_id": "rq6_0001",
            "draft_workflow": {
                "goal": "events: custom DOM events bubble to window",
                "prompt_semantics": {
                    "semantic_confidence": "low",
                    "needs_manual_review": True,
                    "expected_results": [],
                    "user_workflow_steps": [],
                    "blocked_terms": ["clickOnLink"],
                },
            },
            "source_snippet": "",
        }

        result = validator.validate_task(task, packet, {})
        findings = result["finding_codes"].split(";")

        self.assertEqual(result["mask_ok"], "needs_revision")
        self.assertIn("blocked_prompt_term", findings)
        self.assertIn("low_semantic_confidence", findings)
        self.assertIn("missing_semantic_expected_result", findings)
        self.assertIn("missing_semantic_user_workflow", findings)

    def test_review_row_includes_semantic_review_fields(self) -> None:
        builder = load_script("rq6_task_suite_builder", TASK_SUITE_SCRIPT)
        source_semantics = {
            "source_review_semantics_available": True,
            "prompt_semantics": {
                "semantic_confidence": "medium",
                "needs_manual_review": False,
                "expected_results": [{"observable_outcome": "the result is observable"}],
            },
            "actions": [{"type": "click"}],
            "notes": [],
        }
        workflow = {
            "workflow": {
                "actions": [{"type": "click"}],
                "assertions": [{"intent": "the result is observable"}],
                "phase2_extracted_actions": [{"type": "click"}],
                "waits": [],
                "prompt_semantics": source_semantics["prompt_semantics"],
            }
        }

        row = builder.build_review_row(
            task_id="rq6_0001",
            repo="example/project",
            source_file="tests/example.spec.ts",
            test_name="semantic task",
            start_line=1,
            end_line=5,
            source_available=True,
            extraction_available=True,
            workflow=workflow,
            prompt="Create one new Playwright UI test.",
            source_semantics=source_semantics,
            has_app_metadata=False,
            has_pretest_metadata=False,
            requires_app_metadata=False,
            requires_pretest_metadata=False,
        )

        self.assertEqual(row["semantic_confidence"], "medium")
        self.assertEqual(row["needs_manual_enrichment"], "no")
        self.assertEqual(row["purpose_preserved"], "yes")
        self.assertEqual(row["leakage_risk"], "low")
        self.assertEqual(row["ambiguity"], "low")
        self.assertEqual(row["expected_result_specificity"], "yes")


if __name__ == "__main__":
    unittest.main()
