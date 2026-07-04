#!/usr/bin/env python3
"""Scan pilot-30 for navigation false positives (substring 'visit' etc.)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_SM = Path(__file__).resolve().parent.parent
_RQ = _SM.parent / "rq_aggregation"
for p in (_SM, _RQ):
    sys.path.insert(0, str(p))

from navigationMetrics import is_navigation_feature, safe_repo_dir  # noqa: E402

RUN = Path(
    r"<study-root>"
    r"\github_pilot_census_output\typescript__2026-05-10_09-57-24__min500stars"
    r"\phase2c_full_v39"
)
PILOT = RUN / "static_metrics_pilot_30"
from classify import is_navigation_call  # noqa: E402

repos = [
    r.strip()
    for r in (PILOT / "stratified_repos.txt").read_text(encoding="utf-8").splitlines()
    if r.strip() and not r.startswith("#")
]

false_pos: list[dict] = []
total_nav = 0
fp = 0
for repo in repos:
    for suffix in ("features_direct", "features_expanded"):
        p = RUN / "per_repo_outputs" / f"{safe_repo_dir(repo)}.{suffix}.jsonl"
        if not p.exists():
            continue
        with p.open(encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                if row.get("feature_type") != "ui_action":
                    continue
                if not is_navigation_feature(row):
                    continue
                total_nav += 1
                if not is_navigation_call(row.get("name") or "", row.get("raw_code") or ""):
                    fp += 1
                    if len(false_pos) < 20:
                        false_pos.append(
                            {
                                "repo": repo,
                                "test_id": row.get("test_id"),
                                "line": row.get("line"),
                                "name": row.get("name"),
                                "raw_code": (row.get("raw_code") or "")[:120],
                                "sidecar": suffix,
                            }
                        )

tests_fp: set[str] = set()
tests_nav: set[str] = set()
for repo in repos:
    for suffix in ("features_direct", "features_expanded"):
        p = RUN / "per_repo_outputs" / f"{safe_repo_dir(repo)}.{suffix}.jsonl"
        if not p.exists():
            continue
        with p.open(encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                if row.get("feature_type") != "ui_action":
                    continue
                if not is_navigation_feature(row):
                    continue
                gk = f"{repo}::{row.get('test_id')}"
                tests_nav.add(gk)
                if not is_navigation_call(row.get("name") or "", row.get("raw_code") or ""):
                    tests_fp.add(gk)

metrics_nav: set[str] = set()
dyn_empty_urls = 0
dyn_total = 0
metrics_path = PILOT / "outputs" / "test_case_static_metrics.jsonl"
with metrics_path.open(encoding="utf-8") as f:
    for line in f:
        row = json.loads(line)
        if int(row.get("navigation_action_count") or 0) <= 0:
            continue
        gk = f"{row['repo']}::{row['test_id']}"
        metrics_nav.add(gk)
        if row.get("has_dynamic_navigation"):
            dyn_total += 1
            urls = json.loads(row.get("static_url_literals_json") or "[]")
            if not urls:
                dyn_empty_urls += 1

print(f"pilot30 nav ui_action lines (pre-dedupe): {total_nav}")
print(f"likely false positives: {fp} ({100*fp/max(total_nav,1):.1f}%)")
print(f"tests with >=1 likely FP nav feature: {len(tests_fp)} / {len(metrics_nav)} nav tests")
print(f"dynamic nav tests with empty static_url_literals: {dyn_empty_urls} / {dyn_total}")
for x in false_pos[:15]:
    print(f"  {x['repo']} L{x['line']} [{x['sidecar']}] {x['name']}: {x['raw_code']}")
