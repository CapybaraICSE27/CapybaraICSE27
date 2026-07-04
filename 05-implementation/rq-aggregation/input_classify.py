"""RQ2 input source resolution (AST-first, regex audit fallback)."""

from __future__ import annotations

import re
import json
from typing import Any, Dict, Optional, Tuple

from classify import classify_input, map_input_source
from input_plausibility import resolve_input_plausibility, resolve_input_plausibility_detail, resolve_upload_visibility

INPUT_SOURCE_CLASSES = (
    "literal_input",
    "variable_input",
    "variable_from_external_file",
    "fixture_file_input",
    "external_file_input",
    "environment_input",
    "generated_input",
    "parameterized_input",
    "file_upload_input",
    "api_seed_input",
    "network_mock_payload_input",
    "unknown_input",
)

VALUE_VISIBILITY = ("visible", "partially_visible", "opaque", "unknown")

INPUT_CHANNELS = (
    "ui_text_entry",
    "ui_file_upload",
    "ui_selection",
    "keyboard_input",
    "keyboard_entry",
    "load_site",
    "environment_read",
    "generated_value",
    "unknown",
)

CONTROL_TOKEN_NAMES = {
    "alt",
    "arrowdown",
    "arrowleft",
    "arrowright",
    "arrowup",
    "backspace",
    "cmd",
    "command",
    "control",
    "ctrl",
    "del",
    "delete",
    "down",
    "downarrow",
    "end",
    "enter",
    "esc",
    "escape",
    "home",
    "insert",
    "left",
    "leftarrow",
    "meta",
    "mod",
    "movetoend",
    "movetostart",
    "option",
    "pagedown",
    "pageup",
    "return",
    "right",
    "rightarrow",
    "selectall",
    "shift",
    "space",
    "tab",
    "up",
    "uparrow",
}

CONTROL_TEMPLATE_VARIABLE_NAMES = {
    "cmdorctrl",
    "commandorcontrol",
    "controlkey",
    "ctrlkey",
    "keycode",
    "metakey",
    "modifier",
    "modifierkey",
    "shortcut",
    "shortcutkey",
}

BRACE_TOKEN_RE = re.compile(r"\{([^{}]+)\}")
TEMPLATE_EXPR_RE = re.compile(r"\$\{([^{}]+)\}")


def _is_non_consumer_value_construction(name: str, raw: str) -> bool:
    """
    Identify value-construction helpers that should not become RQ2 consumer inputs.

    The Phase 2C input extractor can surface Array.from(...).fill(...) because it
    shares a method name with UI fill APIs. Keep this narrow so page/locator fill
    calls remain in RQ2.
    """
    text = f"{name or ''} {raw or ''}"
    return bool(
        re.search(r"\bArray\.from(?:<[^>]+>)?\s*\([^)]*\)\s*\.fill\s*\(", text)
        or re.search(r"\bnew\s+Array\s*\([^)]*\)\s*\.fill\s*\(", text)
    )


def _clean_control_token(token: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(token or "").strip().lower())


def _is_control_token_name(token: str) -> bool:
    cleaned = _clean_control_token(token)
    if not cleaned:
        return False
    if cleaned in CONTROL_TOKEN_NAMES:
        return True
    if cleaned.startswith("numpad") and cleaned[6:] in CONTROL_TOKEN_NAMES:
        return True
    if "arrow" in cleaned and cleaned.replace("arrow", "") in {"up", "down", "left", "right"}:
        return True
    return False


def _is_control_chord_parts(parts: list[str]) -> bool:
    if not parts:
        return False
    cleaned = [_clean_control_token(part) for part in parts if _clean_control_token(part)]
    if not cleaned:
        return False
    if all(_is_control_token_name(part) for part in cleaned):
        return True
    modifiers = {"alt", "cmd", "command", "control", "ctrl", "meta", "mod", "option", "shift"}
    has_modifier = any(part in modifiers for part in cleaned)
    return has_modifier and all(_is_control_token_name(part) or len(part) == 1 for part in cleaned)


def _is_control_template_variable(expr: str) -> bool:
    cleaned = _clean_control_token(expr.split(".")[-1])
    return cleaned in CONTROL_TEMPLATE_VARIABLE_NAMES


def _strip_value_wrapper(value: str) -> str:
    text = str(value or "").strip()
    while len(text) >= 2 and text[0] in "'\"`" and text[-1] == text[0]:
        text = text[1:-1].strip()
    return text


