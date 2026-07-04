"""Left-join Phase 2 static metrics onto per-test RQ summary rows."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from stream_io import iter_jsonl, test_key

# Stable export set (prefixed sm_ on joined RQ tables).
STATIC_METRICS_COLUMNS: List[str] = [
    "metrics_status",
    "test_body_loc",
    "test_body_ncloc",
    "test_body_statement_count",
    "test_body_call_count",
    "test_body_cyclomatic_basic",
    "test_body_cyclomatic_extended",
    "test_body_branch_count",
    "test_body_loop_count",
    "test_body_switch_case_count",
    "test_body_conditional_expression_count",
    "test_body_logical_condition_count",
    "test_body_try_catch_count",
    "test_body_max_nesting_depth",
    "hook_count",
    "hook_metrics_unresolved_count",
    "hook_ncloc_total",
    "hook_cyclomatic_basic_total",
    "hook_cyclomatic_extended_total",
    "setup_hook_ncloc_total",
    "teardown_hook_ncloc_total",
    "navigation_action_count",
    "dynamic_navigation_action_count",
    "unique_static_url_count",
    "has_dynamic_navigation",
    "estimated_page_or_view_count",
    "static_url_literals_json",
]

STATIC_METRICS_BOOL_COLUMNS = frozenset({"has_dynamic_navigation"})
STATIC_METRICS_JSON_COLUMNS = frozenset({"static_url_literals_json"})
STATIC_METRICS_STRING_COLUMNS = frozenset({"metrics_status"})
STATIC_METRICS_NUMERIC_COLUMNS = frozenset(STATIC_METRICS_COLUMNS) - (
    STATIC_METRICS_BOOL_COLUMNS | STATIC_METRICS_JSON_COLUMNS | STATIC_METRICS_STRING_COLUMNS
)


@dataclass
class StaticMetricsLoadResult:
    by_key: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    rows_read: int = 0
    rows_malformed: int = 0
    # Extra JSONL rows for a key already seen (last row wins), not distinct duplicated keys.
    duplicate_rows: int = 0
    unique_keys: int = 0

    @property
    def duplicate_keys(self) -> int:
        """Backward-compatible alias for duplicate_rows."""
        return self.duplicate_rows


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes"}
    if value is None:
        return False
    return bool(value)


def _missing_value_for_column(col: str) -> Any:
    """Unmatched left join: blank/NA, never numeric zero (avoids false zeros in analysis)."""
    if col in STATIC_METRICS_BOOL_COLUMNS:
        return ""
    if col in STATIC_METRICS_JSON_COLUMNS or col in STATIC_METRICS_STRING_COLUMNS:
        return ""
    return ""


def _format_column_value(col: str, value: Any) -> Any:
    if col in STATIC_METRICS_BOOL_COLUMNS:
        return as_bool(value)
    if col in STATIC_METRICS_JSON_COLUMNS:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False)
    if value is None:
        return ""
    return value


def static_metrics_unmatched_defaults() -> Dict[str, Any]:
    """Defaults when no static-metrics row exists for this test (left join miss)."""
    out: Dict[str, Any] = {
        "sm_joined": False,
        "sm_metrics_ok": False,
    }
    for col in STATIC_METRICS_COLUMNS:
        out[f"sm_{col}"] = _missing_value_for_column(col)
    return out


def metrics_row_is_ok(static_row: Dict[str, Any]) -> bool:
    return str(static_row.get("metrics_status") or "").strip().lower() == "ok"


def load_static_metrics(path: Path) -> StaticMetricsLoadResult:
    """Load test_case_static_metrics.jsonl keyed by test_key(repo, test_id)."""
    result = StaticMetricsLoadResult()
    if not path.exists():
        return result
    seen: Set[str] = set()
    for row in iter_jsonl(path):
        result.rows_read += 1
        repo = str(row.get("repo") or "").strip()
        tid = str(row.get("test_id") or "").strip()
        if not repo or not tid:
            result.rows_malformed += 1
            continue
        row = {**row, "repo": repo, "test_id": tid}
        key = test_key(repo, tid)
        if key in result.by_key:
            result.duplicate_rows += 1
        else:
            seen.add(key)
        result.by_key[key] = row
    result.unique_keys = len(seen)
    return result


def resolve_static_metrics_path(static_metrics_dir: Path) -> Path:
    """Accept run dir or explicit static_metrics output dir."""
    static_metrics_dir = static_metrics_dir.absolute()
    direct = static_metrics_dir / "test_case_static_metrics.jsonl"
    if direct.exists():
        return direct
    nested = static_metrics_dir / "static_metrics" / "test_case_static_metrics.jsonl"
    if nested.exists():
        return nested
    return direct


def merge_static_fields(
    base: Dict[str, Any],
    static_row: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Left join: base row unchanged except sm_* columns added.

    sm_joined: static row present for this test key.
    sm_metrics_ok: metrics_status == "ok" (usable for analysis).
    Unmatched rows use blank sm_* values, not numeric zeros.
    """
    merged = dict(base)
    if static_row is None:
        merged.update(static_metrics_unmatched_defaults())
        return merged

    merged["sm_joined"] = True
    merged["sm_metrics_ok"] = metrics_row_is_ok(static_row)
    for col in STATIC_METRICS_COLUMNS:
        val = static_row.get(col)
        if val is None:
            merged[f"sm_{col}"] = ""
        else:
            merged[f"sm_{col}"] = _format_column_value(col, val)
    return merged


