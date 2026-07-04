#!/usr/bin/env python3
"""Regression tests for static URL extraction from navigation raw_code."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from navigationMetrics import (
    compute_navigation_by_test,
    extract_static_urls_from_raw,
    resolve_navigation_feature_paths,
    safe_repo_dir,
)


class TestExtractStaticUrls(unittest.TestCase):
    def test_goto_with_options_object(self) -> None:
        raw = "page.goto('/get-query', { waitUntil: 'networkidle' })"
        urls, dynamic = extract_static_urls_from_raw(raw)
        self.assertIn("/get-query", urls)
        self.assertFalse(dynamic)

    def test_cy_visit_with_options_object(self) -> None:
        raw = (
            "cy.visit('http://127.0.0.1:6006/iframe.html?id=slider--controlled', "
            "{ onBeforeLoad(win) { cy.stub(win.console, 'log'); } })"
        )
        urls, dynamic = extract_static_urls_from_raw(raw)
        self.assertTrue(any("127.0.0.1" in u for u in urls))
        self.assertFalse(dynamic)

    def test_cy_visit_with_second_argument(self) -> None:
        raw = "cy.visit('/', authSetup)"
        urls, dynamic = extract_static_urls_from_raw(raw)
        self.assertIn("/", urls)
        self.assertFalse(dynamic)

    def test_dynamic_variable_first_argument(self) -> None:
        raw = "page.goto(dynamicUrl)"
        urls, dynamic = extract_static_urls_from_raw(raw)
        self.assertEqual(urls, set())
        self.assertTrue(dynamic)

    def test_full_run_without_global_files_falls_back_to_sidecars(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            run = Path(td)
            per_repo = run / "per_repo_outputs"
            per_repo.mkdir()
            repos = {f"Owner/repo{i}" for i in range(121)}
            target = "Owner/repo120"
            p = per_repo / f"{safe_repo_dir(target)}.features_direct.jsonl"
            p.write_text(
                json.dumps(
                    {
                        "repo": target,
                        "test_id": "t1",
                        "feature_type": "ui_action",
                        "name": "page.goto",
                        "raw_code": "page.goto('/dashboard')",
                        "line": 7,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            paths, source = resolve_navigation_feature_paths(run, repos)
            self.assertEqual(source, "per_repo_sidecars_fallback")
            self.assertEqual(paths, [p])

            nav = compute_navigation_by_test(run, repos_filter=repos)
            self.assertEqual(nav[f"{target}::t1"]["estimated_page_or_view_count"], 1)
            self.assertEqual(nav[f"{target}::t1"]["navigation_action_count"], 1)

    def test_global_files_preferred_for_full_run_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            run = Path(td)
            per_repo = run / "per_repo_outputs"
            per_repo.mkdir()
            sidecar = per_repo / "Owner__repo.features_direct.jsonl"
            sidecar.write_text("", encoding="utf-8")
            global_path = run / "test_case_features_direct.jsonl"
            global_path.write_text("", encoding="utf-8")

            paths, source = resolve_navigation_feature_paths(
                run,
                {f"Owner/repo{i}" for i in range(121)},
            )
            self.assertEqual(source, "global_merged")
            self.assertEqual(paths, [global_path])


if __name__ == "__main__":
    unittest.main()