def _literal_array_values(value: str) -> Optional[list[str]]:
    text = _strip_value_wrapper(value)
    if not (text.startswith("[") and text.endswith("]")):
        return None
    try:
        parsed = json.loads(text.replace("'", '"'))
    except Exception:
        return None
    if not isinstance(parsed, list):
        return None
    out: list[str] = []
    for item in parsed:
        if not isinstance(item, str):
            return None
        out.append(item)
    return out


def _is_pure_control_value(value: str) -> bool:
    """Return true when an AST-extracted value is only keyboard/control syntax."""
    text = _strip_value_wrapper(value)
    if not text:
        return False

    array_values = _literal_array_values(text)
    if array_values is not None:
        return bool(array_values) and all(_is_pure_control_value(item) for item in array_values)

    template_exprs = TEMPLATE_EXPR_RE.findall(text)
    if template_exprs:
        if any(not _is_control_template_variable(expr) for expr in template_exprs):
            return False
        text_without_exprs = TEMPLATE_EXPR_RE.sub("", text)
        if "{}" in text_without_exprs:
            remainder = text_without_exprs.replace("{}", "")
            compact = re.sub(r"[^A-Za-z0-9_$]+", "", remainder)
            if not compact or (len(compact) == 1 and compact.isalnum()):
                return True
    else:
        text_without_exprs = text

    if not BRACE_TOKEN_RE.search(text_without_exprs):
        parts = [p for p in re.split(r"[+\s,]+", text_without_exprs) if p]
        return bool(parts) and all(_is_control_token_name(part) for part in parts)

    saw_control = False

    def replace_brace(match: re.Match[str]) -> str:
        nonlocal saw_control
        body = match.group(1)
        if not body:
            saw_control = True
            return ""
        pieces = [p for p in re.split(r"[+\s,]+", body) if p]
        if _is_control_chord_parts(pieces):
            saw_control = True
            return ""
        return match.group(0)

    remainder = BRACE_TOKEN_RE.sub(replace_brace, text_without_exprs)
    compact = re.sub(r"[^A-Za-z0-9_$]+", "", remainder)
    if not compact:
        return saw_control or bool(template_exprs)
    # Template modifier shortcuts such as `{${modifierKey}}a` are still a pure
    # keyboard command even though the terminal shortcut key is a bare literal.
    if template_exprs and len(compact) == 1 and compact.isalnum():
        return True
    return False


def _components_have_substantive_value(components_json: str) -> bool:
    if not components_json:
        return False
    try:
        components = json.loads(components_json)
    except Exception:
        return False
    if not isinstance(components, list):
        return False
    for component in components:
        if not isinstance(component, dict):
            continue
        evidence = str(component.get("evidence") or component.get("value") or "")
        origin_kind = str(component.get("originKind") or component.get("origin_kind") or "")
        provenance = str(component.get("provenance") or "")
        if origin_kind in {"inline_literal", "inline_array"}:
            if evidence and not _is_pure_control_value(evidence):
                return True
            continue
        if not origin_kind and provenance.startswith(("inline_literal:", "inline_array:")) and not evidence:
            continue
        haystack = " ".join(part for part in (evidence, provenance) if part)
        if origin_kind and not _is_control_template_variable(evidence or provenance or origin_kind):
            return True
        if haystack and not _is_pure_control_value(haystack):
            return True
    return False


