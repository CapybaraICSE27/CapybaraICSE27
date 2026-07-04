"""Map existing Phase 2 feature provenance to RQ1 intent hints (Milestone 2)."""

from __future__ import annotations

from typing import Any, Dict, List

from classify import classify_setup

SETUP_ELIGIBLE_FEATURE_TYPES = frozenset({
    "setup",
    "teardown",
    "browser_context_control",
    "network_mock",
    "time_control",
})

HOOK_SOURCE_KINDS = frozenset({
    "before",
    "after",
    "beforeEach",
    "afterEach",
    "beforeAll",
    "afterAll",
})

GENERIC_HELPER_NAME_RE = (
    "setup",
    "teardown",
    "prepare",
    "initialize",
    "init",
    "cleanup",
    "clean",
    "reset",
)


def map_provenance_hints(feature: Dict[str, Any]) -> Dict[str, Any]:
    """Structured hints from fields already on Phase 2C features."""
    name = str(feature.get("name") or "")
    raw = str(feature.get("raw_code") or "")
    sk = str(feature.get("source_kind") or "")
    ft = str(feature.get("feature_type") or "")
    hook_key = str(feature.get("hook_instance_key") or "")
    inventory_category = classify_setup(name, raw, sk, ft)
    ft_low = ft.lower()
    sk_low = sk.lower()
    if ft_low in SETUP_ELIGIBLE_FEATURE_TYPES or ft_low in ("setup", "teardown"):
        inventory_basis = "feature_type"
    elif sk_low in {s.lower() for s in HOOK_SOURCE_KINDS}:
        inventory_basis = "source_kind"
    elif inventory_category and inventory_category != "unknown_setup":
        inventory_basis = "lexical_fallback"
    else:
        inventory_basis = ""

    hints: Dict[str, Any] = {
        "inventory_category": inventory_category,
        "inventory_category_basis": inventory_basis,
        "cypress_command_role_ast": (feature.get("cypress_command_role_ast") or "").strip(),
        "cypress_command_role_basis_ast": (feature.get("cypress_command_role_basis_ast") or "").strip(),
        "cypress_command_role_confidence_ast": (
            feature.get("cypress_command_role_confidence_ast") or ""
        ).strip(),
        "workflow_kind_ast": (feature.get("workflow_kind_ast") or "").strip(),
        "workflow_kind_basis_ast": (feature.get("workflow_kind_basis_ast") or "").strip(),
        "fixture_param_name": (feature.get("fixture_param_name") or "").strip(),
        "fixture_scope": (feature.get("fixture_scope") or "").strip(),
        "fixture_declared_by": (feature.get("fixture_declared_by") or "").strip(),
        "hook_instance_key": hook_key,
        "hook_owner_kind": (feature.get("hook_owner_kind") or "").strip(),
        "is_support_hook": hook_key.startswith("support:"),
        "is_shared_hook_feature": bool(feature.get("is_shared_hook_feature")),
        "helper_resolution_status": (feature.get("helper_resolution_status") or "").strip(),
        "ast_confidence": (feature.get("ast_confidence") or feature.get("confidence") or "").strip(),
        "framework_api_category": (feature.get("framework_api_category") or "").strip(),
        "framework_api_category_basis_ast": (feature.get("framework_api_category_basis_ast") or "").strip(),
        "statement_phase_hint_ast": (feature.get("statement_phase_hint_ast") or "").strip(),
        "statement_phase_hint_basis_ast": (feature.get("statement_phase_hint_basis_ast") or "").strip(),
        "helper_body_phase_hint_ast": (feature.get("helper_body_phase_hint_ast") or "").strip(),
        "helper_body_phase_hint_basis_ast": (
            feature.get("helper_body_phase_hint_basis_ast") or ""
        ).strip(),
        "state_mutation_kind": (feature.get("state_mutation_kind") or "").strip(),
        "navigation_target_ast": (feature.get("navigation_target_ast") or "").strip(),
        "navigation_bootstrap_candidate_ast": bool(feature.get("navigation_bootstrap_candidate_ast")),
    }
    return hints


def provenance_basis_labels(hints: Dict[str, Any]) -> List[str]:
    """Human-readable provenance sources used for classification."""
    labels: List[str] = []
    if hints.get("cypress_command_role_ast"):
        basis = hints.get("cypress_command_role_basis_ast") or "legacy_unlabeled"
        labels.append(f"cypress_command_role:{hints['cypress_command_role_ast']}:{basis}")
    if hints.get("fixture_param_name"):
        labels.append("playwright_fixture_provenance")
    if hints.get("hook_instance_key"):
        labels.append("hook_instance_key")
    if hints.get("inventory_category"):
        basis = hints.get("inventory_category_basis") or "lexical_fallback"
        labels.append(f"classify_setup:{hints['inventory_category']}:{basis}")
    if hints.get("framework_api_category"):
        basis = hints.get("framework_api_category_basis_ast") or "unknown_basis"
        labels.append(f"framework_api_category:{hints['framework_api_category']}:{basis}")
    if hints.get("statement_phase_hint_ast"):
        basis = hints.get("statement_phase_hint_basis_ast") or "legacy_unlabeled"
        labels.append(f"statement_phase_hint_ast:{hints['statement_phase_hint_ast']}:{basis}")
    if hints.get("helper_body_phase_hint_ast"):
        basis = hints.get("helper_body_phase_hint_basis_ast") or "legacy_unlabeled"
        labels.append(f"helper_body_phase_hint_ast:{hints['helper_body_phase_hint_ast']}:{basis}")
    return labels or ["lexical_fallback"]
