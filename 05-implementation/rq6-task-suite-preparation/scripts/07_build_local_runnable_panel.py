#!/usr/bin/env python3
"""Phase 1 finalizer: build selected and reserve repo panels from baseline runs."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

LIB = Path(__file__).resolve().parents[1] / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

from common import DEFAULT_OUT_DIR, iter_jsonl, write_csv, write_jsonl  # noqa: E402


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--baseline-runs", type=Path, default=DEFAULT_OUT_DIR / "human_test_baseline_runs.jsonl")
    ap.add_argument("--target-repos", type=int, default=20)
    ap.add_argument("--tests-per-repo", type=int, default=3)
    ap.add_argument("--reserve-repos", type=int, default=10)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    by_repo_test: Dict[tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for run in iter_jsonl(args.baseline_runs):
        target_id = str(run.get("execution_target_id") or run.get("test_id") or "")
        by_repo_test[(str(run.get("repo_full_name") or ""), target_id)].append(run)

    stable_tests_by_repo: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    passed_once_by_repo: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for (repo, test_id), runs in by_repo_test.items():
        passed = [r for r in runs if r.get("passed_once")]
        durations = [float(r.get("duration_sec") or 0) for r in runs if float(r.get("duration_sec") or 0) > 0]
        summary = {
            "repo_full_name": repo,
            "repo_cache_key": runs[0].get("repo_cache_key"),
            "framework": runs[0].get("framework"),
            "source_provenance": runs[0].get("source_provenance"),
            "phase2_commit_alignment": runs[0].get("phase2_commit_alignment"),
            "source_snapshot_sha256": runs[0].get("source_snapshot_sha256"),
            "test_id": test_id,
            "execution_target_id": test_id,
            "execution_scope": runs[0].get("execution_scope") or "test_title",
            "representative_test_id": runs[0].get("representative_test_id"),
            "represented_test_count": runs[0].get("represented_test_count"),
            "represented_test_ids_json": runs[0].get("represented_test_ids_json"),
            "represented_test_names_json": runs[0].get("represented_test_names_json"),
            "file_path": runs[0].get("file_path"),
            "test_name": runs[0].get("test_name"),
            "runs_attempted": len(runs),
            "runs_passed": len(passed),
            "stable_passed": len(runs) > 0 and len(passed) == len(runs),
            "passed_once": bool(passed),
            "median_duration_sec": statistics.median(durations) if durations else 0,
            "max_duration_sec": max(durations) if durations else 0,
            "baseline_stable_passed": len(runs) > 0 and len(passed) == len(runs),
        }
        if summary["passed_once"]:
            passed_once_by_repo[repo].append(summary)
        if summary["stable_passed"]:
            stable_tests_by_repo[repo].append(summary)

    repo_rows: List[Dict[str, Any]] = []
    for repo in sorted(set(passed_once_by_repo) | set(stable_tests_by_repo)):
        stable = stable_tests_by_repo.get(repo, [])
        passed_once = passed_once_by_repo.get(repo, [])
        first = (stable or passed_once)[0]
        row = {
            "repo_full_name": repo,
            "repo_cache_key": first.get("repo_cache_key"),
            "framework": first.get("framework"),
            "source_provenance": first.get("source_provenance"),
            "phase2_commit_alignment": first.get("phase2_commit_alignment"),
            "num_tests_passed_once": len(passed_once),
            "num_tests_stable_passed": len(stable),
            "qualifies_main": len(stable) >= args.tests_per_repo,
            "qualifies_reserve": len(passed_once) >= args.tests_per_repo,
            "median_test_sec": statistics.median([t["median_duration_sec"] for t in stable]) if stable else 0,
            "selection_notes": "",
        }
        repo_rows.append(row)

    main_panel = [r for r in repo_rows if r["qualifies_main"]]
    main_panel.sort(key=lambda r: (str(r.get("framework") or ""), -int(r.get("num_tests_stable_passed") or 0), str(r.get("repo_full_name") or "")))
    selected = main_panel[: args.target_repos]
    selected_repos = {r["repo_full_name"] for r in selected}
    reserve = [r for r in repo_rows if r["repo_full_name"] not in selected_repos and r["qualifies_reserve"]]
    reserve = reserve[: args.reserve_repos]
    selected_tests: List[Dict[str, Any]] = []
    for repo_row in selected:
        tests = sorted(
            stable_tests_by_repo.get(str(repo_row["repo_full_name"]), []),
            key=lambda t: (float(t.get("median_duration_sec") or 0), str(t.get("file_path") or ""), str(t.get("test_id") or "")),
        )
        selected_tests.extend(tests[: args.tests_per_repo])

    write_csv(args.out_dir / "selected_repo_panel_20.csv", selected)
    write_csv(args.out_dir / "reserve_repo_panel.csv", reserve)
    stability_rows = [t for tests in stable_tests_by_repo.values() for t in tests]
    write_jsonl(args.out_dir / "human_test_stability.jsonl", stability_rows)
    write_jsonl(args.out_dir / "selected_human_tests_60.jsonl", selected_tests)
    write_csv(args.out_dir / "selected_human_tests_60.csv", selected_tests)
    print(
        json.dumps(
            {
                "selected_repos": len(selected),
                "selected_human_tests": len(selected_tests),
                "reserve_repos": len(reserve),
                "stable_tests": len(stability_rows),
                "out_dir": str(args.out_dir),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