def classify_rq2_value_bearing_input(row: Dict[str, Any]) -> Tuple[str, str, str]:
    """Classify whether an RQ2 row should contribute to value-input results.

    This is a reporting/aggregation boundary. It uses structured fields first;
    lexical parsing is limited to AST-extracted value strings because keyboard
    control tokens are themselves lexical API values.
    """
    rq2_unit = str(row.get("rq2_unit") or "consumer_input").strip()
    if rq2_unit and rq2_unit not in {"consumer_input", "load_site"}:
        return "false", "non_consumer_input_unit", "rq2_unit"

    channel = str(row.get("input_channel") or row.get("input_channel_ast") or "").strip()
    source = str(row.get("input_source_class") or row.get("input_source_ast") or "").strip()
    codebook = str(row.get("input_plausibility_codebook_path") or "").strip()
    origin_kind = str(row.get("input_origin_kind") or row.get("input_origin_kind_ast") or "").strip()
    value = str(
        row.get("input_value_redacted")
        or row.get("value_summary")
        or row.get("input_origin_evidence")
        or row.get("input_origin_evidence_ast")
        or ""
    ).strip()
    components_json = str(row.get("input_provenance_components_json") or "")

    if channel in {"keyboard_entry", "keyboard_input"}:
        return "false", "keyboard_control_token", "keyboard_channel"
    if source == "file_upload_input" or channel == "ui_file_upload":
        return "true", "", "file_value"
    if channel == "ui_selection":
        return "true", "", "selection_value"
    if _components_have_substantive_value(components_json):
        return "true", "", "component_provenance"

    pure_control = _is_pure_control_value(value)
    if pure_control and channel in {"ui_text_entry", "text_entry"}:
        return "false", "pure_control_text_entry", "pure_control_token"
    if codebook == "keyboard_or_control_token" and pure_control:
        return "false", "pure_control_text_entry", "pure_control_token"
    if codebook == "keyboard_or_control_token" and not value and origin_kind in {"inline_literal", "inline_array", ""}:
        return "false", "pure_control_text_entry", "control_codebook"
    if codebook == "keyboard_or_control_token" and origin_kind not in {"composite_expression"}:
        return "false", "pure_control_text_entry", "control_codebook"
    if codebook == "keyboard_or_control_token" and origin_kind == "composite_expression":
        return "true", "", "composite_value_plus_control"
    return "true", "", "value_argument"


def _split_provenance(provenance: str) -> Dict[str, str]:
    if not provenance:
        return {"external_file_path": "", "field_path": ""}
    body = provenance
    def _looks_file_path(value: str) -> bool:
        v = (value or "").strip()
        return bool(re.search(r"\.(?:json|ya?ml|csv|txt|tsv)$", v, re.I) or "/" in v or "\\" in v)

    for prefix in ("external_file:", "fixture_file:"):
        if body.startswith(prefix):
            body = body[len(prefix) :]
            if "#" in body:
                file_part, field = body.split("#", 1)
                return {"external_file_path": file_part, "field_path": field}
            return {"external_file_path": body, "field_path": ""}
    if body.startswith("parameterized_row:"):
        if "#" in body:
            _row_part, field = body.split("#", 1)
            return {"external_file_path": "", "field_path": field}
        return {"external_file_path": "", "field_path": ""}
    if ":" in body:
        return {"external_file_path": "", "field_path": ""}
    if "#" in body:
        unknown_part, field = body.split("#", 1)
        if _looks_file_path(unknown_part):
            return {"external_file_path": unknown_part, "field_path": field}
        return {"external_file_path": "", "field_path": field}
    if _looks_file_path(body):
        return {"external_file_path": body, "field_path": ""}
    return {"external_file_path": "", "field_path": ""}


def _provenance_family(provenance: str, origin_kind: str = "") -> str:
    prov = (provenance or "").strip()
    if origin_kind:
        return origin_kind
    if not prov:
        return "missing"
    if prov.startswith("inline_literal:"):
        return "inline_literal"
    if prov.startswith("inline_object:"):
        return "inline_object"
    if prov.startswith("inline_array:"):
        return "inline_array"
    if prov.startswith(("external_file:", "fixture_file:")):
        return "external_file"
    if prov.startswith("parameterized_row:"):
        return "parameterized_row"
    if prov.startswith("generated:"):
        return "generated"
    if prov.startswith("environment:"):
        return "environment"
    if prov.startswith("api_seed:"):
        return "api_seed"
    if prov.startswith("alias:"):
        return "alias"
    if prov == "composite_expression":
        return "composite_expression"
    return "other_resolved"


def _origin_kind_from_provenance(provenance: str) -> str:
    prov = (provenance or "").strip()
    if prov.startswith(("external_file:", "fixture_file:")):
        return "static_file_root_member" if "#" in prov else "static_file_root"
    if prov.startswith("parameterized_row:"):
        return "parameterized_row_member" if "#" in prov else "parameterized_row"
    if prov.startswith("generated:"):
        return "generated_call"
    if prov.startswith("environment:"):
        return "environment_value"
    if prov.startswith("api_seed:"):
        return "api_response_callback_param"
    if prov.startswith("inline_literal:"):
        return "inline_literal"
    if prov.startswith("inline_object:"):
        return "inline_object"
    if prov.startswith("inline_array:"):
        return "inline_array"
    if prov.startswith("alias:"):
        return "cypress_alias"
    if prov == "composite_expression":
        return "composite_expression"
    return ""


