"""Feature deduplication and hook attachment (fallback when expanded JSONL absent)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterator, List, Set

from stream_io import iter_jsonl


def helper_edge_dedupe_key(e: Dict[str, Any]) -> str:
    """Dedupe key for helper_edges rows (matches phase2c helperEdgeUtils.js)."""
    resolved = e.get("resolved")
    if resolved is True:
        resolved_s = "1"
    elif resolved is False:
        resolved_s = "0"
    else:
        resolved_s = str(resolved or "")
    return "|".join(
        [
            str(e.get("repo") or "").strip(),
            str(e.get("test_id") or "").strip(),
            str(e.get("hook_instance_key") or ""),
            str(e.get("from") or ""),
            str(e.get("to") or ""),
            str(e.get("target_file") or ""),
            str(e.get("depth") or ""),
            resolved_s,
        ]
    )


def feature_dedupe_key(repo: str, test_id: str, f: Dict[str, Any]) -> str:
    repo = str(repo or "").strip()
    test_id = str(test_id or "").strip()
    raw = str(f.get("raw_code") or "")[:400]
    return "|".join(
        [
            repo,
            test_id,
            str(f.get("feature_type", "")),
            str(f.get("name", "")),
            str(f.get("line", "")),
            str(f.get("source_kind", "")),
            str(f.get("helper_depth", 0)),
            str(f.get("target_file", "")),
            str(f.get("hook_instance_key", "")),
            str(f.get("attached_from_hook", False)),
            raw,
        ]
    )


def is_direct_test_body_feature(f: Dict[str, Any]) -> bool:
    """True for in-test-body rows from the direct (2B) feature file."""
    if f.get("is_shared_hook_feature"):
        return False
    if not f.get("test_id"):
        return False
    if f.get("attached_from_hook"):
        return False
    if int(f.get("helper_depth") or 0) > 0:
        return False
    return str(f.get("source_kind") or "") == "test_body"


def iter_direct_test_body_features(path) -> Iterator[Dict[str, Any]]:
    """Yield non-shared test_body features from test_case_features_direct.jsonl."""
    if not path or not path.exists():
        return
    for f in iter_jsonl(path):
        if is_direct_test_body_feature(f):
            yield f


def iter_direct_non_shared_features(path) -> Iterator[Dict[str, Any]]:
    """Yield all non-shared direct features with a test_id (2AB-only fallback)."""
    if not path or not path.exists():
        return
    for f in iter_jsonl(path):
        if f.get("is_shared_hook_feature"):
            continue
        if f.get("test_id"):
            yield f


def iter_deduped_features(
    features: Iterator[Dict[str, Any]],
    seen: Set[str] | None = None,
) -> Iterator[Dict[str, Any]]:
    if seen is None:
        seen = set()
    for f in features:
        repo = str(f.get("repo") or "").strip()
        tid = str(f.get("test_id") or "").strip()
        if not repo or not tid:
            continue
        dk = feature_dedupe_key(repo, tid, f)
        if dk in seen:
            continue
        seen.add(dk)
        yield f


def iter_hook_attached_features(
    test_cases: Dict[str, Dict[str, Any]],
    hook_by_key: Dict[str, List[Dict[str, Any]]],
    seen: Set[str],
) -> Iterator[Dict[str, Any]]:
    """Attach shared hook features to tests (2AB-only fallback)."""
    for key, tc in test_cases.items():
        repo = str(tc.get("repo") or "").strip()
        tid = str(tc.get("test_id") or "").strip()
        if not repo or not tid:
            continue
        for hk in tc.get("hook_instance_keys") or []:
            hk_str = str(hk)
            for f in hook_by_key.get(hk_str, []):
                row = {
                    **f,
                    "test_id": tid,
                    "repo": repo,
                    "attached_from_hook": True,
                    "is_shared_hook_feature": False,
                }
                dk = feature_dedupe_key(repo, tid, row)
                if dk in seen:
                    continue
                seen.add(dk)
                yield row


def build_hook_by_key_from_direct(direct_path) -> Dict[str, List[Dict[str, Any]]]:

    hook_by_key: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    if not direct_path or not direct_path.exists():
        return hook_by_key
    for f in iter_jsonl(direct_path):
        if f.get("is_shared_hook_feature") and f.get("hook_instance_key"):
            hook_by_key[str(f["hook_instance_key"])].append(f)
    return hook_by_key
