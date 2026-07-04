"""Feature-derived navigation / page-view heuristics (Phase 2 static metrics)."""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

# Reuse the same dedupe + interaction classification as Phase 2D.
_RQ_DIR = Path(__file__).resolve().parent.parent / "rq_aggregation"
if str(_RQ_DIR) not in sys.path:
    sys.path.insert(0, str(_RQ_DIR))

from classify import classify_interaction  # noqa: E402
from feature_merge import feature_dedupe_key  # noqa: E402

_SM_DIR = Path(__file__).resolve().parent
if str(_SM_DIR) not in sys.path:
    sys.path.insert(0, str(_SM_DIR))
from jsonl_utils import iter_jsonl_objects  # noqa: E402

# First string literal after navigation-like callee (allows options / extra args).
_NAV_FIRST_LITERAL = re.compile(
    r"(?:\bpage\.goto|\bcy\.visit|\.goto|\.visit|\.navigateTo)\s*\(\s*"
    r"((?:'[^']*')|(?:\"[^\"]*\")|(?:`[^`${]*`))",
    re.IGNORECASE,
)
_URL_FROM_METHOD = re.compile(
    r"(?:browser\.url|page\.waitForURL|toHaveURL|expect\s*\([^)]*\)\.(?:soft\.)?(?:toHaveURL))"
    r"[^`'\"]{0,40}([`'\"])([^`'\"]*?)\1",
    re.IGNORECASE,
)


def safe_repo_dir(full_name: str) -> str:
    return full_name.replace("/", "__").replace(":", "_")


def _strip_quotes(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] in "'\"`" and s[-1] == s[0]:
        return s[1:-1].strip()
    return s


def extract_static_urls_from_raw(raw: str) -> Tuple[Set[str], bool]:
    """Return unique static-ish URL/path strings and whether raw has obvious template/string-build."""
    if not raw:
        return set(), False
    tpl_dynamic = bool(re.search(r"\$\{|`[^`]*\$\{|[\"']\s*\+|\+\s*[\"']", raw))
    urls: Set[str] = set()
    for m in _NAV_FIRST_LITERAL.finditer(raw):
        inner = _strip_quotes(m.group(1) or "")
        if inner:
            urls.add(inner)
    for m in _URL_FROM_METHOD.finditer(raw):
        inner = _strip_quotes((m.group(2) or "").strip())
        if inner:
            urls.add(inner)
    expr_dynamic = bool(
        re.search(
            r"(?:\bpage\.goto|\bcy\.visit|\.goto|\.visit|\.navigateTo)\s*\(\s*"
            r"(?:[a-zA-Z_$][\w$]*|\{)",
            raw,
        )
    )
    dynamic = tpl_dynamic or (not urls and expr_dynamic)
    return urls, dynamic


def is_navigation_feature(f: Dict[str, Any]) -> bool:
    if str(f.get("feature_type") or "") != "ui_action":
        return False
    name = str(f.get("name") or "")
    raw = str(f.get("raw_code") or "")
    return classify_interaction(name, raw) == "navigation"


def _ui_action_line_predicate(line: str) -> bool:
    return '"ui_action"' in line or '"feature_type"' not in line


def iter_jsonl_navigation_candidates(
    path: Path,
    repos_filter: Set[str] | None = None,
) -> Iterable[Dict[str, Any]]:
    """Stream JSONL; repo filter tolerates compact JSON (no space after colon)."""
    yield from iter_jsonl_objects(
        path,
        repos_filter=repos_filter,
        extra_line_predicate=_ui_action_line_predicate,
    )


_SIDECAR_SUBSET_MAX_REPOS = 120


def _collect_sidecar_feature_paths(
    per_repo_dir: Path,
    repos_filter: Set[str] | None,
) -> List[Path]:
    if not per_repo_dir.is_dir():
        return []
    paths: List[Path] = []
    suffixes = ("features_direct", "features_expanded")
    if repos_filter is None:
        for suffix in suffixes:
            paths.extend(sorted(per_repo_dir.glob(f"*.{suffix}.jsonl")))
        return sorted(paths)
    for repo in sorted(repos_filter):
        stem = safe_repo_dir(repo)
        for suffix in suffixes:
            p = per_repo_dir / f"{stem}.{suffix}.jsonl"
            if p.exists():
                paths.append(p)
    return paths


