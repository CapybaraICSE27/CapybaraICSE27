"""Streaming JSONL readers for Phase 2D."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional


def iter_jsonl(path: Path) -> Iterator[Dict[str, Any]]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def load_test_cases(path: Path) -> Dict[str, Dict[str, Any]]:
    """Load test cases keyed by test_key(repo, test_id) (small enough for full corpus)."""
    out: Dict[str, Dict[str, Any]] = {}
    for tc in iter_jsonl(path):
        repo = str(tc.get("repo") or "").strip()
        tid = str(tc.get("test_id") or "").strip()
        if repo and tid:
            tc = {**tc, "repo": repo, "test_id": tid}
            out[test_key(repo, tid)] = tc
    return out


def test_key(repo: str, test_id: str) -> str:
    return f"{str(repo or '').strip()}::{str(test_id or '').strip()}"


def resolve_feature_sources(input_dir: Path) -> Dict[str, Optional[Path]]:
    """Pick authoritative feature JSONL paths."""
    expanded = input_dir / "test_case_features_expanded.jsonl"
    direct = input_dir / "test_case_features_direct.jsonl"
    edges = input_dir / "helper_edges.jsonl"
    return {
        "expanded": expanded if expanded.exists() else None,
        "direct": direct if direct.exists() else None,
        "helper_edges": edges if edges.exists() else None,
    }


def iter_features(
    input_dir: Path,
    per_repo_dir: Optional[Path] = None,
) -> Iterator[Dict[str, Any]]:
    """
    Yield feature rows from expanded JSONL (preferred) or per-repo sidecars.
    Does not load all rows into memory.
    """
    sources = resolve_feature_sources(input_dir)
    if sources["expanded"] is not None:
        yield from iter_jsonl(sources["expanded"])
        return

    if per_repo_dir and per_repo_dir.is_dir():
        for path in sorted(per_repo_dir.glob("*.features_expanded.jsonl")):
            yield from iter_jsonl(path)
        return

    if per_repo_dir and per_repo_dir.is_dir():
        for path in sorted(per_repo_dir.glob("*.features_direct.jsonl")):
            yield from iter_jsonl(path)
        return

    if sources["direct"] is not None:
        yield from iter_jsonl(sources["direct"])


def iter_shared_hook_features(direct_path: Path) -> Iterator[Dict[str, Any]]:
    """Yield only shared hook template features from direct file (2AB fallback)."""
    if not direct_path.exists():
        return
    for f in iter_jsonl(direct_path):
        if f.get("is_shared_hook_feature") and f.get("hook_instance_key"):
            yield f


def iter_helper_edges(
    input_dir: Path,
    per_repo_dir: Optional[Path] = None,
) -> Iterator[Dict[str, Any]]:
    """Stream helper edges from merged JSONL or per-repo sidecars."""
    global_path = input_dir / "helper_edges.jsonl"
    if global_path.exists():
        yield from iter_jsonl(global_path)
        return

    repo_dir = per_repo_dir or (input_dir / "per_repo_outputs")
    if repo_dir.is_dir():
        for path in sorted(repo_dir.glob("*.helper_edges.jsonl")):
            yield from iter_jsonl(path)


def write_csv(path: Path, rows: List[Dict[str, Any]], fieldnames: List[str] | None = None) -> None:
    import csv

    if not rows:
        if fieldnames:
            with path.open("w", encoding="utf-8", newline="") as f:
                csv.DictWriter(f, fieldnames=fieldnames).writeheader()
        return
    if fieldnames is None:
        fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)
