#!/usr/bin/env python3
"""Regression tests for merge-only static metric output refresh."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from navigationMetrics import safe_repo_dir


class TestMergePerRepoOutputs(unittest.TestCase):
    def test_recompute_navigation_uses_cached_static_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            run = root / "run"
            output = run / "static_metrics"
            (run / "per_repo_outputs").mkdir(parents=True)
            (output / "per_repo_outputs").mkdir(parents=True)

            repo = "Example/app"
            stem = safe_repo_dir(repo)
            payload = {
                "repo": repo,
                "metrics": [
                    {
                        "repo": repo,
                        "test_id": "test-1",
                        "file_path": "tests/dashboard.spec.ts",
                        "metrics_status": "ok",
                        "test_body_ncloc": 3,
                        "test_body_cyclomatic_basic": 1,
                        "test_body_branch_count": 0,
                        "test_body_loop_count": 0,
                        "hook_count": 0,
                    }
                ],
                "hooks": [],
            }
            (output / "per_repo_outputs" / f"{stem}.json").write_text(
                json.dumps(payload),
                encoding="utf-8",
            )
            (run / "per_repo_outputs" / f"{stem}.features_direct.jsonl").write_text(
                json.dumps(
                    {
                        "repo": repo,
                        "test_id": "test-1",
                        "feature_type": "ui_action",
                        "name": "page.goto",
                        "raw_code": "page.goto('/dashboard')",
                        "line": 12,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            script = Path(__file__).resolve().parent / "scripts" / "merge_per_repo_outputs.py"
            subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--output-dir",
                    str(output),
                    "--input-run-dir",
                    str(run),
                    "--recompute-navigation",
                ],
                check=True,
                text=True,
                capture_output=True,
            )

            rows = [
                json.loads(line)
                for line in (output / "test_case_static_metrics.jsonl").read_text(
                    encoding="utf-8"
                ).splitlines()
                if line.strip()
            ]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["navigation_action_count"], 1)
            self.assertEqual(rows[0]["estimated_page_or_view_count"], 1)

            summary = json.loads((output / "static_metrics_summary.json").read_text())
            self.assertFalse(summary["skipped_navigation"])
            self.assertEqual(summary["navigation_feature_source"], "per_repo_sidecars")
            self.assertEqual(summary["navigation_joined_tests"], 1)


if __name__ == "__main__":
    unittest.main()
