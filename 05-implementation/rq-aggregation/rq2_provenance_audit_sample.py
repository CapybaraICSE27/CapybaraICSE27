"""Stratified audit samples for RQ2 provenance gate validation."""

from __future__ import annotations

import csv
import random
from pathlib import Path
from typing import Dict, List

from rq2_audit_fields import PROVENANCE_AUDIT_FIELDS
from rq2_provenance_gates import (
    VARIABLE_LIKE_SOURCES,
    _is_true_static_file_candidate,
    _origin_resolved,
    _static_file_linked,
)


def _sample(rows: List[Dict[str, str]], n: int, seed: int) -> List[Dict[str, str]]:
    if not rows:
        return []
    rng = random.Random(seed)
    picked = rows if len(rows) <= n else rng.sample(rows, n)
    return picked


def _audit_row(bucket: str, row: Dict[str, str]) -> Dict[str, str]:
    out = {"audit_bucket": bucket}
    for field in PROVENANCE_AUDIT_FIELDS:
        if field == "audit_bucket":
            continue
        out[field] = row.get(field, "")
    return out


def build_audit_samples(events_path: Path, output_dir: Path, sample_size: int = 30, seed: int = 42) -> Path:
    rows = list(csv.DictReader(events_path.open(encoding="utf-8")))

    static_true = [r for r in rows if _is_true_static_file_candidate(r)]
    static_unresolved = [r for r in static_true if not _static_file_linked(r)]
    static_resolved = [r for r in static_true if _static_file_linked(r)]

    variable_like = [r for r in rows if (r.get("input_source_class") or "") in VARIABLE_LIKE_SOURCES]
    origin_resolved = [r for r in variable_like if _origin_resolved(r)]

    visible_unclear = [
        r
        for r in rows
        if (r.get("value_visibility") or "") == "visible"
        and (r.get("input_plausibility") or "") in ("unclear", "needs_review")
    ]

    buckets = [
        ("static_file_unresolved", _sample(static_unresolved, sample_size, seed)),
        ("static_file_resolved", _sample(static_resolved, sample_size, seed + 1)),
        ("variable_origin_resolved", _sample(origin_resolved, sample_size, seed + 2)),
        ("visible_plausibility_unclear", _sample(visible_unclear, sample_size, seed + 3)),
    ]

    out_rows: List[Dict[str, str]] = []
    for bucket, sampled in buckets:
        for row in sampled:
            out_rows.append(_audit_row(bucket, row))

    out_path = output_dir / "rq2_provenance_audit_sample.csv"
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=PROVENANCE_AUDIT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(out_rows)

    summary_path = output_dir / "rq2_provenance_audit_sample_summary.json"
    summary = {
        "sample_size_per_bucket": sample_size,
        "population_counts": {
            "static_file_true_candidates": len(static_true),
            "static_file_unresolved": len(static_unresolved),
            "static_file_resolved": len(static_resolved),
            "variable_origin_resolved": len(origin_resolved),
            "visible_plausibility_unclear": len(visible_unclear),
        },
        "sampled_counts": {name: len(sampled) for name, sampled in buckets},
        "output_csv": str(out_path),
    }
    summary_path.write_text(__import__("json").dumps(summary, indent=2), encoding="utf-8")
    return out_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate RQ2 provenance audit samples")
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--sample-size", type=int, default=30)
    args = parser.parse_args()
    events = args.input_dir / "rq2_input_events.csv"
    path = build_audit_samples(events, args.input_dir, sample_size=args.sample_size)
    print(path)