def resolve_input_pattern(
    name: str,
    raw: str,
    feature: Optional[Dict[str, Any]] = None,
    *,
    is_parameterized_test: bool = False,
) -> Dict[str, Any]:
    """
    Resolve RQ2 paper-facing fields from Phase 2B/2C AST + provenance.
    """
    inferred = map_input_source("", name, raw)
    if inferred == "unknown_input":
        inferred = classify_input(name, raw)

    result: Dict[str, Any] = {
        "input_source_class": inferred,
        "input_source_inferred": inferred,
        "input_generation_class": inferred,
        "value_visibility": "unknown",
        "input_channel": "unknown",
        "input_provenance": "",
        "input_provenance_family": "missing",
        "input_provenance_components_json": "",
        "external_file_path": "",
        "field_path": "",
        "field_context": "",
        "input_evidence_basis": "regex_fallback",
        "input_source_confidence": "medium",
        "input_plausibility": "not_observable",
        "input_plausibility_confidence": "low",
        "input_plausibility_codebook_path": "",
        "input_plausibility_paper_label": "indeterminate_or_insufficient_evidence",
        "needs_review": False,
        "rq2_unit": "consumer_input",
        "exclude_from_rq2_consumer_events": False,
        "input_origin_kind": "",
        "input_origin_confidence": "",
        "input_origin_evidence": "",
        "linked_definition_line": "",
        "linked_definition_file": "",
        "is_static_file_candidate": False,
        "rq2_value_bearing_input": "true",
        "rq2_value_exclusion_reason": "",
        "rq2_value_bearing_basis": "value_argument",
    }

    if not feature:
        if is_parameterized_test and result["input_source_class"] == "variable_input":
            result["input_source_class"] = "parameterized_input"
            result["input_generation_class"] = "parameterized_input"
        result["input_plausibility"] = resolve_input_plausibility(
            value_redacted="",
            field_context="",
            value_visibility=result["value_visibility"],
            input_source_class=result["input_source_class"],
            input_channel=result["input_channel"],
        )[0]
        result["input_plausibility_paper_label"] = "indeterminate_or_insufficient_evidence"
        result["input_plausibility_codebook_path"] = "insufficient_value_and_target_semantics"
        (
            result["rq2_value_bearing_input"],
            result["rq2_value_exclusion_reason"],
            result["rq2_value_bearing_basis"],
        ) = classify_rq2_value_bearing_input({**result, "raw_code": raw, "name": name})
        return result

    rq2_unit = (feature.get("rq2_unit") or "consumer_input").strip()
    if rq2_unit == "consumer_input" and _is_non_consumer_value_construction(name, raw):
        rq2_unit = "value_construction"
    result["rq2_unit"] = rq2_unit
    if rq2_unit and rq2_unit not in {"consumer_input", "load_site"}:
        result["exclude_from_rq2_consumer_events"] = True

    ast_source = (feature.get("input_source_ast") or "").strip()
    provenance = (feature.get("input_provenance_ast") or "").strip()
    visibility = (feature.get("value_visibility_ast") or "").strip() or "unknown"
    channel = (feature.get("input_channel_ast") or "").strip() or "unknown"
    field_context = (feature.get("field_context_ast") or "").strip()
    value_redacted = (feature.get("input_value_redacted") or feature.get("value_summary") or "").strip()
    conf = (feature.get("input_source_confidence_ast") or feature.get("input_provenance_confidence") or "medium").strip()
    missing_ast_basis = False

    if ast_source:
        result["input_source_class"] = ast_source
        result["input_generation_class"] = ast_source
        result["value_visibility"] = visibility if visibility in VALUE_VISIBILITY else "unknown"
        result["input_channel"] = channel if channel in INPUT_CHANNELS else "unknown"
        result["field_context"] = field_context
        result["input_source_confidence"] = conf or "medium"
        basis = (feature.get("input_evidence_basis_ast") or "").strip()
        if basis:
            result["input_evidence_basis"] = basis
        elif provenance:
            result["input_evidence_basis"] = "ast_provenance"
        else:
            result["input_evidence_basis"] = "missing_input_evidence_basis"
            result["input_source_confidence"] = "low"
            missing_ast_basis = True

    if provenance:
        result["input_provenance"] = provenance
        result["input_provenance_family"] = _provenance_family(
            provenance,
            (feature.get("input_provenance_family_ast") or feature.get("input_origin_kind_ast") or "").strip(),
        )
        result["input_provenance_components_json"] = str(feature.get("input_provenance_components_json") or "")
        result.update(_split_provenance(provenance))
        if result["input_source_class"] in ("variable_input", "unknown_input") and provenance.startswith(
            ("external_file:", "fixture_file:")
        ):
            result["input_source_class"] = "variable_from_external_file"
            result["input_generation_class"] = "variable_from_external_file"

    origin_kind = (feature.get("input_origin_kind_ast") or "").strip()
    origin_conf = (feature.get("input_origin_confidence_ast") or "").strip()
    origin_evidence = (feature.get("input_origin_evidence_ast") or "").strip()
    if origin_kind:
        result["input_origin_kind"] = origin_kind
        if result["input_provenance_family"] == "missing":
            result["input_provenance_family"] = _provenance_family(provenance, origin_kind)
        result["input_origin_confidence"] = origin_conf or "medium"
        result["input_origin_evidence"] = origin_evidence
        result["linked_definition_line"] = str(feature.get("linked_definition_line") or "")
        result["linked_definition_file"] = (feature.get("linked_definition_file") or "").strip()
        result["is_static_file_candidate"] = bool(feature.get("is_static_file_candidate_ast"))
        if ast_source in ("variable_input", "unknown_input") and origin_kind:
            pass  # input_source_ast already upgraded in JS origin resolver
    elif provenance:
        derived_origin_kind = _origin_kind_from_provenance(provenance)
        if derived_origin_kind:
            result["input_origin_kind"] = derived_origin_kind
            result["input_origin_confidence"] = conf or "medium"
            result["input_origin_evidence"] = result["input_evidence_basis"]
            if derived_origin_kind.startswith(("static_file_", "parameterized_row", "network_mock_payload")):
                result["is_static_file_candidate"] = True

    if is_parameterized_test and result["input_source_class"] == "variable_input":
        result["input_source_class"] = "parameterized_input"
        result["input_generation_class"] = "parameterized_input"

    load_path = (feature.get("input_load_path_ast") or "").strip()
    if load_path and not result["external_file_path"]:
        result["external_file_path"] = load_path

    if not result["input_origin_kind"]:
        result["is_static_file_candidate"] = bool(feature.get("is_static_file_candidate_ast"))

    if result["input_source_class"] == "file_upload_input":
        result["value_visibility"] = resolve_upload_visibility(value_redacted, result["value_visibility"])

    plausibility_value = value_redacted
    if not plausibility_value and result["input_source_class"] == "environment_input":
        plausibility_value = raw or name

    plausibility_context = " ".join(
        part
        for part in (
            field_context,
            str(feature.get("input_target_context_ast") or ""),
            str(feature.get("input_target_context_normalized_ast") or ""),
            str(feature.get("input_target_role_ast") or ""),
            str(feature.get("input_value_expression_kind_ast") or ""),
            str(feature.get("input_endpoint_construction_ast") or ""),
            name,
            raw,
        )
        if part
    )

    plausibility_detail = resolve_input_plausibility_detail(
        value_redacted=plausibility_value,
        field_context=plausibility_context,
        value_visibility=result["value_visibility"],
        input_source_class=result["input_source_class"],
        input_channel=result["input_channel"],
    )
    result["input_plausibility"] = plausibility_detail["input_plausibility"]
    result["input_plausibility_confidence"] = plausibility_detail["input_plausibility_confidence"]
    result["input_plausibility_paper_label"] = plausibility_detail["input_plausibility_paper_label"]
    result["input_plausibility_codebook_path"] = plausibility_detail["input_plausibility_codebook_path"]
    result["needs_review"] = bool(plausibility_detail["needs_review"]) or missing_ast_basis
    (
        result["rq2_value_bearing_input"],
        result["rq2_value_exclusion_reason"],
        result["rq2_value_bearing_basis"],
    ) = classify_rq2_value_bearing_input(
        {
            **result,
            **feature,
            "input_value_redacted": value_redacted,
            "raw_code": raw,
            "name": name,
        }
    )

    result["input_source_inferred"] = inferred
    return result


def input_ast_audit_mismatch_type(ast_source: str, inferred_source: str, ast_confidence: str) -> str:
    tags = []
    if ast_source and inferred_source and ast_source != inferred_source:
        tags.append("source_class")
    if (ast_confidence or "").strip().lower() == "low":
        tags.append("low_confidence")
    return "match" if not tags else ";".join(tags)
