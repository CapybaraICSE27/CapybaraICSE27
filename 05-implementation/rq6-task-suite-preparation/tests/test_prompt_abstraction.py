#!/usr/bin/env python3
"""Unit tests for RQ6 prompt abstraction levels."""

from __future__ import annotations

import unittest
import importlib.util
import tempfile
from pathlib import Path
from types import ModuleType
import sys

LIB = Path(__file__).resolve().parents[1] / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

from prompt_abstraction import build_prompt_variants  # noqa: E402

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


def load_task_suite_builder() -> ModuleType:
    spec = importlib.util.spec_from_file_location("rq6_task_suite_builder", TASK_SUITE_SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_masking_validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("rq6_masking_validator", MASKING_SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sample_task() -> dict:
    return {
        "task_id": "rq6_0001",
        "repo_full_name": "example/project",
        "framework": "playwright",
        "agent_test_file": "tests/rq6-agent/rq6_0001.spec.ts",
        "verification_command": "pnpm exec playwright test tests/rq6-agent/rq6_0001.spec.ts --reporter=json",
    }


def sample_workflow() -> dict:
    return {
        "workflow": {
            "goal": "Navigation: keeps the active page after link transition",
            "actions": [
                {
                    "type": "navigate",
                    "target_hint": "the docs getting started view",
                    "prompt_safe_detail": "/docs/getting-started",
                    "source_layer": "source_review",
                },
                {
                    "type": "click",
                    "target_hint": "a user-facing navigation link",
                    "prompt_safe_detail": "Getting started",
                    "source_layer": "source_review",
                },
            ],
            "setup": [{"kind": "event observer setup", "count": 1}],
            "assertions": [
                {
                    "kind": "URL assertion",
                    "intent": "browser URL changes to the expected page",
                    "prompt_safe_detail": "the address ends with /docs/getting-started",
                }
            ],
        }
    }


class TestPromptAbstraction(unittest.TestCase):
    def test_builds_three_prompt_variants_for_one_task(self) -> None:
        variants = build_prompt_variants(sample_task(), sample_workflow())

        self.assertEqual([row["prompt_level"] for row in variants], ["high", "medium", "low"])
        self.assertEqual({row["task_id"] for row in variants}, {"rq6_0001"})
        self.assertEqual(
            {row["prompt_id"] for row in variants},
            {"rq6_0001__high", "rq6_0001__medium", "rq6_0001__low"},
        )

    def test_high_prompt_omits_low_level_route_and_workflow_steps(self) -> None:
        high = build_prompt_variants(sample_task(), sample_workflow())[0]["prompt"]

        self.assertIn("Create one new Playwright UI test", high)
        self.assertIn("Navigation", high)
        self.assertNotIn("/docs/getting-started", high)
        self.assertNotIn("Getting started", high)
        self.assertNotIn("High-level workflow clues", high)
        self.assertNotIn("expect(", high)
        self.assertNotIn("data-testid", high)

    def test_medium_prompt_includes_user_workflow_without_code_or_selectors(self) -> None:
        medium = build_prompt_variants(sample_task(), sample_workflow())[1]["prompt"]

        self.assertIn("User workflow", medium)
        self.assertIn("navigate to the docs getting started view", medium)
        self.assertIn("click a user-facing navigation link", medium)
        self.assertIn("Expected result", medium)
        self.assertNotIn("page.goto(", medium)
        self.assertNotIn("expect(", medium)
        self.assertNotIn("data-testid", medium)
        self.assertNotIn("/docs/getting-started", medium)

    def test_medium_prompt_uses_goal_when_assertion_intent_is_generic(self) -> None:
        workflow = sample_workflow()
        workflow["workflow"]["goal"] = "events: custom DOM events bubble to window"
        workflow["workflow"]["assertions"] = [
            {
                "kind": "observable assertion",
                "intent": "expected browser or UI behavior occurs",
            }
        ]

        medium = build_prompt_variants(sample_task(), workflow)[1]["prompt"]

        self.assertIn(
            "Expected result: verify that events: custom DOM events bubble to window.",
            medium,
        )

    def test_prompt_levels_prefer_rich_prompt_semantics(self) -> None:
        workflow = {
            "workflow": {
                "goal": "events: custom DOM events bubble to window",
                "actions": [
                    {
                        "type": "click",
                        "target_hint": "a navigation link",
                        "source_layer": "source_review",
                    }
                ],
                "setup": [{"kind": "event or hook observer setup", "count": 1}],
                "assertions": [
                    {
                        "kind": "observable assertion",
                        "intent": "expected browser or UI behavior occurs",
                    }
                ],
                "prompt_semantics": {
                    "scenario_summary": "custom DOM events bubble to the window after navigation",
                    "preconditions": [
                        {
                            "text": "register a page-level or window-level event observer",
                            "evidence_basis": "source_event_listener_or_hook",
                            "confidence": "high",
                        }
                    ],
                    "user_workflow_steps": [
                        {
                            "text": "trigger navigation through a visible or internal navigation link",
                            "safe_detail": "the interaction should cause the app to emit a custom DOM event",
                            "evidence_basis": "source_named_click_helper",
                            "confidence": "high",
                        }
                    ],
                    "expected_results": [
                        {
                            "observable_outcome": "a page-level or window-level observer receives the custom event after the interaction",
                            "observation_channel": "event",
                            "evidence_basis": "source_event_listener_or_hook",
                            "confidence": "high",
                        }
                    ],
                    "semantic_confidence": "high",
                    "needs_manual_review": False,
                },
            }
        }

        high, medium, low = [row["prompt"] for row in build_prompt_variants(sample_task(), workflow)]

        self.assertIn("custom DOM events bubble to the window after navigation", high)
        self.assertIn("page-level or window-level observer receives the custom event", high)
        self.assertNotIn("trigger navigation through", high)
        self.assertIn("register a page-level or window-level event observer", medium)
        self.assertIn("trigger navigation through a visible or internal navigation link", medium)
        self.assertIn("page-level or window-level observer receives the custom event", medium)
        self.assertIn("the interaction should cause the app to emit a custom DOM event", low)
        self.assertNotIn("expected browser or UI behavior occurs", medium)

    def test_low_prompt_can_include_prompt_safe_details_but_not_code(self) -> None:
        low = build_prompt_variants(sample_task(), sample_workflow())[2]["prompt"]

        self.assertIn("/docs/getting-started", low)
        self.assertIn("Getting started", low)
        self.assertIn("the address ends with /docs/getting-started", low)
        self.assertNotIn("page.goto(", low)
        self.assertNotIn("expect(", low)
        self.assertNotIn("data-testid", low)

    def test_task_suite_builder_writes_prompt_variants_for_one_task(self) -> None:
        builder = load_task_suite_builder()
        task_spec = sample_task()

        with tempfile.TemporaryDirectory() as td:
            out_dir = Path(td)
            prompt = builder.write_prompt_artifacts(out_dir, task_spec, sample_workflow())

            self.assertEqual(prompt, task_spec["prompt"])
            self.assertIn("User workflow", prompt)
            variants_path = out_dir / "agent_prompt_variants.jsonl"
            self.assertTrue(variants_path.exists())
            lines = variants_path.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 3)
            self.assertTrue((out_dir / "prompts" / "high" / "rq6_0001_prompt.md").exists())
            self.assertTrue((out_dir / "prompts" / "medium" / "rq6_0001_prompt.md").exists())
            self.assertTrue((out_dir / "prompts" / "low" / "rq6_0001_prompt.md").exists())

    def test_masking_validator_loads_medium_spec_and_prompt_variants(self) -> None:
        builder = load_task_suite_builder()
        validator = load_masking_validator()
        task_spec = sample_task()

        with tempfile.TemporaryDirectory() as td:
            suite = Path(td)
            builder.write_prompt_artifacts(suite, task_spec, sample_workflow())
            builder.write_jsonl(suite / "agent_task_specs.jsonl", [task_spec])

            loaded = validator.load_prompt_task_rows(suite)

        self.assertEqual(len(loaded), 4)
        self.assertEqual(
            [row.get("prompt_level") for row in loaded],
            ["medium", "high", "medium", "low"],
        )
        self.assertEqual(loaded[0]["prompt_id"], "rq6_0001__primary_medium")
        self.assertEqual(loaded[1]["prompt_id"], "rq6_0001__high")


if __name__ == "__main__":
    unittest.main()
