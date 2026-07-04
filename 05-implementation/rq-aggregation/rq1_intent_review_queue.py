"""RQ1 setup/teardown intent manual review queue (Milestone 2)."""

from __future__ import annotations

from typing import Any, Dict, List

RQ1_INTENT_REVIEW_QUEUE_FIELDS = [
    "repo",
    "test_id",
    "framework",
    "line",
    "name",
    "raw_code",
    "feature_type",
    "source_kind",
    "inventory_category",
    "phase",
    "scope",
    "primary_intent",
    "primary_intent_evidence_basis",
    "confidence",
    "review_reason",
    "uncertain_reason",
    "fallback_used",
    "structured_evidence_available",
    "helper_resolution_status",
    "child_setup_unit_count",
    "child_intent_counts_json",
    "dominant_child_intent",
    "mixed_intent_score",
    "provenance_basis",
    "eligibility_basis",
    "manual_phase_ok",
    "manual_scope_ok",
    "manual_intent_ok",
    "manual_notes",
]


def build_intent_review_row(event_row: Dict[str, Any]) -> Dict[str, Any]:
    out = {k: event_row.get(k, "") for k in RQ1_INTENT_REVIEW_QUEUE_FIELDS if not k.startswith("manual_")}
    out["manual_phase_ok"] = ""
    out["manual_scope_ok"] = ""
    out["manual_intent_ok"] = ""
    out["manual_notes"] = ""
    return out
