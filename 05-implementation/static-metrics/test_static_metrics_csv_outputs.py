#!/usr/bin/env python3
"""Regression tests for deterministic static-metrics CSV output."""

from __future__ import annotations

import csv
import subprocess
import tempfile
import unittest
from pathlib import Path

from extract_static_metrics import (
    HOOK_STATIC_METRIC_FIELDS,
    cleanup_materialized_tree,
    git_commit_exists,
    materialize_commit_tree,
    write_csv,
)


class TestStaticMetricsCsvOutputs(unittest.TestCase):
    def test_empty_rows_truncate_stale_csv(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "test_case_static_metrics.csv"
            path.write_text("stale,data\n1,2\n", encoding="utf-8")

            write_csv(path, [])

            self.assertEqual(path.read_text(encoding="utf-8"), "")

    def test_empty_hook_rows_write_stable_header(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "hook_static_metrics.csv"

            write_csv(path, [], HOOK_STATIC_METRIC_FIELDS)

            with path.open(encoding="utf-8", newline="") as f:
                reader = csv.reader(f)
                header = next(reader)
                remaining = list(reader)

            self.assertEqual(header, HOOK_STATIC_METRIC_FIELDS)
            self.assertEqual(remaining, [])

    def test_explicit_fieldnames_preserve_extra_columns(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "hook_static_metrics.csv"

            write_csv(
                path,
                [{"repo": "owner/repo", "hook_lookup_key": "a.ts::beforeEach:1", "new_metric": 7}],
                ["repo", "hook_lookup_key"],
            )

            with path.open(encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                self.assertIn("new_metric", reader.fieldnames or [])
                row = next(reader)

            self.assertEqual(row["new_metric"], "7")

    def test_materialize_commit_tree_uses_expected_commit_contents(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, stdout=subprocess.PIPE)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
            (repo / "spec.ts").write_text("const version = 'v1';\n", encoding="utf-8")
            subprocess.run(["git", "add", "spec.ts"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "v1"], cwd=repo, check=True, stdout=subprocess.PIPE)
            commit_v1 = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()

            (repo / "spec.ts").write_text("const version = 'v2';\n", encoding="utf-8")
            subprocess.run(["git", "commit", "-am", "v2"], cwd=repo, check=True, stdout=subprocess.PIPE)

            self.assertTrue(git_commit_exists(repo, commit_v1))
            materialized = materialize_commit_tree(
                repo="owner/repo",
                repo_path=repo,
                commit=commit_v1,
                source_root=Path(td) / "sources",
            )
            try:
                self.assertEqual(
                    (materialized / "spec.ts").read_text(encoding="utf-8"),
                    "const version = 'v1';\n",
                )
                self.assertFalse((materialized / ".git").exists())
            finally:
                cleanup_materialized_tree(materialized)
            self.assertFalse(materialized.exists())


if __name__ == "__main__":
    unittest.main()
