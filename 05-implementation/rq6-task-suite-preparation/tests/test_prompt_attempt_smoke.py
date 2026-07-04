#!/usr/bin/env python3
"""Unit tests for the RQ6 prompt-attempt smoke runner."""

from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from types import ModuleType


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "11_run_prompt_attempt_smoke.py"
)


def load_runner() -> ModuleType:
    spec = importlib.util.spec_from_file_location("rq6_prompt_attempt_smoke", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestPromptAttemptSmoke(unittest.TestCase):
    def test_mask_hidden_reference_test_replaces_only_target_block(self) -> None:
        runner = load_runner()
        source = "\n".join(
            [
                "test.describe('events', () => {",
                "\ttest('triggers custom dom events on document', async ({ page }) => {",
                "\t\texpect(true).toBe(true);",
                "\t});",
                "\ttest('custom dom events bubble to window', async ({ page }) => {",
                "\t\tawait page.evaluate(() => {",
                "\t\t\twindow.addEventListener(",
                "\t\t\t\t'swup:link:click',",
                "\t\t\t\t(event: any) => (window.data = event.detail.hook)",
                "\t\t\t);",
                "\t\t});",
                "\t\tawait clickOnLink(page, '/page-2.html');",
                "\t\texpect(await page.evaluate(() => window.data)).toStrictEqual('link:click');",
                "\t});",
                "\ttest('triggers dom events for \"swup:any\"', async ({ page }) => {",
                "\t\texpect(true).toBe(true);",
                "\t});",
                "});",
            ]
        )

        masked, changed = runner.mask_hidden_reference_test(source)

        self.assertTrue(changed)
        self.assertIn("test.skip('custom dom events bubble to window'", masked)
        self.assertIn("hidden RQ6 reference test masked", masked)
        self.assertIn("triggers custom dom events on document", masked)
        self.assertIn('triggers dom events for "swup:any"', masked)
        self.assertNotIn("clickOnLink(page, '/page-2.html')", masked)
        self.assertNotIn("window.data = event.detail.hook", masked)

    def test_default_attempts_cover_high_medium_low_prompts_and_tests(self) -> None:
        runner = load_runner()

        self.assertEqual(set(runner.PROMPTS), {"high", "medium", "low"})
        self.assertEqual(set(runner.GENERATED_TESTS), {"high", "medium", "low"})
        self.assertIn("--project chromium", runner.DEFAULT_VERIFICATION_COMMAND)
        self.assertIn("Swup exposes", runner.PROMPTS["high"])
        self.assertIn("`link:click`", runner.PROMPTS["medium"])
        self.assertIn("swup:link:click", runner.PROMPTS["low"])
        self.assertIn("page.getByTestId('link-to-page-2').click()", runner.GENERATED_TESTS["high"])
        self.assertIn("_swup.hooks.on('link:click'", runner.GENERATED_TESTS["medium"])
        self.assertIn("page.getByTestId('link-to-page-2').click()", runner.GENERATED_TESTS["medium"])
        self.assertIn("window.addEventListener('swup:link:click'", runner.GENERATED_TESTS["low"])
        self.assertIn("page.getByTestId('link-to-page-2').click()", runner.GENERATED_TESTS["low"])

    def test_replace_text_file_breaks_hardlink_before_writing(self) -> None:
        runner = load_runner()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source.txt"
            linked = root / "linked.txt"
            source.write_text("original")
            try:
                os.link(source, linked)
            except OSError:
                self.skipTest("hardlinks are not supported on this filesystem")

            runner.replace_text_file(linked, "changed")

            self.assertEqual(source.read_text(), "original")
            self.assertEqual(linked.read_text(), "changed")

    def test_copy_attempt_workdir_allows_safe_replacement(self) -> None:
        runner = load_runner()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            base = root / "base"
            dest = root / "dest"
            nested = base / "tests" / "functional"
            nested.mkdir(parents=True)
            source_file = nested / "events.spec.ts"
            source_file.write_text("original")

            runner.copy_attempt_workdir(base, dest, overwrite=False)

            copied_file = dest / "tests" / "functional" / "events.spec.ts"
            self.assertEqual(copied_file.read_text(), "original")
            runner.replace_text_file(copied_file, "changed")
            self.assertEqual(source_file.read_text(), "original")
            self.assertEqual(copied_file.read_text(), "changed")

    def test_copy_attempt_workdir_dereferences_base_symlink(self) -> None:
        runner = load_runner()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            real_base = root / "real_base"
            base_link = root / "base_link"
            dest = root / "dest"
            nested = real_base / "tests" / "functional"
            nested.mkdir(parents=True)
            source_file = nested / "events.spec.ts"
            source_file.write_text("original")
            base_link.symlink_to(real_base, target_is_directory=True)

            runner.copy_attempt_workdir(base_link, dest, overwrite=False)

            copied_file = dest / "tests" / "functional" / "events.spec.ts"
            self.assertFalse(dest.is_symlink())
            self.assertEqual(copied_file.read_text(), "original")
            runner.replace_text_file(copied_file, "changed")
            self.assertEqual(source_file.read_text(), "original")
            self.assertEqual(copied_file.read_text(), "changed")

    def test_in_place_attempt_restores_reference_source(self) -> None:
        runner = load_runner()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            base = root / "base"
            source_dir = base / "tests" / "functional"
            source_dir.mkdir(parents=True)
            source_file = source_dir / "events.spec.ts"
            reference = root / "events.reference.ts"
            reference_text = "\n".join(
                [
                    "test.describe('events', () => {",
                    "\ttest('custom dom events bubble to window', async ({ page }) => {",
                    "\t\tawait page.evaluate(() => {});",
                    "\t});",
                    "\ttest('next test', async () => {});",
                    "});",
                ]
            )
            source_file.write_text(reference_text)
            reference.write_text(reference_text)

            row = runner.run_one_attempt(
                level="low",
                base_workdir=base,
                out_dir=root / "out",
                in_place_base_workdir=True,
                reference_source_file=reference,
                agent_test_file=Path("tests/functional/rq6-agent/rq6_0001.spec.ts"),
                verification_command="python3 -c \"print('ok')\"",
                overwrite=True,
            )

            self.assertEqual(row["status"], "passed")
            self.assertTrue(row["reference_test_masked"])
            self.assertEqual(source_file.read_text(), reference_text)
            self.assertTrue((root / "out" / "low" / "generated_test.ts").is_file())


if __name__ == "__main__":
    unittest.main()
