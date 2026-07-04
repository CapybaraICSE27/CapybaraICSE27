"""RQ2 manual review queue selection (Phase 5 scaffold)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from input_classify import input_ast_audit_mismatch_type

RQ2_REVIEW_QUEUE_FIELDS = [
    "repo",
    "test_id",
    "framework",
    "line",
    "name",
    "raw_code",
    "input_source_class",
    "input_source_inferred",
    "input_plausibility",
    "input_plausibility_paper_label",
    "input_plausibility_confidence",
    "input_plausibility_codebook_path",
    "value_visibility",
    "input_channel",
    "input_provenance",
    "input_provenance_family",
    "input_provenance_components_json",
    "field_context",
    "input_target_role_ast",
    "input_target_role_basis_ast",
    "input_target_context_ast",
    "input_target_context_normalized_ast",
    "input_target_context_basis_ast",
    "input_value_expression_kind_ast",
    "input_endpoint_construction_ast",
    "input_endpoint_construction_basis_ast",
    "rq2_value_bearing_input",
    "rq2_value_exclusion_reason",
    "rq2_value_bearing_basis",
    "value_summary",
    "needs_review",
    "review_reason",
    "input_evidence_basis",
    "input_source_confidence",
    "input_provenance_confidence",
]


def review_reasons(
    inp: Dict[str, Any],
    feature: Optional[Dict[str, Any]] = None,
    *,
    ast_mismatch: str = "match",
) -> List[str]:
    reasons: List[str] = []
    if inp.get("needs_review"):
        reasons.append("needs_review_flag")
    if (inp.get("input_plausibility_confidence") or "").strip().lower() == "low":
        reasons.append("low_plausibility_confidence")
    if (
        inp.get("input_plausibility") == "unclear"
        and inp.get("value_visibility") == "visible"
    ):
        reasons.append("visible_unclear")
    if ast_mismatch and ast_mismatch != "match":
        reasons.append(f"ast_regex_mismatch:{ast_mismatch}")
    if (inp.get("input_source_confidence") or "").strip().lower() == "low":
        reasons.append("low_source_confidence")
    prov_conf = (feature or {}).get("input_provenance_confidence") or ""
    if prov_conf.strip().lower() == "low":
        reasons.append("low_provenance_confidence")
    parse_status = (feature or {}).get("input_load_parse_status_ast") or ""
    if parse_status in ("error", "partial"):
        reasons.append(f"external_file_parse:{parse_status}")
    return reasons


def should_enqueue_review(
    inp: Dict[str, Any],
    feature: Optional[Dict[str, Any]] = None,
    *,
    ast_mismatch: str = "match",
) -> bool:
    return bool(review_reasons(inp, feature, ast_mismatch=ast_mismatch))


def build_review_row(
    base_fields: Dict[str, Any],
    inp: Dict[str, Any],
    *,
    name: str = "",
    raw_code: str = "",
    line: str = "",
    feature: Optional[Dict[str, Any]] = None,
    ast_mismatch: str = "match",
) -> Dict[str, Any]:
    reasons = review_reasons(inp, feature, ast_mismatch=ast_mismatch)
    return {
        **base_fields,
        "line": line,
        "name": name,
        "raw_code": (raw_code or "")[:500],
        "input_source_class": inp.get("input_source_class", ""),
        "input_source_inferred": inp.get("input_source_inferred", ""),
        "input_plausibility": inp.get("input_plausibility", ""),
        "input_plausibility_paper_label": inp.get("input_plausibility_paper_label", ""),
        "input_plausibility_confidence": inp.get("input_plausibility_confidence", ""),
        "input_plausibility_codebook_path": inp.get("input_plausibility_codebook_path", ""),
        "value_visibility": inp.get("value_visibility", ""),
        "input_channel": inp.get("input_channel", ""),
        "input_provenance": inp.get("input_provenance", ""),
        "input_provenance_family": inp.get("input_provenance_family", ""),
        "input_provenance_components_json": inp.get("input_provenance_components_json", ""),
        "field_context": inp.get("field_context", ""),
        "input_target_role_ast": (feature or {}).get("input_target_role_ast", ""),
        "input_target_role_basis_ast": (feature or {}).get("input_target_role_basis_ast", ""),
        "input_target_context_ast": (feature or {}).get("input_target_context_ast", ""),
        "input_target_context_normalized_ast": (feature or {}).get("input_target_context_normalized_ast", ""),
        "input_target_context_basis_ast": (feature or {}).get("input_target_context_basis_ast", ""),
        "input_value_expression_kind_ast": (feature or {}).get("input_value_expression_kind_ast", ""),
        "input_endpoint_construction_ast": (feature or {}).get("input_endpoint_construction_ast", ""),
        "input_endpoint_construction_basis_ast": (feature or {}).get("input_endpoint_construction_basis_ast", ""),
        "rq2_value_bearing_input": inp.get("rq2_value_bearing_input", ""),
        "rq2_value_exclusion_reason": inp.get("rq2_value_exclusion_reason", ""),
        "rq2_value_bearing_basis": inp.get("rq2_value_bearing_basis", ""),
        "value_summary": inp.get("value_summary", "") if "value_summary" in inp else "",
        "needs_review": inp.get("needs_review", False),
        "review_reason": ";".join(reasons),
        "input_evidence_basis": inp.get("input_evidence_basis", ""),
        "input_source_confidence": inp.get("input_source_confidence", ""),
        "input_provenance_confidence": (feature or {}).get("input_provenance_confidence", ""),
    }
