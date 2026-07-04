#!/usr/bin/env python3
"""Unit tests for Phase 2D aggregation."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from classify import (
    classify_interaction,
    classify_setup,
    infer_locator_strategy,
    is_navigation_call,
    is_rq1_control_environment,
    is_rq1_environment_feature,
    map_input_source,
)
from feature_merge import (
    feature_dedupe_key,
    helper_edge_dedupe_key,
    build_hook_by_key_from_direct,
    is_direct_test_body_feature,
)
from run_rq_aggregation import load_repo_test_cases, merge_csv_partials, stream_all_features, validate_parallel_temp_dir
from aggregate import (
    Aggregator,
    assertion_execution_scope,
    assertion_provenance,
    assertion_source_bucket,
    ui_action_bucket,
    expanded_assertion_source_pattern,
    is_test_body_source,
    ui_action_category_from_feature,
)
from aggregate import TestAgg
from static_metrics_join import merge_static_fields


class TestParallelTempDirGuard(unittest.TestCase):
    def test_rejects_input_dir_as_parallel_temp_dir(self):
        root = Path("C:/tmp/phase2_run")
        with self.assertRaises(RuntimeError):
            validate_parallel_temp_dir(root, root, root / "per_repo_outputs")

    def test_allows_named_child_parallel_temp_dir(self):
        root = Path("C:/tmp/phase2_run")
        resolved = validate_parallel_temp_dir(
            root / "_phase2d_partials",
            root,
            root / "per_repo_outputs",
        )
        self.assertEqual(resolved.name, "_phase2d_partials")


class TestEventCsvFreshness(unittest.TestCase):
    def test_parallel_merge_overwrites_stale_event_csv_when_no_partials_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stale = root / "rq2_input_events.csv"
            stale.write_text("old\n", encoding="utf-8")
            partial = root / "_phase2d_partials" / "worker_001"
            partial.mkdir(parents=True)

            merge_csv_partials(partial_dirs=[partial], output_dir=root)

            self.assertTrue(stale.exists())
            self.assertTrue(stale.read_text(encoding="utf-8").startswith("repo,test_id,framework"))
            self.assertNotIn("old", stale.read_text(encoding="utf-8"))

    def test_single_process_close_overwrites_stale_empty_event_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stale = root / "rq2_input_events.csv"
            stale.write_text("old\n", encoding="utf-8")

            agg = Aggregator({}, root)
            agg.close_event_sinks()

            self.assertTrue(stale.read_text(encoding="utf-8").startswith("repo,test_id,framework"))
            self.assertNotIn("old", stale.read_text(encoding="utf-8"))


class TestLoadRepoTestCases(unittest.TestCase):
    def test_falls_back_to_root_for_repos_missing_sidecars(self):
        import json

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            per_repo = root / "per_repo_outputs"
            per_repo.mkdir()
            (per_repo / "owner__with-sidecar.test_cases.jsonl").write_text(
                json.dumps({"repo": "owner/with-sidecar", "test_id": "t1"}) + "\n",
                encoding="utf-8",
            )
            (root / "test_cases.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps({"repo": "owner/with-sidecar", "test_id": "root-ignored"}),
                        json.dumps({"repo": "owner/root-only", "test_id": "t2"}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            loaded = load_repo_test_cases(
                repos=["owner/with-sidecar", "owner/root-only"],
                input_dir=root,
                per_repo_dir=per_repo,
            )

            self.assertIn("owner/with-sidecar::t1", loaded)
            self.assertIn("owner/root-only::t2", loaded)
            self.assertNotIn("owner/with-sidecar::root-ignored", loaded)


class TestClassifyInteraction(unittest.TestCase):
    def test_cy_visit_is_navigation(self):
        self.assertEqual(classify_interaction("cy.visit", "cy.visit('/settings')"), "navigation")

    def test_page_goto_is_navigation(self):
        self.assertEqual(classify_interaction("page.goto", 'page.goto("/auth/sign-up")'), "navigation")

    def test_browser_url_is_navigation(self):
        self.assertEqual(classify_interaction("browser.url", "browser.url('/home')"), "navigation")

    def test_opentovisitors_not_navigation(self):
        self.assertEqual(
            classify_interaction(
                "cy.get",
                "cy.get('[data-cy=tag-openToVisitors]').contains(visitorType).click()",
            ),
            "locator_query",
        )

    def test_gotocheckout_not_navigation(self):
        self.assertEqual(
            classify_interaction(
                "page.components.cart.goToCheckoutButton.click",
                "page.components.cart.goToCheckoutButton.click()",
            ),
            "click",
        )

    def test_goto3_label_not_navigation(self):
        self.assertEqual(
            classify_interaction("cy.get('div').contains", "cy.get('div').contains('goTo3')"),
            "locator_query",
        )

    def test_tohaveurl_not_navigation(self):
        self.assertEqual(
            classify_interaction("expect(page).toHaveURL", "expect(page).toHaveURL(/\\/home$/)"),
            "unknown_action",
        )

    def test_waitforurl_not_navigation(self):
        self.assertFalse(is_navigation_call("page.waitForURL", "await page.waitForURL('**/dashboard')"))
        self.assertEqual(
            classify_interaction("page.waitForURL", "await page.waitForURL('**/dashboard')"),
            "wait_synchronization",
        )

    def test_is_navigation_call_helper(self):
        self.assertTrue(is_navigation_call("cy.visit", "cy.visit('/')"))
        self.assertFalse(is_navigation_call("cy.get", "cy.get('[data-cy=openToVisitors]')"))

    def test_structured_ui_category_overrides_raw_text_fallback(self):
        self.assertEqual(
            ui_action_category_from_feature(
                {"ui_action_category": "drag_drop", "terminal_action_ast": "drag"},
                "page.mouse.up",
                "await page.mouse.up()",
            ),
            "drag_drop",
        )
        self.assertEqual(
            ui_action_category_from_feature(
                {"ui_action_category": "scroll", "terminal_action_ast": "scroll"},
                "container.evaluate.scroll",
                "container.evaluate((el) => { el.scrollTop = 100 })",
            ),
            "scroll",
        )


class TestClassifySetup(unittest.TestCase):
    def test_after_each_is_teardown_not_hook_setup(self):
        cat = classify_setup("afterEach callback", "cy.login()", "afterEach", "setup")
        self.assertEqual(cat, "teardown_cleanup")

    def test_before_each_is_hook_setup(self):
        cat = classify_setup("beforeEach", "cy.visit('/')", "beforeEach", "setup")
        self.assertEqual(cat, "hook_setup")

    def test_network_mock_feature_type(self):
        cat = classify_setup("page.route", "await page.route('**/*', handler)", "test_body", "network_mock")
        self.assertEqual(cat, "network_mock")


class TestRq1Features(unittest.TestCase):
    def test_includes_network_mock(self):
        self.assertTrue(is_rq1_environment_feature({"feature_type": "network_mock"}))

    def test_excludes_plain_ui_action(self):
        self.assertFalse(is_rq1_environment_feature({"feature_type": "ui_action"}))

    def test_control_session_is_rq1(self):
        self.assertTrue(
            is_rq1_environment_feature(
                {
                    "feature_type": "control",
                    "name": "cy.session",
                    "raw_code": "cy.session('user', () => cy.request('/login'))",
                }
            )
        )

    def test_control_wrap_excluded(self):
        self.assertFalse(
            is_rq1_environment_feature(
                {
                    "feature_type": "control",
                    "name": "cy.wrap",
                    "raw_code": "cy.wrap($el).click()",
                }
            )
        )

    def test_control_then_excluded(self):
        self.assertFalse(
            is_rq1_environment_feature(
                {
                    "feature_type": "control",
                    "name": "cy.then",
                    "raw_code": "cy.get('button').then(($btn) => { ... })",
                }
            )
        )

    def test_control_cookie_included(self):
        self.assertTrue(
            is_rq1_environment_feature(
                {
                    "feature_type": "control",
                    "name": "page.context",
                    "raw_code": "await context.addCookies([{ name: 'token', value: 'x' }])",
                }
            )
        )

    def test_control_intercept_included(self):
        self.assertTrue(
            is_rq1_control_environment("cy.intercept", "cy.intercept('GET', '/api/**', { fixture: 'x' })")
        )


class TestAssertionSourceKinds(unittest.TestCase):
    def test_helper_oracle_counts_as_helper_provenance(self):
        self.assertEqual(assertion_source_bucket("helper_oracle", 0, False), "helper")
        self.assertEqual(assertion_provenance("helper_oracle", 0, False), "helper")
        self.assertEqual(assertion_execution_scope("helper_oracle", False, 0), "expanded")
        self.assertFalse(is_test_body_source("helper_oracle", False, 0))

    def test_implicit_oracle_counts_as_direct_test_body(self):
        self.assertEqual(assertion_source_bucket("implicit_oracle", 0, False), "direct")
        self.assertEqual(assertion_provenance("implicit_oracle", 0, False), "direct")
        self.assertEqual(assertion_execution_scope("implicit_oracle", False, 0), "test_body")
        self.assertTrue(is_test_body_source("implicit_oracle", False, 0))


class TestDedupeKey(unittest.TestCase):
    def test_raw_code_in_key(self):
        a = feature_dedupe_key("r", "t", {"feature_type": "ui_action", "name": "x", "line": 1, "raw_code": "cy.get(1)"})
        b = feature_dedupe_key("r", "t", {"feature_type": "ui_action", "name": "x", "line": 1, "raw_code": "cy.get(2)"})
        self.assertNotEqual(a, b)

    def test_repo_test_id_whitespace_normalized_in_key(self):
        base = {"feature_type": "ui_action", "name": "x", "line": 1, "raw_code": "cy.get(1)"}
        self.assertEqual(
            feature_dedupe_key(" r ", " t ", base),
            feature_dedupe_key("r", "t", base),
        )
        e = {"repo": " r ", "test_id": " t ", "from": "a", "to": "b", "resolved": True}
        self.assertEqual(helper_edge_dedupe_key(e), helper_edge_dedupe_key({**e, "repo": "r", "test_id": "t"}))

    def test_helper_edge_resolved_normalized(self):
        e1 = {"repo": "r", "test_id": "t", "from": "a", "to": "b", "resolved": True}
        e2 = {"repo": "r", "test_id": "t", "from": "a", "to": "b", "resolved": "1"}
        self.assertEqual(helper_edge_dedupe_key(e1), helper_edge_dedupe_key(e2))


class TestIngestFeatureNormalization(unittest.TestCase):
    def test_event_csv_uses_stripped_repo_test_id(self):
        import csv
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            tc = {"r::t": {"repo": "r", "test_id": "t", "describe_path": []}}
            agg = Aggregator(tc, out)
            agg.rq4_sink.open()
            agg.ingest_feature(
                {
                    "repo": " r ",
                    "test_id": " t ",
                    "feature_type": "ui_action",
                    "name": "click",
                    "raw_code": "cy.get('#x').click()",
                    "source_kind": "test_body",
                    "line": 1,
                }
            )
            agg.close_event_sinks()
            with (out / "rq4_interaction_events.csv").open(encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["repo"], "r")
            self.assertEqual(rows[0]["test_id"], "t")


class TestHelperEdgeDedup(unittest.TestCase):
    def test_duplicate_edge_counted_once(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            tc = {"r::t": {"repo": "r", "test_id": "t", "describe_path": []}}
            agg = Aggregator(tc, out)
            edge = {
                "repo": "r",
                "test_id": "t",
                "hook_instance_key": "hk1",
                "from": "helperA",
                "to": "helperB",
                "target_file": "helpers.ts",
                "depth": 1,
                "resolved": True,
            }
            agg.ingest_helper_edge(edge)
            agg.ingest_helper_edge(dict(edge))
            self.assertEqual(agg.by_key["r::t"].helper_edge_count, 1)
            self.assertEqual(len(agg.seen_helper_edges), 1)

    def test_distinct_edges_both_counted(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            tc = {"r::t": {"repo": "r", "test_id": "t", "describe_path": []}}
            agg = Aggregator(tc, out)
            base = {
                "repo": "r",
                "test_id": "t",
                "hook_instance_key": "hk1",
                "from": "a",
                "to": "b",
                "target_file": "h.ts",
                "depth": 1,
                "resolved": True,
            }
            agg.ingest_helper_edge(base)
            agg.ingest_helper_edge({**base, "to": "c"})
            self.assertEqual(agg.by_key["r::t"].helper_edge_count, 2)


class TestInputSource(unittest.TestCase):
    def test_trusts_input_source(self):
        self.assertEqual(map_input_source("variable_input", "input:fill:x", ""), "variable_input")


class TestLocatorStrategy(unittest.TestCase):
    def test_page_goto_not_css(self):
        self.assertIsNone(infer_locator_strategy("page.goto", "await page.goto('/home')", "navigation"))

    def test_cy_get_is_css(self):
        self.assertEqual(
            infer_locator_strategy("cy.get", "cy.get('#btn')", "locator_query"),
            "css",
        )


class TestUiActionBucket(unittest.TestCase):
    def test_before_each_is_hook(self):
        self.assertEqual(ui_action_bucket("beforeEach", True, 0), "hook")

    def test_test_body(self):
        self.assertEqual(ui_action_bucket("test_body", False, 0), "test_body")

    def test_hook_attached_cypress_command_is_hook(self):
        self.assertEqual(ui_action_bucket("cypress_command", True, 1), "hook")

    def test_cypress_command_without_hook(self):
        self.assertEqual(ui_action_bucket("cypress_command", False, 0), "cypress_command")


class TestAssertionPattern(unittest.TestCase):
    def test_direct_and_helper(self):
        agg = TestAgg(repo="r", test_id="t")
        agg.direct_assertion_count = 2
        agg.helper_assertion_count = 1
        self.assertEqual(expanded_assertion_source_pattern(agg), "direct_and_helper")


class TestFeatureMergeImport(unittest.TestCase):
    def test_build_hook_by_key_import(self):
        import tempfile
        from pathlib import Path

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
            f.write(
                '{"is_shared_hook_feature":true,"hook_instance_key":"k1","feature_type":"setup"}\n'
            )
            path = Path(f.name)
        try:
            hooks = build_hook_by_key_from_direct(path)
            self.assertIn("k1", hooks)
        finally:
            path.unlink(missing_ok=True)


class TestDirectTestBodyFeature(unittest.TestCase):
    def test_accepts_test_body(self):
        self.assertTrue(
            is_direct_test_body_feature(
                {"test_id": "t1", "source_kind": "test_body", "feature_type": "ui_action"}
            )
        )

    def test_rejects_shared_hook(self):
        self.assertFalse(
            is_direct_test_body_feature(
                {
                    "test_id": "t1",
                    "source_kind": "test_body",
                    "is_shared_hook_feature": True,
                }
            )
        )

    def test_rejects_before_each(self):
        self.assertFalse(
            is_direct_test_body_feature(
                {"test_id": "t1", "source_kind": "beforeEach", "feature_type": "setup"}
            )
        )


class TestStaticMetricsJoin(unittest.TestCase):
    def test_left_join_missing_static_row(self):
        base = {"repo": "r", "test_id": "t", "ui_action_count": 3}
        merged = merge_static_fields(base, None)
        self.assertEqual(merged["ui_action_count"], 3)
        self.assertFalse(merged["sm_joined"])
        self.assertFalse(merged["sm_metrics_ok"])
        self.assertEqual(merged["sm_test_body_ncloc"], "")

    def test_left_join_with_static_row(self):
        base = {"repo": "r", "test_id": "t"}
        sm = {"test_body_ncloc": 12, "navigation_action_count": 2, "metrics_status": "ok"}
        merged = merge_static_fields(base, sm)
        self.assertTrue(merged["sm_joined"])
        self.assertTrue(merged["sm_metrics_ok"])
        self.assertEqual(merged["sm_test_body_ncloc"], 12)
        self.assertEqual(merged["sm_navigation_action_count"], 2)


class TestStreamAllFeatures(unittest.TestCase):
    def test_merges_direct_test_body_with_expanded(self):
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            direct = root / "test_case_features_direct.jsonl"
            expanded = root / "test_case_features_expanded.jsonl"
            direct.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "repo": "r",
                                "test_id": "t",
                                "source_kind": "test_body",
                                "feature_type": "ui_action",
                                "name": "cy.get",
                                "line": 10,
                                "raw_code": "cy.get('#a')",
                            }
                        ),
                        json.dumps(
                            {
                                "is_shared_hook_feature": True,
                                "hook_instance_key": "hk",
                                "source_kind": "beforeEach",
                                "feature_type": "setup",
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            expanded.write_text(
                json.dumps(
                    {
                        "repo": "r",
                        "test_id": "t",
                        "source_kind": "cypress_command",
                        "feature_type": "ui_action",
                        "name": "cy.click",
                        "line": 99,
                        "raw_code": "cy.get('#a').click()",
                        "attached_from_hook": True,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            tc = {"r::t": {"repo": "r", "test_id": "t", "hook_instance_keys": ["hk"]}}
            rows = list(stream_all_features(root, None, tc))
            source_kinds = {r.get("source_kind") for r in rows}
            self.assertIn("test_body", source_kinds)
            self.assertIn("cypress_command", source_kinds)
            self.assertEqual(len(rows), 2)


if __name__ == "__main__":
    unittest.main()
