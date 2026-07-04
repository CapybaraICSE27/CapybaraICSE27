#!/usr/bin/env python3
"""Print pass/fail for static-metrics validation gates from static_metrics_summary.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple


def load_summary(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def check_gates(s: Dict[str, Any]) -> List[Tuple[str, bool, str]]:
    status_dist = s.get("metrics_status_distribution") or {}
    ok_n = int(status_dist.get("ok") or 0)
    total = int(s.get("metrics_rows_total") or s.get("test_cases_total") or 0)
    non_ok = {k: v for k, v in status_dist.items() if k != "ok" and int(v or 0) > 0}

    gates: List[Tuple[str, bool, str]] = []

    gates.append(
        (
            "metrics_status_all_ok",
            total > 0 and ok_n == total and not non_ok,
            f"ok={ok_n}/{total} distribution={status_dist}",
        )
    )
    gates.append(
        (
            "zero_ncloc_tests_ok_status",
            int(s.get("zero_ncloc_tests_ok_status") or 0) == 0,
            f"count={s.get('zero_ncloc_tests_ok_status', 0)}",
        )
    )
    gates.append(
        (
            "hook_metrics_unresolved_total",
            int(s.get("hook_metrics_unresolved_total") or 0) == 0,
            f"total={s.get('hook_metrics_unresolved_total', 0)}",
        )
    )
    gates.append(
        (
            "repos_commit_mismatch",
            int(s.get("repos_commit_mismatch") or 0) == 0,
            f"repos={s.get('repos_commit_mismatch', 0)} row_commit_mismatches={s.get('commit_mismatches', 0)}",
        )
    )
    gates.append(
        (
            "missing_repo_cache",
            int(s.get("missing_repo_cache") or 0) == 0
            and int(s.get("repos_missing_cache") or 0) == 0,
            f"rows={s.get('missing_repo_cache', 0)} repos={s.get('repos_missing_cache', 0)}",
        )
    )
    outliers = int(s.get("outlier_tests_count") or 0)
    gates.append(
        (
            "outlier_tests_count",
            outliers == 0,
            f"count={outliers} sample={s.get('outlier_tests_sample', [])[:3]}",
        )
    )

    ncloc = s.get("ncloc_distribution") or {}
    cyc = s.get("cyclomatic_basic_distribution") or {}
    gates.append(
        (
            "ncloc_distribution_sane",
            int(ncloc.get("min") or 0) >= 1 and int(ncloc.get("max") or 0) < 2000,
            f"ncloc={ncloc}",
        )
    )
    gates.append(
        (
            "cyclomatic_distribution_sane",
            int(cyc.get("min") or 0) >= 1 and int(cyc.get("max") or 0) < 200,
            f"cyclomatic_basic={cyc}",
        )
    )

    return gates


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("summary_json", type=Path, nargs="?", default=None)
    ap.add_argument("--output-dir", type=Path, default=None)
    args = ap.parse_args()

    path = args.summary_json
    if path is None:
        if args.output_dir is None:
            print("Provide summary_json or --output-dir", file=sys.stderr)
            sys.exit(2)
        path = args.output_dir / "static_metrics_summary.json"

    if not path.exists():
        print(f"Missing {path}", file=sys.stderr)
        sys.exit(2)

    s = load_summary(path)
    gates = check_gates(s)
    failed = 0
    for name, ok, detail in gates:
        mark = "PASS" if ok else "FAIL"
        if not ok:
            failed += 1
        print(f"[{mark}] {name}: {detail}")

    print()
    print(
        json.dumps(
            {
                "repos_processed": s.get("repos_processed"),
                "metrics_rows_total": s.get("metrics_rows_total"),
                "repos_errors": s.get("repos_errors"),
            },
            indent=2,
        )
    )
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
