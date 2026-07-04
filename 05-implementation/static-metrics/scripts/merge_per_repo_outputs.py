#!/usr/bin/env python3
"""Merge per_repo_outputs/*.json into global static-metrics artifacts (no Node re-run)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SM_DIR = Path(__file__).resolve().parent.parent
if str(_SM_DIR) not in sys.path:
    sys.path.insert(0, str(_SM_DIR))

from extract_static_metrics import (  # noqa: E402
    HOOK_STATIC_METRIC_FIELDS,
    STATIC_METRICS_PAYLOAD_VERSION,
    build_validation_report,
    file_sha256,
    load_repos_file,
    navigation_row_defaults,
    sort_hook_metric_rows,
    sort_test_metric_rows,
    write_csv,
)
from navigationMetrics import (  # noqa: E402
    compute_navigation_by_test,
    resolve_navigation_feature_paths,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--repos-file",
        type=Path,
        default=None,
        help="If set, only merge repos listed (must have per_repo_outputs/<safe>.json)",
    )
    parser.add_argument(
        "--input-run-dir",
        type=Path,
        default=None,
        help="Phase 2C run dir; used for summary metadata and optional navigation recompute",
    )
    parser.add_argument(
        "--recompute-navigation",
        action="store_true",
        help="Recompute navigation/page-view fields from cached Phase 2C feature sidecars",
    )
    args = parser.parse_args()

    output_dir = args.output_dir.resolve()
    per_repo_dir = output_dir / "per_repo_outputs"
    if not per_repo_dir.is_dir():
        raise FileNotFoundError(per_repo_dir)

    if args.repos_file:
        from extract_static_metrics import safe_repo_dir

        wanted = {safe_repo_dir(r) for r in load_repos_file(args.repos_file)}
        paths = sorted(
            p for p in per_repo_dir.glob("*.json") if p.name.endswith(".json") and ".manifest." not in p.name and p.stem in wanted
        )
    else:
        paths = sorted(
            p for p in per_repo_dir.glob("*.json") if ".manifest." not in p.name
        )

    all_rows: list[dict] = []
    all_hook_rows: list[dict] = []
    repos_processed = 0

    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as err:
            print(f"Skip {path.name}: {err}", file=sys.stderr)
            continue
        repo = str(payload.get("repo") or "")
        metrics = payload.get("metrics") or []
        hooks = payload.get("hooks") or []
        repos_processed += 1
        all_rows.extend(metrics)
        for hk in hooks:
            all_hook_rows.append({"repo": repo, **hk})

    nav_source = None
    nav_feature_files = 0
    nav_joined_tests = 0
    nav_defaults = navigation_row_defaults()
    input_run = args.input_run_dir.resolve() if args.input_run_dir else None
    if args.recompute_navigation:
        if input_run is None:
            raise ValueError("--recompute-navigation requires --input-run-dir")
        repos_filter = {
            str(row.get("repo") or "").strip()
            for row in all_rows
            if str(row.get("repo") or "").strip()
        }
        nav_paths, nav_source = resolve_navigation_feature_paths(input_run, repos_filter)
        nav_feature_files = len(nav_paths)
        print(
            f"Recomputing navigation from {nav_source} ({nav_feature_files} feature files)",
            file=sys.stderr,
        )
        nav_map = compute_navigation_by_test(input_run, repos_filter=repos_filter)
        nav_joined_tests = len(nav_map)
        print(f"Navigation rows joined: {nav_joined_tests}", file=sys.stderr)
        for row in all_rows:
            gk = f"{row.get('repo')}::{row.get('test_id')}"
            row.update(nav_map.get(gk, dict(nav_defaults)))
    else:
        for row in all_rows:
            for k, v in nav_defaults.items():
                row.setdefault(k, v)

    all_rows = sort_test_metric_rows(all_rows)
    all_hook_rows = sort_hook_metric_rows(all_hook_rows)

    jsonl_path = output_dir / "test_case_static_metrics.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as f:
        for row in all_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    hook_jsonl_path = output_dir / "hook_static_metrics.jsonl"
    with hook_jsonl_path.open("w", encoding="utf-8") as f:
        for row in all_hook_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    write_csv(output_dir / "test_case_static_metrics.csv", all_rows)
    write_csv(output_dir / "hook_static_metrics.csv", all_hook_rows, HOOK_STATIC_METRIC_FIELDS)

    validation = build_validation_report(all_rows)
    node_script = _SM_DIR / "analyze_static_metrics.cjs"
    from cache_fingerprint import build_analyzer_fingerprint

    test_cases_sha = ""
    if input_run:
        tc_path = input_run / "test_cases.jsonl"
        if tc_path.exists():
            test_cases_sha = file_sha256(tc_path)

    summary = {
        "input_run_dir": str(input_run) if input_run else None,
        "repos_file": str(args.repos_file.resolve()) if args.repos_file else None,
        "static_metrics_payload_version": STATIC_METRICS_PAYLOAD_VERSION,
        "test_cases_jsonl_sha256": test_cases_sha or None,
        "analyzer_fingerprint": build_analyzer_fingerprint(node_script),
        "output_dir": str(output_dir),
        "repos_total": len(paths),
        "repos_processed": repos_processed,
        "hook_rows_total": len(all_hook_rows),
        "skipped_navigation": not bool(args.recompute_navigation),
        "navigation_feature_source": nav_source,
        "navigation_feature_files": nav_feature_files,
        "navigation_joined_tests": nav_joined_tests,
        "merge_only": True,
        **validation,
    }
    (output_dir / "static_metrics_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
