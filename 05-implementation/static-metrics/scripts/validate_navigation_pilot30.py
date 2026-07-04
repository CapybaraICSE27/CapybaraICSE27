#!/usr/bin/env python3
"""Compare pilot-30 navigation metrics to recomputation from Phase 2C sidecars."""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

_SM = Path(__file__).resolve().parent.parent
_RQ = _SM.parent / "rq_aggregation"
for p in (_SM, _RQ):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from navigationMetrics import (  # noqa: E402
    compute_navigation_by_test,
    is_navigation_feature,
    safe_repo_dir,
)

RUN = Path(
    r"<study-root>"
    r"\github_pilot_census_output\typescript__2026-05-10_09-57-24__min500stars"
    r"\phase2c_full_v39"
)
PILOT = RUN / "static_metrics_pilot_30"
METRICS = PILOT / "outputs" / "test_case_static_metrics.jsonl"
REPOS_FILE = PILOT / "stratified_repos.txt"


def load_repos() -> List[str]:
    repos = []
    for line in REPOS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            repos.append(line)
    return repos


def load_metrics() -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    with METRICS.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            gk = f"{row['repo']}::{row['test_id']}"
            out[gk] = row
    return out


def list_nav_features_for_test(repo: str, test_id: str) -> List[Dict[str, Any]]:
    stem = safe_repo_dir(repo)
    feats: List[Dict[str, Any]] = []
    for suffix in ("features_direct", "features_expanded"):
        p = RUN / "per_repo_outputs" / f"{stem}.{suffix}.jsonl"
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
                if is_navigation_feature(row):
                    feats.append({**row, "_sidecar": suffix})
    return feats


