#!/usr/bin/env python3
"""Compare RQ3 distribution CSVs between two Phase 2D run directories."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Dict, List


def read_distribution(path: Path, key_col: str, count_col: str = "count") -> Dict[str, int]:
    if not path.exists():
        return {}
    out: Dict[str, int] = {}
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            key = (row.get(key_col) or "").strip()
            if not key:
                continue
            out[key] = int(float(row.get(count_col) or 0))
    return out


def counter_from_events(path: Path, col: str) -> Counter:
    c: Counter = Counter()
    if not path.exists():
        return c
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            c[(row.get(col) or "").strip() or "unknown"] += 1
    return c


def delta_table(old: Dict[str, int], new: Dict[str, int]) -> List[Dict[str, object]]:
    keys = sorted(set(old) | set(new))
    rows = []
    for k in keys:
        o = old.get(k, 0)
        n = new.get(k, 0)
        rows.append({
            "label": k,
            "old_count": o,
            "new_count": n,
            "delta": n - o,
            "delta_pct": round((n - o) / o * 100, 2) if o else None,
        })
    rows.sort(key=lambda r: (-abs(int(r["delta"])), str(r["label"])))
    return rows


def write_csv(path: Path, rows: List[Dict[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fields)
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--old-dir", type=Path, required=True)
    ap.add_argument("--new-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, default=None)
    args = ap.parse_args()

    old_dir = args.old_dir.resolve()
    new_dir = args.new_dir.resolve()
    out_dir = (args.out_dir or (new_dir / "rq3_compare_vs_old")).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    comparisons = [
        ("workflow_archetype", old_dir / "review_bundle_rq3" / "workflow_archetype_distribution.csv",
         new_dir / "review_bundle_rq3" / "workflow_archetype_distribution.csv", "workflow_archetype"),
        ("workflow_abstraction_events", old_dir / "rq3_workflow_pattern_events.csv",
         new_dir / "rq3_workflow_pattern_events.csv", "abstraction_kind"),
    ]

    for name, old_path, new_path, col in comparisons:
        new_dist = new_dir / "review_bundle_rq3" / f"{col}_distribution.csv"
        if col == "workflow_archetype":
            new_dist = new_dir / "review_bundle_rq3" / "workflow_archetype_distribution.csv"
        if old_path.name.endswith("_distribution.csv") or "distribution" in old_path.name:
            old = read_distribution(old_path, col if col != "workflow_archetype" else "workflow_archetype")
            new = read_distribution(new_dist, col if col != "workflow_archetype" else "workflow_archetype")
        else:
            old = dict(counter_from_events(old_path, col))
            new = dict(counter_from_events(new_path, col))
        write_csv(out_dir / f"delta_{name}.csv", delta_table(old, new))

    old_summary = json.loads((old_dir / "rq_aggregation_summary.json").read_text(encoding="utf-8"))
    new_summary = json.loads((new_dir / "rq_aggregation_summary.json").read_text(encoding="utf-8"))
    summary_keys = [
        "test_cases", "rq3_locator_events", "rq3_sync_events", "rq3_workflow_events",
        "rq3_ast_provenance",
    ]
    compare_summary = {
        "old_dir": str(old_dir),
        "new_dir": str(new_dir),
        "old": {k: old_summary.get(k) for k in summary_keys},
        "new": {k: new_summary.get(k) for k in summary_keys},
    }
    (out_dir / "summary_compare.json").write_text(json.dumps(compare_summary, indent=2), encoding="utf-8")
    print(json.dumps(compare_summary, indent=2))


if __name__ == "__main__":
    main()
