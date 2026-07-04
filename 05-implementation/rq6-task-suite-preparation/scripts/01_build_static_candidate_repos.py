#!/usr/bin/env python3
"""Phase 1A: build static RQ6 candidate repo list from Phase 1/2 artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

LIB = Path(__file__).resolve().parents[1] / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

from common import (  # noqa: E402
    DEFAULT_OUT_DIR,
    DEFAULT_PHASE1_INVENTORY,
    DEFAULT_PHASE2_RUN_DIR,
    DEFAULT_REPO_CACHE,
    confidence_max,
    is_executable_test_case,
    is_skipped_test,
    iter_jsonl,
    load_csv_by_test_id,
    normalize_framework,
    primary_counter_value,
    repo_cache_key,
    require_inputs,
    split_repo,
    to_int,
    write_csv,
    write_jsonl,
)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--phase1-inventory", type=Path, default=DEFAULT_PHASE1_INVENTORY)
    ap.add_argument("--phase2-run-dir", type=Path, default=DEFAULT_PHASE2_RUN_DIR)
    ap.add_argument("--repo-cache", type=Path, default=DEFAULT_REPO_CACHE)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    ap.add_argument("--framework", action="append", default=["playwright", "cypress"])
    ap.add_argument("--min-phase2-tests", type=int, default=5)
    ap.add_argument("--min-ui-action-tests", type=int, default=3)
    ap.add_argument("--min-assertion-tests", type=int, default=3)
    ap.add_argument("--min-candidate-tests", type=int, default=3)
    ap.add_argument("--allow-medium-confidence", action="store_true")
    ap.add_argument("--include-excluded", action="store_true", help="Also write excluded rows to rq6_static_repo_screen.jsonl")
    return ap.parse_args()


def inventory_stats(path: Path) -> Dict[str, Dict[str, Any]]:
    stats: Dict[str, Dict[str, Any]] = {}
    for row in iter_jsonl(path):
        repo = str(row.get("repo") or "")
        if not repo:
            continue
        item = stats.setdefault(
            repo,
            {
                "repo": repo,
                "commits": Counter(),
                "frameworks": Counter(),
                "confidences": [],
                "num_ui_test_files": 0,
            },
        )
        item["num_ui_test_files"] += 1
        if row.get("commit"):
            item["commits"][str(row.get("commit"))] += 1
        fw = normalize_framework(
            row.get("detected_frameworks")
            or row.get("file_detected_frameworks")
            or row.get("repo_framework_context")
        )
        if fw:
            item["frameworks"][fw] += 1
        item["confidences"].append(str(row.get("confidence") or ""))
    return stats


def build_test_stats(
    test_cases_path: Path,
    assertion_by_test: Dict[Tuple[str, str], Dict[str, str]],
    include_frameworks: Set[str],
) -> Dict[str, Dict[str, Any]]:
    stats: Dict[str, Dict[str, Any]] = {}
    for row in iter_jsonl(test_cases_path):
        if not is_executable_test_case(row):
            continue
        repo = str(row.get("repo") or "")
        if not repo:
            continue
        test_id = str(row.get("test_id") or "")
        item = stats.setdefault(
            repo,
            {
                "repo": repo,
                "frameworks": Counter(),
                "confidences": [],
                "commits": Counter(),
                "num_phase2_tests": 0,
                "num_tests_with_expanded_ui_actions": 0,
                "num_tests_with_assertions": 0,
                "num_dynamic_parameterized_tests": 0,
                "num_skipped_tests": 0,
                "num_candidate_tests_for_rq6": 0,
                "candidate_file_paths": set(),
            },
        )
        item["num_phase2_tests"] += 1
        fw = normalize_framework(row.get("framework"))
        if fw:
            item["frameworks"][fw] += 1
        item["confidences"].append(str(row.get("phase1_confidence") or ""))
        if row.get("commit"):
            item["commits"][str(row.get("commit"))] += 1
        if bool(row.get("has_expanded_ui_actions")):
            item["num_tests_with_expanded_ui_actions"] += 1

        rq5 = assertion_by_test.get((repo, test_id), {})
        assertion_count = to_int(rq5.get("assertion_count"), 1 if row.get("has_direct_assertions") else 0)
        if assertion_count > 0:
            item["num_tests_with_assertions"] += 1

        dynamic_param = bool(row.get("parameterization_dynamic") or row.get("is_parameterized"))
        if dynamic_param:
            item["num_dynamic_parameterized_tests"] += 1
        skipped = is_skipped_test(row)
        if skipped:
            item["num_skipped_tests"] += 1

        if (
            fw in include_frameworks
            and bool(row.get("has_expanded_ui_actions"))
            and assertion_count > 0
            and not dynamic_param
            and not skipped
            and not bool(row.get("extraction_empty"))
        ):
            item["num_candidate_tests_for_rq6"] += 1
            if row.get("file_path"):
                item["candidate_file_paths"].add(str(row.get("file_path")))
    return stats


def exclusion_reason(row: Dict[str, Any], args: argparse.Namespace, include_frameworks: Set[str]) -> str:
    if row["framework_primary"] not in include_frameworks:
        return "unsupported_framework"
    if not row["repo_cache_exists"]:
        return "missing_repo_cache"
    if row["num_phase2_tests"] < args.min_phase2_tests:
        return "insufficient_phase2_tests"
    if row["num_tests_with_expanded_ui_actions"] < args.min_ui_action_tests:
        return "insufficient_ui_action_tests"
    if row["num_tests_with_assertions"] < args.min_assertion_tests:
        return "insufficient_assertion_tests"
    if row["num_candidate_tests_for_rq6"] < args.min_candidate_tests:
        return "insufficient_rq6_candidate_tests"
    if not args.allow_medium_confidence and row["phase1_confidence_max"] != "high":
        return "no_high_confidence_tests"
    return ""


def main() -> None:
    args = parse_args()
    phase2 = args.phase2_run_dir
    test_cases_path = phase2 / "test_cases.jsonl"
    rq5_path = phase2 / "rq5_assertion_complexity_by_test.csv"
    require_inputs([args.phase1_inventory, test_cases_path, rq5_path])
    args.out_dir.mkdir(parents=True, exist_ok=True)

    include_frameworks = {normalize_framework(f) for f in args.framework}
    inv = inventory_stats(args.phase1_inventory)
    rq5 = load_csv_by_test_id(rq5_path, fields=["assertion_count"])
    tests = build_test_stats(test_cases_path, rq5, include_frameworks)

    all_repos = sorted(set(inv) | set(tests))
    screen_rows: List[Dict[str, Any]] = []
    candidates: List[Dict[str, Any]] = []

    for repo in all_repos:
        inv_row = inv.get(repo, {})
        test_row = tests.get(repo, {})
        fw_counter = Counter()
        fw_counter.update(inv_row.get("frameworks") or {})
        fw_counter.update(test_row.get("frameworks") or {})
        commit_counter = Counter()
        commit_counter.update(inv_row.get("commits") or {})
        commit_counter.update(test_row.get("commits") or {})
        owner, name = split_repo(repo)
        cache_key = repo_cache_key(repo)
        repo_cache_path = args.repo_cache / cache_key
        row: Dict[str, Any] = {
            "repo_full_name": repo,
            "repo_cache_key": cache_key,
            "owner": owner,
            "name": name,
            "expected_commit": primary_counter_value(commit_counter),
            "framework_primary": primary_counter_value(fw_counter),
            "phase1_confidence_max": confidence_max(
                list(inv_row.get("confidences") or []) + list(test_row.get("confidences") or [])
            ),
            "num_ui_test_files": int(inv_row.get("num_ui_test_files") or 0),
            "num_phase2_tests": int(test_row.get("num_phase2_tests") or 0),
            "num_tests_with_expanded_ui_actions": int(test_row.get("num_tests_with_expanded_ui_actions") or 0),
            "num_tests_with_assertions": int(test_row.get("num_tests_with_assertions") or 0),
            "num_dynamic_parameterized_tests": int(test_row.get("num_dynamic_parameterized_tests") or 0),
            "num_skipped_tests": int(test_row.get("num_skipped_tests") or 0),
            "num_candidate_tests_for_rq6": int(test_row.get("num_candidate_tests_for_rq6") or 0),
            "num_candidate_files_for_rq6": len(test_row.get("candidate_file_paths") or []),
            "repo_cache_exists": repo_cache_path.exists(),
            "repo_cache_path": str(repo_cache_path),
        }
        reason = exclusion_reason(row, args, include_frameworks)
        row["static_candidate"] = not reason
        row["static_exclusion_reason"] = reason or None
        screen_rows.append(row)
        if row["static_candidate"]:
            candidates.append(row)

    write_jsonl(args.out_dir / "rq6_static_candidate_repos.jsonl", candidates)
    if args.include_excluded:
        write_jsonl(args.out_dir / "rq6_static_repo_screen.jsonl", screen_rows)

    summary_fields = [
        "repo_full_name",
        "repo_cache_key",
        "expected_commit",
        "framework_primary",
        "phase1_confidence_max",
        "num_ui_test_files",
        "num_phase2_tests",
        "num_tests_with_expanded_ui_actions",
        "num_tests_with_assertions",
        "num_candidate_tests_for_rq6",
        "repo_cache_exists",
        "static_candidate",
        "static_exclusion_reason",
    ]
    write_csv(args.out_dir / "rq6_static_candidate_repos_summary.csv", candidates, summary_fields)
    reason_counts = Counter(row["static_exclusion_reason"] or "candidate" for row in screen_rows)
    reason_rows = [{"reason": reason, "count": count} for reason, count in reason_counts.most_common()]
    write_csv(args.out_dir / "exclusion_reasons_summary.csv", reason_rows, ["reason", "count"])

    print(
        json.dumps(
            {
                "repos_screened": len(screen_rows),
                "static_candidates": len(candidates),
                "out_dir": str(args.out_dir),
                "exclusion_reasons": dict(reason_counts.most_common()),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
