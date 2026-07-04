#!/usr/bin/env python3
"""Shared helpers for RQ1/RQ4/RQ5 manual review bundles."""

from __future__ import annotations

import csv
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Tuple


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: List[Dict[str, Any]], fieldnames: List[str] | None = None) -> None:
    if not rows:
        if fieldnames:
            with path.open("w", encoding="utf-8", newline="") as fh:
                csv.DictWriter(fh, fieldnames=fieldnames).writeheader()
            return
        path.write_text("", encoding="utf-8")
        return
    fields = fieldnames or list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fields})


def distribution_rows(counter: Counter, key_name: str = "value") -> List[Dict[str, Any]]:
    return [{key_name: k, "count": v} for k, v in counter.most_common()]


def stratified_sample(
    rows: List[Dict[str, str]],
    key_fn: Callable[[Dict[str, str]], Any],
    per_bucket: int,
    seed: int,
    max_total: int = 0,
) -> List[Dict[str, str]]:
    by_bucket: Dict[Any, List[Dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_bucket[key_fn(row)].append(row)
    rng = random.Random(seed)
    out: List[Dict[str, str]] = []
    for key in sorted(by_bucket.keys(), key=lambda k: str(k)):
        bucket = by_bucket[key]
        rng.shuffle(bucket)
        out.extend(bucket[:per_bucket])
    if max_total and len(out) > max_total:
        rng.shuffle(out)
        out = out[:max_total]
    return out


def framework_summary(
    rows: Iterable[Dict[str, str]],
    metric_cols: List[Tuple[str, str]],
) -> List[Dict[str, Any]]:
    """Aggregate counts and optional sum columns per framework."""
    by_fw: Dict[str, Dict[str, float]] = defaultdict(lambda: {"row_count": 0})
    for row in rows:
        fw = row.get("framework") or "Unknown"
        by_fw[fw]["row_count"] += 1
        for col, kind in metric_cols:
            val = row.get(col) or ""
            if kind == "sum":
                try:
                    by_fw[fw][col] = by_fw[fw].get(col, 0) + float(val or 0)
                except ValueError:
                    pass
    out = []
    for fw in sorted(by_fw.keys()):
        rec = {"framework": fw}
        rec.update({k: int(v) if k == "row_count" else v for k, v in by_fw[fw].items()})
        out.append(rec)
    return out


def copy_if_exists(run_dir: Path, bundle_dir: Path, names: List[str]) -> List[str]:
    copied: List[str] = []
    for name in names:
        src = run_dir / name
        if src.exists():
            import shutil

            shutil.copy2(src, bundle_dir / name)
            copied.append(name)
    return copied


def write_manifest(bundle_dir: Path, manifest: Dict[str, Any]) -> None:
    (bundle_dir / "bundle_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
