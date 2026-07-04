#!/usr/bin/env python3
"""Stratified sample of tests for manual RQ3 pattern validation."""

from __future__ import annotations

import argparse
import csv
import json
import random
from collections import defaultdict
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--patterns-by-test", required=True, help="rq3_patterns_by_test.csv")
    ap.add_argument("--output", required=True, help="Output sample CSV")
    ap.add_argument("--per-archetype", type=int, default=15)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    by_arch: dict[str, list[dict]] = defaultdict(list)
    with Path(args.patterns_by_test).open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            by_arch[row.get("workflow_archetype") or "mixed_or_unclear"].append(row)

    rng = random.Random(args.seed)
    sample = []
    for arch, rows in sorted(by_arch.items()):
        rng.shuffle(rows)
        sample.extend(rows[: args.per_archetype])

    fields = list(sample[0].keys()) if sample else []
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields + ["manual_notes"])
        w.writeheader()
        for row in sample:
            row["manual_notes"] = ""
            w.writerow(row)

    print(json.dumps({"archetypes": len(by_arch), "sample_size": len(sample)}, indent=2))


if __name__ == "__main__":
    main()
