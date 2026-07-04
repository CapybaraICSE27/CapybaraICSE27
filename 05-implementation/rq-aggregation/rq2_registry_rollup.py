"""Roll up per-repo RQ2 registry metrics from Phase 2C analyzer summaries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


REGISTRY_KEYS = (
    "rq2_registry_load_sites",
    "rq2_registry_static_paths",
    "rq2_registry_resolved_paths",
    "rq2_registry_parse_ok",
    "rq2_registry_parse_partial",
    "rq2_registry_parse_error",
    "rq2_registry_entries",
)


def load_per_repo_registry_metrics(per_repo_dir: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not per_repo_dir.is_dir():
        return rows
    for path in sorted(per_repo_dir.glob("*.json")):
        if ".features_" in path.name:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        reg = (data.get("summary") or {}).get("rq2_registry")
        if not reg:
            continue
        rows.append({"repo": data.get("repo", path.stem), **reg})
    return rows


def summarize_registry_rollup(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not rows:
        return {}
    totals = {k: sum(int(r.get(k, 0) or 0) for r in rows) for k in REGISTRY_KEYS}
    static_paths = totals.get("rq2_registry_static_paths", 0)
    resolved = totals.get("rq2_registry_resolved_paths", 0)
    totals["rq2_registry_resolution_rate"] = round(resolved / static_paths, 4) if static_paths else 0.0
    totals["rq2_registry_repos"] = len(rows)
    return totals
