#!/usr/bin/env python3
"""Stratified manual-review bundle for static-metrics pilot (with source + nav evidence)."""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

_SM = Path(__file__).resolve().parent.parent
_RQ = _SM.parent / "rq_aggregation"
for p in (_SM, _RQ):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from extract_static_metrics import safe_repo_dir, iter_jsonl  # noqa: E402
from navigationMetrics import is_navigation_feature  # noqa: E402

REPO_CACHE_DEFAULT = Path(r"<repo-cache>")


def load_metrics(path: Path) -> List[Dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def slice_source(repo_cache: Path, repo: str, file_path: str, start: int, end: int) -> str:
    abs_path = repo_cache / safe_repo_dir(repo) / file_path.replace("\\", "/")
    if not abs_path.exists():
        return ""
    lines = abs_path.read_text(encoding="utf-8", errors="replace").splitlines()
    s = max(1, start or 1)
    e = min(len(lines), end or len(lines))
    if e < s:
        return ""
    chunk = lines[s - 1 : e]
    numbered = [f"{s + i:5d}| {chunk[i]}" for i in range(len(chunk))]
    return "\n".join(numbered)


def nav_features_for_test(
    input_run: Path, repo: str, test_id: str, limit: int = 12
) -> List[Dict[str, Any]]:
    stem = safe_repo_dir(repo)
    out: List[Dict[str, Any]] = []
    for suffix in ("features_direct", "features_expanded"):
        p = input_run / "per_repo_outputs" / f"{stem}.{suffix}.jsonl"
        if not p.exists():
            continue
        with p.open(encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                row = json.loads(line)
                if row.get("test_id") != test_id:
                    continue
                if row.get("feature_type") != "ui_action":
                    continue
                if not is_navigation_feature(row):
                    continue
                out.append(
                    {
                        "sidecar": suffix,
                        "line": row.get("line"),
                        "name": row.get("name"),
                        "raw_code": (row.get("raw_code") or "")[:200],
                        "source_kind": row.get("source_kind"),
                    }
                )
                if len(out) >= limit:
                    return out
    return out


def stratify_bucket(row: Dict[str, Any]) -> str:
    ncloc = int(row.get("test_body_ncloc") or 0)
    if ncloc <= 10:
        sz = "ncloc_small"
    elif ncloc <= 40:
        sz = "ncloc_medium"
    else:
        sz = "ncloc_large"
    fw = str(row.get("framework") or "other").lower()
    if "playwright" in fw:
        fwb = "playwright"
    elif "cypress" in fw:
        fwb = "cypress"
    else:
        fwb = "other"
    hooks = "has_hooks" if int(row.get("hook_count") or 0) > 0 else "no_hooks"
    nav = "has_nav" if int(row.get("navigation_action_count") or 0) > 0 else "no_nav"
    status = str(row.get("metrics_status") or "unknown")
    if status != "ok":
        return f"status_{status}"
    return f"{fwb}:{sz}:{hooks}:{nav}"


def pick_one_per_repo(rows: List[Dict[str, Any]], seed: int) -> Set[str]:
    """One random ok test per repo (deterministic by seed)."""
    by_repo: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        repo = str(r.get("repo") or "").strip()
        if repo:
            by_repo[repo].append(r)
    rng = random.Random(seed)
    keys: Set[str] = set()
    for repo in sorted(by_repo.keys()):
        pool = by_repo[repo][:]
        rng.shuffle(pool)
        r = pool[0]
        keys.add(f"{r['repo']}::{r['test_id']}")
    return keys


def pick_sample(
    rows: List[Dict[str, Any]],
    n: int,
    seed: int,
    must_include: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    must_include = must_include or set()
    if must_include:
        n = max(n, len(must_include))
    by_bucket: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        gk = f"{r['repo']}::{r['test_id']}"
        if gk in must_include:
            continue
        by_bucket[stratify_bucket(r)].append(r)

    rng = random.Random(seed)
    selected: List[Dict[str, Any]] = []
    selected_keys: Set[str] = set(must_include)

    for gk in must_include:
        for r in rows:
            if f"{r['repo']}::{r['test_id']}" == gk:
                selected.append(r)
                break

    buckets = sorted(by_bucket.keys())
    rng.shuffle(buckets)
    per = max(1, n // max(len(buckets), 1))

    for b in buckets:
        pool = by_bucket[b][:]
        rng.shuffle(pool)
        for r in pool:
            if len(selected) >= n:
                break
            gk = f"{r['repo']}::{r['test_id']}"
            if gk in selected_keys:
                continue
            selected_keys.add(gk)
            selected.append(r)
        if len(selected) >= n:
            break

    if len(selected) < n:
        rest = [r for r in rows if f"{r['repo']}::{r['test_id']}" not in selected_keys]
        rng.shuffle(rest)
        for r in rest:
            if len(selected) >= n:
                break
            selected.append(r)

    return selected[:n]


def build_review_row(
    row: Dict[str, Any],
    input_run: Path,
    repo_cache: Path,
) -> Dict[str, Any]:
    repo = str(row["repo"])
    test_id = str(row["test_id"])
    start = int(row.get("callback_start_line") or 0)
    end = int(row.get("callback_end_line") or 0)
    return {
        "repo": repo,
        "test_id": test_id,
        "file_path": row.get("file_path"),
        "test_name": (row.get("test_name") or "")[:120],
        "framework": row.get("framework"),
        "metrics_status": row.get("metrics_status"),
        "callback_start_line": start,
        "callback_end_line": end,
        "test_body_loc": row.get("test_body_loc"),
        "test_body_ncloc": row.get("test_body_ncloc"),
        "test_body_cyclomatic_basic": row.get("test_body_cyclomatic_basic"),
        "test_body_cyclomatic_extended": row.get("test_body_cyclomatic_extended"),
        "hook_count": row.get("hook_count"),
        "hook_metrics_unresolved_count": row.get("hook_metrics_unresolved_count"),
        "hook_ncloc_total": row.get("hook_ncloc_total"),
        "navigation_action_count": row.get("navigation_action_count"),
        "dynamic_navigation_action_count": row.get("dynamic_navigation_action_count"),
        "has_dynamic_navigation": row.get("has_dynamic_navigation"),
        "unique_static_url_count": row.get("unique_static_url_count"),
        "static_url_literals_json": row.get("static_url_literals_json"),
        "estimated_page_or_view_count": row.get("estimated_page_or_view_count"),
        "stratum": stratify_bucket(row),
        "source_slice": slice_source(repo_cache, repo, str(row.get("file_path") or ""), start, end),
        "navigation_features": nav_features_for_test(input_run, repo, test_id),
        "review_checklist": [
            "callback_slice_matches_test_body",
            "ncloc_plausible_for_slice",
            "cyclomatic_plausible",
            "hook_totals_match_resolved_hooks",
            "navigation_count_matches_features",
        ],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--input-run-dir", type=Path, required=True)
    ap.add_argument("--repo-cache", type=Path, default=REPO_CACHE_DEFAULT)
    ap.add_argument("--sample-size", type=int, default=60)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument(
        "--must-include-repos",
        type=str,
        default="Monogatari/Monogatari,springload/react-accessible-accordion",
    )
    ap.add_argument(
        "--one-per-repo",
        action="store_true",
        help="Include at least one test from every repo in metrics (raises sample size if needed)",
    )
    args = ap.parse_args()

    metrics_path = args.output_dir / "test_case_static_metrics.jsonl"
    if not metrics_path.exists():
        raise FileNotFoundError(metrics_path)

    rows = [r for r in load_metrics(metrics_path) if r.get("metrics_status") == "ok"]
    repos_in_metrics = sorted({str(r.get("repo") or "") for r in rows if r.get("repo")})
    must_keys: Set[str] = set()
    if args.one_per_repo:
        must_keys |= pick_one_per_repo(rows, args.seed)
    if not args.one_per_repo:
        must_repos = [x.strip() for x in args.must_include_repos.split(",") if x.strip()]
        per_must = max(2, args.sample_size // max(len(must_repos) * 2, 1))
        rng = random.Random(args.seed)
        for repo in must_repos:
            pool = [r for r in rows if r.get("repo") == repo]
            rng.shuffle(pool)
            for r in pool[:per_must]:
                must_keys.add(f"{r['repo']}::{r['test_id']}")

    target_n = args.sample_size
    if args.one_per_repo:
        target_n = max(target_n, len(repos_in_metrics))
    target_n = max(target_n, len(must_keys))

    non_ok = [r for r in load_metrics(metrics_path) if r.get("metrics_status") != "ok"]
    sample = pick_sample(rows, target_n, args.seed, must_include=must_keys)
    for r in non_ok:
        sample.append(r)

    bundle_dir = args.output_dir / "review_bundle"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    review_rows = [
        build_review_row(r, args.input_run_dir, args.repo_cache) for r in sample
    ]

    jsonl_path = bundle_dir / "manual_review_sample.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as f:
        for row in review_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    csv_fields = [
        "repo",
        "test_id",
        "file_path",
        "test_name",
        "metrics_status",
        "callback_start_line",
        "callback_end_line",
        "test_body_ncloc",
        "test_body_cyclomatic_basic",
        "hook_count",
        "hook_metrics_unresolved_count",
        "navigation_action_count",
        "has_dynamic_navigation",
        "stratum",
    ]
    with (bundle_dir / "manual_review_sample.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
        w.writeheader()
        for row in review_rows:
            w.writerow({k: row.get(k, "") for k in csv_fields})

    repos_in_sample = sorted({str(r.get("repo") or "") for r in review_rows if r.get("repo")})
    manifest = {
        "sample_size": len(review_rows),
        "requested_sample_size": args.sample_size,
        "target_sample_size": target_n,
        "one_per_repo": bool(args.one_per_repo),
        "repos_in_metrics": len(repos_in_metrics),
        "repos_in_sample": len(repos_in_sample),
        "repos_missing_from_sample": sorted(set(repos_in_metrics) - set(repos_in_sample)),
        "ok_in_sample": sum(1 for r in review_rows if r.get("metrics_status") == "ok"),
        "non_ok_in_sample": sum(1 for r in review_rows if r.get("metrics_status") != "ok"),
        "stratum_counts": dict(Counter(r["stratum"] for r in review_rows)),
        "seed": args.seed,
        "audit_instructions": (
            "For each row: verify source_slice, metrics, and navigation_features. "
            "Record pass/fail per checklist item in manual_audit_results.csv. "
            "Compute Wilson 95% CI for overall pass rate."
        ),
    }
    (bundle_dir / "bundle_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    audit_template = bundle_dir / "manual_audit_results.csv"
    with audit_template.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "repo",
                "test_id",
                "reviewer",
                "callback_slice_ok",
                "ncloc_ok",
                "cyclomatic_ok",
                "hooks_ok",
                "navigation_ok",
                "overall_pass",
                "notes",
            ]
        )
        for row in review_rows:
            w.writerow([row["repo"], row["test_id"], "", "", "", "", "", "", "", ""])

    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