def main() -> None:
    repos = load_repos()
    metrics = load_metrics()
    recomputed = compute_navigation_by_test(RUN, repos_filter=set(repos))

    count_mismatch: List[Tuple[str, Dict[str, Any], Dict[str, Any]]] = []
    dyn_mismatch: List[str] = []
    url_mismatch: List[str] = []
    missing_in_metrics: List[str] = []
    extra_in_metrics: List[str] = []

    for gk, nav in recomputed.items():
        if gk not in metrics:
            missing_in_metrics.append(gk)
            continue

    for gk, row in metrics.items():
        repo, tid = gk.split("::", 1)
        if repo not in repos:
            continue
        nav = recomputed.get(gk) or {
            "navigation_action_count": 0,
            "dynamic_navigation_action_count": 0,
            "unique_static_url_count": 0,
            "static_url_literals_json": "[]",
            "has_dynamic_navigation": False,
            "estimated_page_or_view_count": 0,
        }
        m_count = int(row.get("navigation_action_count") or 0)
        r_count = int(nav.get("navigation_action_count") or 0)
        if m_count != r_count:
            count_mismatch.append((gk, row, nav))

        m_dyn = bool(row.get("has_dynamic_navigation"))
        r_dyn = bool(nav.get("has_dynamic_navigation"))
        if m_dyn != r_dyn:
            dyn_mismatch.append(gk)

        try:
            m_urls = set(json.loads(row.get("static_url_literals_json") or "[]"))
        except json.JSONDecodeError:
            m_urls = set()
        try:
            r_urls = set(json.loads(nav.get("static_url_literals_json") or "[]"))
        except json.JSONDecodeError:
            r_urls = set()
        if m_urls != r_urls:
            url_mismatch.append(gk)

        if m_count > 0 and r_count == 0:
            extra_in_metrics.append(gk)
        if m_count == 0 and r_count > 0:
            missing_in_metrics.append(gk)

    # Spot-check: raw nav features vs deduped count
    dedupe_issues: List[Dict[str, Any]] = []
    rng = random.Random(42)
    sample_keys = [gk for gk, row in metrics.items() if int(row.get("navigation_action_count") or 0) > 0]
    rng.shuffle(sample_keys)
    for gk in sample_keys[:15]:
        repo, tid = gk.split("::", 1)
        feats = list_nav_features_for_test(repo, tid)
        row = metrics[gk]
        m_count = int(row.get("navigation_action_count") or 0)
        # Count unique dedupe keys as navigationMetrics does
        from feature_merge import feature_dedupe_key  # noqa: WPS433

        seen = set()
        for f in feats:
            seen.add(feature_dedupe_key(repo, tid, f))
        if len(seen) != m_count and len(feats) != m_count:
            dedupe_issues.append(
                {
                    "gk": gk,
                    "metrics_count": m_count,
                    "raw_nav_features": len(feats),
                    "dedupe_keys": len(seen),
                    "samples": [
                        {
                            "name": f.get("name"),
                            "line": f.get("line"),
                            "raw_code": (f.get("raw_code") or "")[:120],
                            "source_kind": f.get("source_kind"),
                            "sidecar": f.get("_sidecar"),
                        }
                        for f in feats[:5]
                    ],
                }
            )

    # False-positive probe: ui_action with goto in name but NOT navigation class
    suspicious_not_nav: List[Dict[str, Any]] = []
    for repo in repos[:10]:
        stem = safe_repo_dir(repo)
        p = RUN / "per_repo_outputs" / f"{stem}.features_direct.jsonl"
        if not p.exists():
            continue
        with p.open(encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                if row.get("feature_type") != "ui_action":
                    continue
                raw = str(row.get("raw_code") or "").lower()
                name = str(row.get("name") or "").lower()
                if not any(x in raw or x in name for x in ("goto", "visit", "navigateto", ".url(")):
                    continue
                if not is_navigation_feature(row):
                    suspicious_not_nav.append(
                        {
                            "repo": row.get("repo"),
                            "test_id": row.get("test_id"),
                            "name": row.get("name"),
                            "raw_code": (row.get("raw_code") or "")[:100],
                            "line": row.get("line"),
                        }
                    )
                    if len(suspicious_not_nav) >= 8:
                        break
        if len(suspicious_not_nav) >= 8:
            break

    # Assertion features with URL oracles (not counted in nav metrics)
    url_assertions: List[Dict[str, Any]] = []
    for repo in repos[:15]:
        stem = safe_repo_dir(repo)
        p = RUN / "per_repo_outputs" / f"{stem}.features_direct.jsonl"
        if not p.exists():
            continue
        with p.open(encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                if row.get("feature_type") != "assertion":
                    continue
                raw = str(row.get("raw_code") or "").lower()
                if "haveurl" in raw or "waitforurl" in raw:
                    url_assertions.append(
                        {
                            "repo": row.get("repo"),
                            "test_id": row.get("test_id"),
                            "name": row.get("name"),
                            "raw_code": (row.get("raw_code") or "")[:100],
                        }
                    )
                    if len(url_assertions) >= 5:
                        break
        if len(url_assertions) >= 5:
            break

    report = {
        "repos": len(repos),
        "metrics_rows": len(metrics),
        "recomputed_nav_tests": len(recomputed),
        "metrics_with_nav": sum(1 for r in metrics.values() if int(r.get("navigation_action_count") or 0) > 0),
        "count_mismatch": len(count_mismatch),
        "dyn_mismatch": len(dyn_mismatch),
        "url_literals_mismatch": len(url_mismatch),
        "count_mismatch_samples": [
            {
                "gk": gk,
                "metrics": int(row.get("navigation_action_count") or 0),
                "recomputed": int(nav.get("navigation_action_count") or 0),
                "file_path": row.get("file_path"),
            }
            for gk, row, nav in count_mismatch[:10]
        ],
        "dedupe_spot_check_issues": dedupe_issues,
        "goto_like_not_classified_navigation": suspicious_not_nav[:8],
        "url_assertion_features_not_in_nav_count": url_assertions[:5],
    }

    out_path = PILOT / "navigation_validation_report.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2))

    # Manual spot-check narratives for high-nav tests
    print("\n=== SPOT CHECKS (high navigation_action_count) ===")
    high = sorted(
        ((gk, metrics[gk]) for gk in metrics if int(metrics[gk].get("navigation_action_count") or 0) >= 5),
        key=lambda x: -int(x[1].get("navigation_action_count") or 0),
    )[:5]
    for gk, row in high:
        repo, tid = gk.split("::", 1)
        feats = list_nav_features_for_test(repo, tid)
        print(f"\n{gk} count={row.get('navigation_action_count')} dynamic={row.get('has_dynamic_navigation')}")
        print(f"  file: {row.get('file_path')}")
        print(f"  urls: {row.get('static_url_literals_json', '')[:200]}")
        for f in feats[:8]:
            print(
                f"  - L{f.get('line')} [{f.get('_sidecar')}] {f.get('name')}: {(f.get('raw_code') or '')[:90]}"
            )


if __name__ == "__main__":
    main()
