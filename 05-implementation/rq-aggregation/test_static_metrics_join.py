#!/usr/bin/env python3
"""Tests for static metrics left-join (Phase 2D)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from static_metrics_join import (
    StaticMetricsLoadResult,
    as_bool,
    build_static_metrics_by_test_rows,
    join_summary,
    load_static_metrics,
    merge_static_fields,
    metrics_row_is_ok,
    resolve_static_metrics_path,
)
from stream_io import load_test_cases, test_key


class TestTestKey(unittest.TestCase):
    def test_strips_whitespace(self):
        self.assertEqual(test_key(" r ", " t "), test_key("r", "t"))

    def test_load_test_cases_whitespace_repo_matches_static(self):
        with tempfile.TemporaryDirectory() as td:
            cases = Path(td) / "test_cases.jsonl"
            metrics = Path(td) / "test_case_static_metrics.jsonl"
            cases.write_text(
                json.dumps({"repo": " r ", "test_id": "t1"}) + "\n",
                encoding="utf-8",
            )
            metrics.write_text(
                json.dumps(
                    {"repo": "r", "test_id": " t1 ", "metrics_status": "ok", "test_body_ncloc": 1}
                )
                + "\n",
                encoding="utf-8",
            )
            tc = load_test_cases(cases)
            sm = load_static_metrics(metrics)
            row = next(iter(tc.values()))
            self.assertEqual(row["repo"], "r")
            self.assertEqual(row["test_id"], "t1")
            static_row = sm.by_key[test_key("r", "t1")]
            self.assertEqual(static_row["repo"], "r")
            self.assertEqual(static_row["test_id"], "t1")
            s = join_summary(tc, sm.by_key)
            self.assertEqual(s["static_metrics_matched_ok"], 1)
            spine = build_static_metrics_by_test_rows(tc, sm.by_key)
            self.assertEqual(spine[0]["repo"], "r")
            self.assertEqual(spine[0]["test_id"], "t1")


class TestAsBool(unittest.TestCase):
    def test_string_false_is_false(self):
        self.assertFalse(as_bool("false"))
        self.assertFalse(as_bool("0"))

    def test_string_true(self):
        self.assertTrue(as_bool("true"))
        self.assertTrue(as_bool("1"))


class TestLoadStaticMetrics(unittest.TestCase):
    def test_duplicate_and_malformed_rows(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "test_case_static_metrics.jsonl"
            rows = [
                {"repo": "r", "test_id": "t1", "metrics_status": "ok", "test_body_ncloc": 1},
                {"repo": "r", "test_id": "t1", "metrics_status": "ok", "test_body_ncloc": 99},
                {"repo": "r", "test_id": "", "metrics_status": "ok"},
                {"repo": "r2", "test_id": "t2", "metrics_status": "commit_mismatch"},
            ]
            p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
            loaded = load_static_metrics(p)
            self.assertEqual(loaded.rows_read, 4)
            self.assertEqual(loaded.rows_malformed, 1)
            self.assertEqual(loaded.duplicate_rows, 1)
            self.assertEqual(loaded.duplicate_keys, 1)
            self.assertEqual(loaded.unique_keys, 2)
            self.assertEqual(loaded.by_key[test_key("r", "t1")]["test_body_ncloc"], 99)

    def test_resolve_paths(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            nested = root / "static_metrics"
            nested.mkdir()
            target = nested / "test_case_static_metrics.jsonl"
            target.write_text("{}\n", encoding="utf-8")
            self.assertEqual(resolve_static_metrics_path(root), target)
            self.assertEqual(resolve_static_metrics_path(nested), target)


class TestMergeStaticFields(unittest.TestCase):
    def test_unmatched_uses_blank_not_zero(self):
        merged = merge_static_fields({"repo": "r", "test_id": "t"}, None)
        self.assertFalse(merged["sm_joined"])
        self.assertFalse(merged["sm_metrics_ok"])
        self.assertEqual(merged["sm_test_body_ncloc"], "")
        self.assertEqual(merged["sm_has_dynamic_navigation"], "")

    def test_joined_non_ok_not_usable(self):
        sm = {"metrics_status": "commit_mismatch", "test_body_ncloc": 5}
        merged = merge_static_fields({"repo": "r", "test_id": "t"}, sm)
        self.assertTrue(merged["sm_joined"])
        self.assertFalse(merged["sm_metrics_ok"])
        self.assertEqual(merged["sm_test_body_ncloc"], 5)

    def test_json_list_normalized(self):
        sm = {"metrics_status": "ok", "static_url_literals_json": ["/a", "/b"]}
        merged = merge_static_fields({}, sm)
        self.assertTrue(merged["sm_metrics_ok"])
        self.assertEqual(json.loads(merged["sm_static_url_literals_json"]), ["/a", "/b"])

    def test_bool_string_false(self):
        sm = {"metrics_status": "ok", "has_dynamic_navigation": "false"}
        merged = merge_static_fields({}, sm)
        self.assertFalse(merged["sm_has_dynamic_navigation"])


class TestJoinSummary(unittest.TestCase):
    def test_summary_backward_compatible_alias(self):
        s = join_summary({test_key("r", "t1"): {}}, {test_key("r", "t1"): {"metrics_status": "ok"}})
        self.assertEqual(s["static_metrics_unique_keys"], 1)
        self.assertEqual(s["static_metrics_rows_loaded"], 1)

    def test_orphan_and_ok_counts(self):
        tc = {
            test_key("r", "t1"): {"repo": "r", "test_id": "t1"},
            test_key("r", "t2"): {"repo": "r", "test_id": "t2"},
        }
        sm = {
            test_key("r", "t1"): {"repo": "r", "test_id": "t1", "metrics_status": "ok"},
            test_key("r", "t3"): {"repo": "r", "test_id": "t3", "metrics_status": "ok"},
        }
        s = join_summary(tc, sm)
        self.assertEqual(s["static_metrics_matched"], 1)
        self.assertEqual(s["static_metrics_matched_ok"], 1)
        self.assertEqual(s["static_metrics_unmatched"], 1)
        self.assertEqual(s["static_metrics_orphan"], 1)

    def test_metrics_row_is_ok(self):
        self.assertTrue(metrics_row_is_ok({"metrics_status": "ok"}))
        self.assertTrue(metrics_row_is_ok({"metrics_status": " OK "}))
        self.assertFalse(metrics_row_is_ok({"metrics_status": "commit_mismatch"}))

    def test_malformed_test_case_spine_counts(self):
        tc = {
            "bad": {"repo": "", "test_id": "t1"},
            test_key("r", "t1"): {"repo": "r", "test_id": "t1"},
        }
        s = join_summary(tc, {})
        self.assertEqual(s["test_cases_spine"], 2)
        self.assertEqual(s["test_cases_spine_valid_keys"], 1)
        self.assertEqual(s["test_cases_spine_malformed_keys"], 1)
        self.assertEqual(s["static_metrics_unmatched"], 1)

    def test_missing_repo_is_malformed(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "test_case_static_metrics.jsonl"
            p.write_text(
                json.dumps({"repo": "", "test_id": "t1", "metrics_status": "ok"}) + "\n",
                encoding="utf-8",
            )
            loaded = load_static_metrics(p)
            self.assertEqual(loaded.rows_malformed, 1)
            self.assertEqual(loaded.unique_keys, 0)


class TestAggregatorStaticJoin(unittest.TestCase):
    def test_finalize_writes_sm_columns_and_spine_csv(self):
        from aggregate import Aggregator

        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "rq_out"
            tc = {
                test_key("r", "t1"): {
                    "repo": "r",
                    "test_id": "t1",
                    "framework": "cypress",
                    "describe_path": [],
                },
                test_key("r", "t2"): {
                    "repo": "r",
                    "test_id": "t2",
                    "framework": "cypress",
                    "describe_path": [],
                },
            }
            sm = {
                test_key("r", "t1"): {
                    "repo": "r",
                    "test_id": "t1",
                    "metrics_status": "ok",
                    "test_body_ncloc": 7,
                },
            }
            load = StaticMetricsLoadResult(by_key=sm, rows_read=1, unique_keys=1)
            agg = Aggregator(
                tc,
                out,
                static_metrics_by_key=sm,
                static_metrics_load=load,
            )
            agg.rq4_sink.open()
            agg.rq5_sink.open()
            agg.close_event_sinks()
            counts = agg.finalize()

            self.assertEqual(counts["static_metrics_matched_ok"], 1)
            self.assertEqual(counts["static_metrics_unmatched"], 1)

            spine_path = out / "rq_static_metrics_by_test.csv"
            self.assertTrue(spine_path.exists())
            spine_lines = [
                ln for ln in spine_path.read_text(encoding="utf-8").splitlines() if ln.strip()
            ]
            self.assertEqual(len(spine_lines), 3)  # header + 2 tests

            rq4_path = out / "rq4_interaction_complexity_by_test.csv"
            lines = rq4_path.read_text(encoding="utf-8").splitlines()
            self.assertIn("sm_test_body_ncloc", lines[0])
            self.assertIn("sm_joined", lines[0])
            self.assertIn("sm_metrics_ok", lines[0])


class TestBuildStaticMetricsByTestRows(unittest.TestCase):
    def test_one_row_per_test_case(self):
        tc = {test_key("a", "x"): {"repo": "a", "test_id": "x"}}
        rows = build_static_metrics_by_test_rows(tc, {})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["sm_test_body_ncloc"], "")

    def test_lookup_uses_row_fields_not_dict_key(self):
        sm = {test_key("a", "x"): {"metrics_status": "ok", "test_body_ncloc": 3}}
        tc = {"legacy::key": {"repo": "a", "test_id": "x"}}
        rows = build_static_metrics_by_test_rows(tc, sm)
        self.assertEqual(rows[0]["sm_test_body_ncloc"], 3)

    def test_join_summary_uses_row_fields_not_dict_key(self):
        sm = {test_key("a", "x"): {"metrics_status": "ok"}}
        tc = {"legacy::key": {"repo": "a", "test_id": "x"}}
        s = join_summary(tc, sm)
        self.assertEqual(s["static_metrics_matched"], 1)
        self.assertEqual(s["static_metrics_matched_ok"], 1)
        self.assertEqual(s["static_metrics_unmatched"], 0)


if __name__ == "__main__":
    unittest.main()
