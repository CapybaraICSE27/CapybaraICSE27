"""RQ5-B: assertion chain metrics from AST-tagged assertion events (Milestone 3)."""

from __future__ import annotations

from typing import Any, Dict, List, Set


def _i(val: Any, default: int = 0) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _has_chain_metadata(ev: Dict[str, Any]) -> bool:
    root = str(ev.get("assertion_chain_root_id") or "").strip()
    matcher = str(ev.get("assertion_matcher") or "").strip()
    chain_len = _i(ev.get("assertion_chain_length"))
    return bool(root) or bool(matcher) or chain_len > 0


def _truthy(val: Any) -> bool:
    return str(val).lower() in ("1", "true", "yes")


def build_assertion_chain_fields(assertion_events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate chained vs standalone assertion counts per test."""
    empty = {
        "standalone_assertion_count": 0,
        "chained_assertion_count": 0,
        "assertion_chain_statement_count": 0,
        "max_assertion_chain_length": 0,
        "mean_assertion_chain_length": "",
        "chained_assertion_fraction": "",
        "soft_assertion_count": 0,
        "grouped_assertion_count": 0,
        "soft_assertion_chain_count": 0,
        "grouped_assertion_chain_count": 0,
        "assertions_with_chain_fields": 0,
        "assertions_missing_chain_metadata_count": 0,
        "tagged_chained_assertion_count": 0,
        "tagged_standalone_assertion_count": 0,
        "tagged_chained_assertion_fraction": "",
    }
    if not assertion_events:
        return empty

    roots: Dict[str, int] = {}
    chain_lengths: Dict[str, int] = {}
    tagged_standalone = 0
    tagged_chained = 0
    missing_metadata = 0
    soft = 0
    grouped = 0
    soft_chains: Set[str] = set()
    grouped_chains: Set[str] = set()
    with_fields = 0

    for ev in assertion_events:
        root = str(ev.get("assertion_chain_root_id") or "").strip()
        if _truthy(ev.get("is_soft_assertion")):
            soft += 1
            if root:
                soft_chains.add(root)
        if _truthy(ev.get("is_grouped_assertion")):
            grouped += 1
            if root:
                grouped_chains.add(root)

        if not _has_chain_metadata(ev):
            missing_metadata += 1
            continue

        with_fields += 1
        chain_len = _i(ev.get("assertion_chain_length"))
        if root:
            roots[root] = roots.get(root, 0) + 1
            if chain_len:
                chain_lengths[root] = max(chain_lengths.get(root, 0), chain_len)

        if chain_len <= 1:
            tagged_standalone += 1
        else:
            tagged_chained += 1

    unique_chains = len(roots)
    max_len = max(chain_lengths.values()) if chain_lengths else 0
    mean_len = (
        round(sum(chain_lengths.values()) / len(chain_lengths), 4)
        if chain_lengths
        else ""
    )
    tagged_total = tagged_standalone + tagged_chained

    return {
        "standalone_assertion_count": tagged_standalone,
        "chained_assertion_count": tagged_chained,
        "assertion_chain_statement_count": unique_chains,
        "max_assertion_chain_length": max_len,
        "mean_assertion_chain_length": mean_len,
        "chained_assertion_fraction": round(tagged_chained / tagged_total, 6) if tagged_total else "",
        "soft_assertion_count": soft,
        "grouped_assertion_count": grouped,
        "soft_assertion_chain_count": len(soft_chains),
        "grouped_assertion_chain_count": len(grouped_chains),
        "assertions_with_chain_fields": with_fields,
        "assertions_missing_chain_metadata_count": missing_metadata,
        "tagged_chained_assertion_count": tagged_chained,
        "tagged_standalone_assertion_count": tagged_standalone,
        "tagged_chained_assertion_fraction": round(tagged_chained / tagged_total, 6) if tagged_total else "",
    }