def resolve_navigation_feature_paths(
    input_run_dir: Path,
    repos_filter: Set[str] | None,
) -> Tuple[List[Path], str]:
    """
    Prefer per-repo Phase 2C sidecars when scanning a subset (avoids 4M+ line global files).
    Fall back to sidecars for full runs that did not materialize merged feature JSONL files.
    Returns (paths, source_label).
    """
    per_repo_dir = input_run_dir / "per_repo_outputs"
    if (
        repos_filter is not None
        and len(repos_filter) <= _SIDECAR_SUBSET_MAX_REPOS
        and per_repo_dir.is_dir()
    ):
        paths = _collect_sidecar_feature_paths(per_repo_dir, repos_filter)
        if paths:
            return paths, "per_repo_sidecars"

    global_paths: List[Path] = []
    for name in ("test_case_features_direct.jsonl", "test_case_features_expanded.jsonl"):
        p = input_run_dir / name
        if p.exists():
            global_paths.append(p)
    if global_paths:
        return global_paths, "global_merged"

    sidecar_paths = _collect_sidecar_feature_paths(per_repo_dir, repos_filter)
    if sidecar_paths:
        return sidecar_paths, "per_repo_sidecars_fallback"
    return [], "missing"


def compute_navigation_by_test(
    input_run_dir: Path,
    repos_filter: Set[str] | None = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Stream direct + expanded features with global dedupe (same as 2D).
    Key: repo::test_id
    """
    feature_paths, _source = resolve_navigation_feature_paths(input_run_dir, repos_filter)

    by_key: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {
            "navigation_action_count": 0,
            "dynamic_navigation_action_count": 0,
            "static_url_literals": set(),  # type: ignore
            "has_dynamic_navigation": False,
        }
    )
    seen: Set[str] = set()

    # Sidecar files contain a single repo; no need for line-level repo filter.
    line_repo_filter: Set[str] | None = repos_filter if _source == "global_merged" else None

    for path in feature_paths:
        for f in iter_jsonl_navigation_candidates(path, line_repo_filter):
            repo = str(f.get("repo") or "")
            tid = str(f.get("test_id") or "")
            if not tid:
                continue
            if repos_filter is not None and repo not in repos_filter:
                continue
            dk = feature_dedupe_key(repo, tid, f)
            if dk in seen:
                continue
            if not is_navigation_feature(f):
                continue
            seen.add(dk)
            gk = f"{repo}::{tid}"
            row = by_key[gk]
            row["navigation_action_count"] += 1
            raw = str(f.get("raw_code") or "")
            static_urls, row_dynamic = extract_static_urls_from_raw(raw)
            if row_dynamic:
                row["has_dynamic_navigation"] = True
                row["dynamic_navigation_action_count"] += 1
            row["static_url_literals"].update(static_urls)  # type: ignore

    out: Dict[str, Dict[str, Any]] = {}
    for gk, row in by_key.items():
        literals: Set[str] = row["static_url_literals"]  # type: ignore
        nav_n = int(row["navigation_action_count"])
        dyn_n = int(row["dynamic_navigation_action_count"])
        uniq_static = len(literals)
        est = uniq_static + dyn_n
        out[gk] = {
            "navigation_action_count": nav_n,
            "dynamic_navigation_action_count": dyn_n,
            "unique_static_url_count": uniq_static,
            "static_url_literals_json": json.dumps(sorted(literals), ensure_ascii=False)[:2000],
            "has_dynamic_navigation": bool(row["has_dynamic_navigation"]),
            "estimated_page_or_view_count": est,
        }
    return out


def navigation_row_defaults() -> Dict[str, Any]:
    return {
        "navigation_action_count": 0,
        "dynamic_navigation_action_count": 0,
        "unique_static_url_count": 0,
        "static_url_literals_json": "[]",
        "has_dynamic_navigation": False,
        "estimated_page_or_view_count": 0,
    }
