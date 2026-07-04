"""RQ5-A: assertion density derived metrics (Milestone 1)."""

from __future__ import annotations

from typing import Any, Dict, Optional


def _safe_ratio(numerator: int, denominator: Optional[int]) -> str:
    if denominator is None:
        return ""
    try:
        den = int(denominator)
    except (TypeError, ValueError):
        return ""
    if den <= 0:
        return ""
    return str(round(numerator / den, 6))


def _sm_int(static_row: Optional[Dict[str, Any]], key: str) -> Optional[int]:
    if not static_row:
        return None
    val = static_row.get(f"sm_{key}")
    if val is None or val == "":
        val = static_row.get(key)
    if val is None or val == "":
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def build_assertion_density_fields(
    *,
    assertion_count: int,
    test_body_assertion_count: int,
    direct_assertion_count: int,
    hook_assertion_count: int,
    helper_assertion_count: int,
    ui_action_count: int,
    test_body_ui_action_count: int,
    static_row: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Per-test assertion density and flag columns for rq5_assertion_complexity_by_test.csv."""
    ncloc = _sm_int(static_row, "test_body_ncloc")
    stmt = _sm_int(static_row, "test_body_statement_count")

    only_helper = (
        assertion_count > 0
        and direct_assertion_count == 0
        and hook_assertion_count == 0
        and helper_assertion_count > 0
    )

    return {
        "assertion_density_all_actions": _safe_ratio(assertion_count, ui_action_count),
        "assertion_density_test_body": _safe_ratio(
            test_body_assertion_count, test_body_ui_action_count
        ),
        "assertion_density_per_ncloc": _safe_ratio(assertion_count, ncloc),
        "assertion_density_per_statement": _safe_ratio(assertion_count, stmt),
        "tests_with_no_assertions": 1 if assertion_count == 0 else 0,
        "tests_with_only_helper_assertions": 1 if only_helper else 0,
    }