def _test_case_has_valid_key(tc: Dict[str, Any]) -> bool:
    repo = str(tc.get("repo") or "")
    tid = str(tc.get("test_id") or "")
    return bool(repo.strip() and tid.strip())


def _canonical_test_case_keys(test_cases: Dict[str, Dict[str, Any]]) -> Set[str]:
    """Unique test identities from row fields (matches spine CSV join keys)."""
    return {
        test_key(str(tc.get("repo") or ""), str(tc.get("test_id") or ""))
        for tc in test_cases.values()
        if _test_case_has_valid_key(tc)
    }


def build_static_metrics_by_test_rows(
    test_cases: Dict[str, Dict[str, Any]],
    static_by_key: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """One row per test case (spine), left-joined to static metrics."""
    rows: List[Dict[str, Any]] = []
    for _key, tc in sorted(test_cases.items()):
        base = {
            "repo": str(tc.get("repo") or "").strip(),
            "test_id": str(tc.get("test_id") or "").strip(),
            "framework": str(tc.get("framework") or ""),
            "phase1_confidence": str(tc.get("phase1_confidence") or ""),
            "callback_start_line": tc.get("callback_start_line"),
            "callback_end_line": tc.get("callback_end_line"),
        }
        lookup_key = test_key(base["repo"], base["test_id"])
        rows.append(merge_static_fields(base, static_by_key.get(lookup_key)))
    return rows


def join_summary(
    test_cases: Dict[str, Dict[str, Any]],
    static_by_key: Dict[str, Dict[str, Any]],
    *,
    load_result: Optional[StaticMetricsLoadResult] = None,
) -> Dict[str, Any]:
    valid_spine_keys = _canonical_test_case_keys(test_cases)
    test_case_rows_malformed_for_static_join = len(test_cases) - len(valid_spine_keys)
    static_keys = set(static_by_key)
    matched_keys = valid_spine_keys & static_keys
    matched_ok = sum(
        1 for k in matched_keys if metrics_row_is_ok(static_by_key[k])
    )
    matched_non_ok = len(matched_keys) - matched_ok
    unmatched = len(valid_spine_keys - static_keys)
    orphans = len(static_keys - valid_spine_keys)

    out: Dict[str, Any] = {
        "static_metrics_unique_keys": len(static_by_key),
        "static_metrics_rows_loaded": len(static_by_key),
        "test_cases_spine": len(test_cases),
        "test_cases_spine_valid_keys": len(valid_spine_keys),
        "test_cases_spine_malformed_keys": test_case_rows_malformed_for_static_join,
        "static_metrics_matched": len(matched_keys),
        "static_metrics_matched_ok": matched_ok,
        "static_metrics_matched_non_ok": matched_non_ok,
        "static_metrics_unmatched": unmatched,
        "static_metrics_orphan": orphans,
    }
    if load_result is not None:
        out.update(
            {
                "static_metrics_rows_read": load_result.rows_read,
                "static_metrics_rows_malformed": load_result.rows_malformed,
                "static_metrics_duplicate_rows": load_result.duplicate_rows,
                "static_metrics_duplicate_keys": load_result.duplicate_rows,
            }
        )
    return out
