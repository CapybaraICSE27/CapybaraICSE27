"""RQ2 split provenance gate metrics."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List


STATIC_FILE_ORIGIN_KINDS = frozenset({
    "static_file_root",
    "static_file_root_member",
    "static_file_member",
    "static_file_member_member",
    "hook_assigned_fixture",
    "parameterized_row",
    "parameterized_row_member",
    "network_mock_payload",
    "network_mock_payload_member",
})

NON_FILE_ORIGIN_PREFIXES = (
    "hook_assigned_api",
    "hook_assigned_callback",
    "api_",
    "factory_",
    "object_literal",
    "generated_call",
    "cypress_alias",
)

RESOLVED_ORIGIN_KINDS = frozenset({
    "static_file_root",
    "static_file_root_member",
    "static_file_member",
    "hook_assigned_fixture",
    "hook_assigned_api_response",
    "hook_assigned_api_response_member",
    "hook_assigned_callback_param",
    "hook_assigned_callback_param_member",
    "api_response_callback_param",
    "api_response_callback_param_member",
    "api_call_result",
    "api_call_result_member",
    "parameterized_row",
    "parameterized_row_member",
    "factory_build",
    "factory_build_member",
    "generated_call",
    "environment_value",
    "literal_constant",
    "inline_literal",
    "inline_array",
    "inline_object",
    "object_literal",
    "object_literal_member",
    "composite_expression",
    "member_from_bound_root",
    "member_from_bound_root_member",
    "cypress_alias",
    "cypress_alias_member",
    "network_mock_payload",
    "network_mock_payload_member",
})

VARIABLE_LIKE_SOURCES = frozenset({
    "variable_input",
    "variable_from_external_file",
    "api_seed_input",
    "generated_input",
    "parameterized_input",
    "network_mock_payload_input",
})


def _truthy(val: str) -> bool:
    return str(val or "").strip().lower() in ("true", "1", "yes")


def _has_provenance(row: Dict[str, str]) -> bool:
    return bool((row.get("input_provenance") or "").strip())


def _is_non_file_origin(kind: str) -> bool:
    if kind == "composite_expression":
        return False
    return any(kind.startswith(prefix) for prefix in NON_FILE_ORIGIN_PREFIXES)


def _is_true_static_file_candidate(row: Dict[str, str]) -> bool:
    """Rows with fixture/readFile/import/registry load evidence only."""
    src = row.get("input_source_class") or ""
    if src not in VARIABLE_LIKE_SOURCES:
        return False
    if src in ("api_seed_input", "generated_input"):
        return False

    kind = (row.get("input_origin_kind") or "").strip()
    if kind and _is_non_file_origin(kind):
        return False

    components = (row.get("input_provenance_components_json") or "").strip()
    if kind == "composite_expression" and components:
        return any(token in components for token in ("external_file:", "fixture_file:", "parameterized_row:"))

    if src in ("variable_from_external_file", "parameterized_input"):
        return True

    prov = (row.get("input_provenance") or "").strip()
    if prov.startswith(("external_file:", "fixture_file:", "parameterized_row:")):
        return True

    if kind and kind in STATIC_FILE_ORIGIN_KINDS:
        return True
    if kind and (
        "static_file" in kind
        or kind.startswith("parameterized_row")
        or kind.startswith("network_mock_payload")
        or kind == "hook_assigned_fixture"
    ):
        return True

    if (row.get("external_file_path") or "").strip():
        return True

    return _truthy(row.get("is_static_file_candidate"))


def _static_file_linked(row: Dict[str, str]) -> bool:
    kind = (row.get("input_origin_kind") or "").strip()
    if kind == "composite_expression":
        components = row.get("input_provenance_components_json") or ""
        return any(token in components for token in ("external_file:", "fixture_file:", "parameterized_row:"))
    if kind and kind in STATIC_FILE_ORIGIN_KINDS:
        return True
    if row.get("input_source_class") == "variable_from_external_file":
        return True
    prov = (row.get("input_provenance") or "").strip()
    return prov.startswith(("external_file:", "fixture_file:", "parameterized_row:"))


def _origin_resolved(row: Dict[str, str]) -> bool:
    kind = (row.get("input_origin_kind") or "").strip()
    if kind and kind in RESOLVED_ORIGIN_KINDS:
        return True
    if _has_provenance(row):
        return True
    src = row.get("input_source_class") or ""
    return src in ("environment_input", "literal_input", "fixture_file_input", "external_file_input")


def compute_provenance_gates(events_path: Path) -> Dict[str, Any]:
    rows: List[Dict[str, str]] = list(csv.DictReader(events_path.open(encoding="utf-8")))

    static_candidates: List[Dict[str, str]] = []
    variable_like: List[Dict[str, str]] = []

    for row in rows:
        src = row.get("input_source_class") or ""
        if _is_true_static_file_candidate(row):
            static_candidates.append(row)
        if src in VARIABLE_LIKE_SOURCES:
            variable_like.append(row)

    static_linked = sum(1 for r in static_candidates if _static_file_linked(r))
    origin_resolved = sum(1 for r in variable_like if _origin_resolved(r))

    static_denom = len(static_candidates) or 1
    var_denom = len(variable_like) or 1

    return {
        "rq2_static_file_candidate_count": len(static_candidates),
        "rq2_static_file_candidate_linked_count": static_linked,
        "rq2_static_file_candidate_link_rate": round(static_linked / static_denom, 4),
        "rq2_variable_like_count": len(variable_like),
        "rq2_variable_origin_resolved_count": origin_resolved,
        "rq2_variable_origin_resolved_rate": round(origin_resolved / var_denom, 4),
        "rq2_provenance_gate_static_target": 0.60,
        "rq2_provenance_gate_origin_target": 0.20,
        "rq2_provenance_gate_static_pass": static_linked / static_denom >= 0.60,
        "rq2_provenance_gate_origin_pass": origin_resolved / var_denom >= 0.20,
    }


def write_provenance_gates(output_dir: Path, events_path: Path | None = None) -> Dict[str, Any]:
    ep = events_path or (output_dir / "rq2_input_events.csv")
    if not ep.exists():
        return {}
    metrics = compute_provenance_gates(ep)
    (output_dir / "rq2_provenance_gates.json").write_text(
        __import__("json").dumps(metrics, indent=2),
        encoding="utf-8",
    )
    return metrics
