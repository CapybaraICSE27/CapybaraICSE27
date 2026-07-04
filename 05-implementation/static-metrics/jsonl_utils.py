"""Shared JSONL streaming helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Set


def line_might_match_repos(line: str, repos_filter: Optional[Set[str]]) -> bool:
    """Cheap pre-filter: repo slug appears on line (works for compact and pretty JSON)."""
    if not repos_filter:
        return True
    return any(repo in line for repo in repos_filter)


def iter_jsonl_objects(
    path: Path,
    *,
    repos_filter: Optional[Set[str]] = None,
    extra_line_predicate=None,
) -> Iterable[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            if not line_might_match_repos(line, repos_filter):
                continue
            if extra_line_predicate is not None and not extra_line_predicate(line):
                continue
            row = json.loads(line)
            if repos_filter is not None:
                repo = str(row.get("repo") or "").strip()
                if not repo or repo not in repos_filter:
                    continue
            yield row
