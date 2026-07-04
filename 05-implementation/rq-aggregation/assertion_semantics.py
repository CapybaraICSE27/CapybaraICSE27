"""RQ5-C Tier 1: map assertion evidence to verification_intent."""

from __future__ import annotations

import re
import json
from typing import Any, Dict, FrozenSet

from classify import ALL_ASSERTION_ORACLE_CATEGORIES

ORACLE_TO_VERIFICATION_INTENT: Dict[str, str] = {
    "visibility_oracle": "element_presence",
    "text_content_oracle": "content_correctness",
    "url_navigation_oracle": "navigation_outcome",
    "element_state_oracle": "interactive_state",
    "count_or_length_oracle": "collection_size",
    "visual_snapshot_oracle": "visual_regression",
    "network_response_oracle": "network_contract",
    "accessibility_oracle": "accessibility_compliance",
    # classify_assertion uses api_state_oracle for request-related checks.
    "api_state_oracle": "api_or_data_contract",
    "value_attribute_oracle": "value_or_attribute_correctness",
    "style_visual_state_oracle": "style_or_visual_state",
    "api_data_contract_oracle": "api_or_data_contract",
    "generic_assertion": "unspecified",
}

VERIFICATION_INTENT_LABELS: FrozenSet[str] = frozenset(
    set(ORACLE_TO_VERIFICATION_INTENT.values())
)


def map_verification_intent(oracle_category: str) -> str:
    """Map classify_assertion() category to paper-facing verification_intent."""
    key = (oracle_category or "").strip().lower()
    return ORACLE_TO_VERIFICATION_INTENT.get(key, "unspecified")


MATCHER_TO_VERIFICATION_INTENT: Dict[str, str] = {
    "tobevisible": "element_presence",
    "tobehidden": "element_presence",
    "toexist": "element_presence",
    "exist": "element_presence",
    "exists": "element_presence",
    "tohavetext": "content_correctness",
    "tocontaintext": "content_correctness",
    "tocontain": "content_correctness",
    "contain": "content_correctness",
    "contains": "content_correctness",
    "include": "content_correctness",
    "match": "content_correctness",
    "tomatch": "content_correctness",
    "tohavetitle": "content_correctness",
    "tohaveurl": "navigation_outcome",
    "tohavelength": "collection_size",
    "tohavecount": "collection_size",
    "tohavebeencalledtimes": "interactive_state",
    "tohavereceivedeventtimes": "interactive_state",
    "calledtimes": "interactive_state",
    "tohavebeencalled": "api_or_data_contract",
    "tohavebeencalledwith": "api_or_data_contract",
    "tohavebeencalledonce": "interactive_state",
    "tohavebeencalledtwice": "interactive_state",
    "tohavebeencalledthrice": "interactive_state",
    "tohavebeencalledoncewith": "api_or_data_contract",
    "tohaveaccessiblename": "accessibility_compliance",
    "tohaveaccessibledescription": "accessibility_compliance",
    "tohaveaccessibleerror": "accessibility_compliance",
    "tohaveaccessibleerrormessage": "accessibility_compliance",
    "tohaverole": "accessibility_compliance",
    "tomatchariasnapshot": "accessibility_compliance",
    "tobecalled": "api_or_data_contract",
    "tobecalledwith": "api_or_data_contract",
    "becalled": "api_or_data_contract",
    "becalledwith": "api_or_data_contract",
    "becalledwithmatch": "api_or_data_contract",
    "becalledwithexactly": "api_or_data_contract",
    "becalledonce": "interactive_state",
    "becalledtwice": "interactive_state",
    "becalledthrice": "interactive_state",
    "called": "api_or_data_contract",
    "calledwith": "api_or_data_contract",
    "calledwithmatch": "api_or_data_contract",
    "calledonce": "interactive_state",
    "havecalledonce": "interactive_state",
    "calledtwice": "interactive_state",
    "calledthrice": "interactive_state",
    "calledoncewith": "api_or_data_contract",
    "calledbefore": "api_or_data_contract",
    "calledafter": "api_or_data_contract",
    "notcalled": "api_or_data_contract",
    "havebeencalled": "api_or_data_contract",
    "havebeencalledonce": "interactive_state",
    "havebeencalledtwice": "interactive_state",
    "havebeencalledthrice": "interactive_state",
    "havecallcount": "interactive_state",
    "callcount": "interactive_state",
    "havebeencalledwith": "api_or_data_contract",
    "havebeencalledwithmatch": "api_or_data_contract",
    "havebeencalledoncewith": "api_or_data_contract",
    "havebeencalledbefore": "api_or_data_contract",
    "havebeencalledafter": "api_or_data_contract",
    "havebeennotcalled": "api_or_data_contract",
    "notbeencalled": "api_or_data_contract",
    "tohavevalue": "value_or_attribute_correctness",
    "tohaveattribute": "value_or_attribute_correctness",
    "tohaveattr": "value_or_attribute_correctness",
    "tohaveid": "value_or_attribute_correctness",
    "tohaveproperty": "value_or_attribute_correctness",
    "tohavejsproperty": "value_or_attribute_correctness",
    "tohavecustomstate": "value_or_attribute_correctness",
    "tohavereceivedevent": "value_or_attribute_correctness",
    "tohavereceivedeventdetail": "value_or_attribute_correctness",
    "tobedefined": "value_or_attribute_correctness",
    "tobeundefined": "value_or_attribute_correctness",
    "tobenull": "value_or_attribute_correctness",
    "tobeempty": "value_or_attribute_correctness",
    "tobeemptystring": "value_or_attribute_correctness",
    "tobetruthy": "value_or_attribute_correctness",
    "tobefalsy": "value_or_attribute_correctness",
    "tobegreaterthan": "value_or_attribute_correctness",
    "tobegreaterthanorequal": "value_or_attribute_correctness",
    "tobelessthan": "value_or_attribute_correctness",
    "tobelessthanorequal": "value_or_attribute_correctness",
    "tohavecss": "style_or_visual_state",
    "tohaveclass": "style_or_visual_state",
    "tohaveelementclass": "style_or_visual_state",
    "tohavescreenshot": "visual_regression",
    "tobescreenshot": "visual_regression",
    "tomatchscreenshot": "visual_regression",
    "tomatchsnapshot": "visual_regression",
    "tobeattached": "element_presence",
    "tobeinthedocument": "element_presence",
    "tobeinviewport": "element_presence",
    "tobedisplayed": "element_presence",
    "tobeexisting": "element_presence",
    "tobeenabled": "interactive_state",
    "tobedisabled": "interactive_state",
    "tobechecked": "interactive_state",
    "tobeclickable": "interactive_state",
    "tobefocused": "interactive_state",
    "tobeeditable": "interactive_state",
    "tobeselected": "interactive_state",
    "bevisible": "element_presence",
    "benotvisible": "element_presence",
    "beexist": "element_presence",
    "exist": "element_presence",
    "notexist": "element_presence",
    "notbeexist": "element_presence",
    "nothavedescendants": "element_presence",
    "havetext": "content_correctness",
    "hashavetext": "content_correctness",
    "havetitle": "content_correctness",
    "containtext": "content_correctness",
    "includetext": "content_correctness",
    "havehtml": "content_correctness",
    "havelength": "collection_size",
    "havelengthof": "collection_size",
    "havecount": "collection_size",
    "length": "collection_size",
    "lengthof": "collection_size",
    "count": "collection_size",
    "size": "collection_size",
    "havevalue": "value_or_attribute_correctness",
    "value": "value_or_attribute_correctness",
    "attr": "value_or_attribute_correctness",
    "hasattr": "value_or_attribute_correctness",
    "havengcontrolvalue": "value_or_attribute_correctness",
    "havedata": "value_or_attribute_correctness",
    "haveattr": "value_or_attribute_correctness",
    "haveattribute": "value_or_attribute_correctness",
    "haveid": "value_or_attribute_correctness",
    "haveaprop": "value_or_attribute_correctness",
    "haveaproperty": "value_or_attribute_correctness",
    "nothaveaproperty": "value_or_attribute_correctness",
    "havesubset": "value_or_attribute_correctness",
    "deepinclude": "value_or_attribute_correctness",
    "haveanykeys": "value_or_attribute_correctness",
    "havecelldata": "value_or_attribute_correctness",
    "haveownproperty": "value_or_attribute_correctness",
    "havedeepproperty": "value_or_attribute_correctness",
    "havesamecolumndata": "value_or_attribute_correctness",
    "prop": "value_or_attribute_correctness",
    "property": "value_or_attribute_correctness",
    "haveprop": "value_or_attribute_correctness",
    "haveproperty": "value_or_attribute_correctness",
    "havejsproperty": "value_or_attribute_correctness",
    "havecss": "style_or_visual_state",
    "haveclass": "style_or_visual_state",
    "havefocus": "interactive_state",
    "havefocused": "interactive_state",
    "befocus": "interactive_state",
    "beenabled": "interactive_state",
    "bedisabled": "interactive_state",
    "bechecked": "interactive_state",
    "beselected": "interactive_state",
    "befocused": "interactive_state",
    "beempty": "value_or_attribute_correctness",
    "empty": "value_or_attribute_correctness",
    "bedefined": "value_or_attribute_correctness",
    "beundefined": "value_or_attribute_correctness",
    "benull": "value_or_attribute_correctness",
    "defined": "value_or_attribute_correctness",
    "undefined": "value_or_attribute_correctness",
    "null": "value_or_attribute_correctness",
    "eq": "value_or_attribute_correctness",
    "toeq": "value_or_attribute_correctness",
    "equal": "value_or_attribute_correctness",
    "beequal": "value_or_attribute_correctness",
    "eql": "value_or_attribute_correctness",
    "eqls": "value_or_attribute_correctness",
    "beeql": "value_or_attribute_correctness",
    "deepequal": "value_or_attribute_correctness",
    "deepeq": "value_or_attribute_correctness",
    "toequal": "value_or_attribute_correctness",
    "tostrictequal": "value_or_attribute_correctness",
    "tobe": "value_or_attribute_correctness",
    "be": "value_or_attribute_correctness",
    "beeq": "value_or_attribute_correctness",
    "equals": "value_or_attribute_correctness",
    "isequal": "value_or_attribute_correctness",
    "assertisequal": "value_or_attribute_correctness",
    "bea": "value_or_attribute_correctness",
    "bean": "value_or_attribute_correctness",
    "beinstanceof": "value_or_attribute_correctness",
    "instanceof": "value_or_attribute_correctness",
    "tobeinstanceof": "value_or_attribute_correctness",
    "isboolean": "value_or_attribute_correctness",
    "betrue": "value_or_attribute_correctness",
    "befalse": "value_or_attribute_correctness",
    "true": "value_or_attribute_correctness",
    "false": "value_or_attribute_correctness",
    "betruthy": "value_or_attribute_correctness",
    "befalsy": "value_or_attribute_correctness",
    "ok": "value_or_attribute_correctness",
    "notok": "value_or_attribute_correctness",
    "nothave": "value_or_attribute_correctness",
    "above": "value_or_attribute_correctness",
    "below": "value_or_attribute_correctness",
    "greaterthan": "value_or_attribute_correctness",
    "begreaterthan": "value_or_attribute_correctness",
    "tobegreaterthan": "value_or_attribute_correctness",
    "tobegreaterthanorequal": "value_or_attribute_correctness",
    "gt": "value_or_attribute_correctness",
    "begt": "value_or_attribute_correctness",
    "least": "value_or_attribute_correctness",
    "gte": "value_or_attribute_correctness",
    "begte": "value_or_attribute_correctness",
    "atleast": "value_or_attribute_correctness",
    "beatleast": "value_or_attribute_correctness",
    "lessthan": "value_or_attribute_correctness",
    "belessthan": "value_or_attribute_correctness",
    "tobelessthan": "value_or_attribute_correctness",
    "tobelessthanorequal": "value_or_attribute_correctness",
    "lt": "value_or_attribute_correctness",
    "belt": "value_or_attribute_correctness",
    "lte": "value_or_attribute_correctness",
    "belte": "value_or_attribute_correctness",
    "atmost": "value_or_attribute_correctness",
    "beatmost": "value_or_attribute_correctness",
    "most": "value_or_attribute_correctness",
    "bemost": "value_or_attribute_correctness",
    "isatmost": "value_or_attribute_correctness",
    "assertisatmost": "value_or_attribute_correctness",
    "closeto": "value_or_attribute_correctness",
    "tobecloseto": "value_or_attribute_correctness",
    "becloseto": "value_or_attribute_correctness",
    "approximately": "value_or_attribute_correctness",
    "beapproximately": "value_or_attribute_correctness",
    "oneof": "value_or_attribute_correctness",
    "beoneof": "value_or_attribute_correctness",
    "tomatchobject": "value_or_attribute_correctness",
    "satisfy": "value_or_attribute_correctness",
    "besatisfy": "value_or_attribute_correctness",
    "throw": "value_or_attribute_correctness",
    "nottothrow": "value_or_attribute_correctness",
    "tothrow": "value_or_attribute_correctness",
    "topass": "value_or_attribute_correctness",
    "tohavenoviolations": "accessibility_compliance",
    "matchariasnapshot": "accessibility_compliance",
}

NETWORK_SUBJECTS = frozenset({"response", "request", "network"})
API_DATA_SUBJECTS = frozenset({"api"})
PAGE_NAVIGATION_SUBJECTS = frozenset({"page"})
STRONG_SUBJECT_BASES = frozenset({
    "ast_api_call",
    "ast_cypress_subject_chain",
    "ast_response_wait_call",
})
STRONG_NAVIGATION_SUBJECT_BASES = frozenset({
    "ast_cypress_subject_chain",
    "ast_page_call",
})
HEURISTIC_SUBJECT_BASES = frozenset({
    "",
    "ast_subject_identifier_name_heuristic",
})
GENERIC_EQUALITY_MATCHERS = frozenset({
    "eq",
    "equal",
    "eql",
    "deepequal",
    "toequal",
    "tostrictequal",
    "tobe",
    "betrue",
    "befalse",
    "ok",
    "toeq",
    "beequal",
    "beeql",
})
AMBIGUOUS_CONTENT_MATCHERS = frozenset({
    "contain",
    "contains",
    "include",
    "match",
    "tocontain",
    "tomatch",
})
AMBIGUOUS_MATCHERS = GENERIC_EQUALITY_MATCHERS | AMBIGUOUS_CONTENT_MATCHERS
STATUS_MATCHERS = GENERIC_EQUALITY_MATCHERS | {
    "above",
    "atleast",
    "beatleast",
    "begreaterthan",
    "begte",
    "begt",
    "belessthan",
    "belte",
    "belt",
    "greaterthan",
    "gte",
    "gt",
    "least",
    "lessthan",
    "lte",
    "lt",
    "tobegreaterthan",
    "tobegreaterthanorequal",
    "tobelessthan",
    "tobelessthanorequal",
    "isabove",
    "assertisabove",
}
GENERIC_SCALAR_MATCHERS = frozenset({
    "be",
    "beempty",
    "bedefined",
    "befalse",
    "befalsy",
    "benull",
    "betrue",
    "betruthy",
    "defined",
    "empty",
    "false",
    "notok",
    "null",
    "ok",
    "tobe",
    "tobedefined",
    "tobeempty",
    "tobeemptystring",
    "tobefalsy",
    "tobenull",
    "tobetruthy",
    "tobeundefined",
    "true",
    "undefined",
})
COLLECTION_CONTEXT_MATCHERS = frozenset({
    "and",
    "count",
    "havecount",
    "havelength",
    "havelengthof",
    "length",
    "lengthof",
    "notok",
    "ok",
    "should",
    "size",
    "tohavecount",
    "tohavelength",
}) | GENERIC_EQUALITY_MATCHERS

SUBJECT_SEMANTIC_ROLE_TO_INTENT = {
    "element_presence": "element_presence",
    "network_status": "network_contract",
    "network_payload": "network_contract",
    "ui_control_state": "interactive_state",
    "ui_event_counter": "interactive_state",
    "style_layout_property": "style_or_visual_state",
    "text_content_payload": "content_correctness",
    "scalar_property": "value_or_attribute_correctness",
    "api_object_contract": "api_or_data_contract",
    "collection_size": "collection_size",
    "visual_snapshot_api": "visual_regression",
}

VALUE_ATTRIBUTE_MATCHERS = frozenset({
    "value",
    "havevalue",
    "tohavevalue",
    "attr",
    "haveattr",
    "haveattribute",
    "tohaveattr",
    "tohaveattribute",
    "haveprop",
    "property",
    "haveproperty",
    "tohaveproperty",
    "prop",
})

ATTRIBUTE_MATCHERS = frozenset({
    "attr",
    "haveattr",
    "haveattribute",
    "tohaveattr",
    "tohaveattribute",
    "haveprop",
    "property",
    "haveproperty",
    "tohaveproperty",
    "prop",
})


def _normalize_matcher(matcher: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (matcher or "").lower())


def _matcher_lookup_key(normalized_matcher: str) -> str:
    """Drop assertion negation tokens before intent lookup."""
    candidates = [normalized_matcher]
    if normalized_matcher.startswith("not"):
        candidates.append(normalized_matcher[3:])
    for prefix in ("be", "have", "contain"):
        marker = f"{prefix}not"
        if normalized_matcher.startswith(marker):
            candidates.append(prefix + normalized_matcher[len(marker):])
    for candidate in candidates:
        if candidate in MATCHER_TO_VERIFICATION_INTENT:
            return candidate
        if candidate in ("toequal", "tostrictequal", "equal", "eql"):
            return candidate
    return normalized_matcher


def _codebook_path_for_intent(intent: str) -> str:
    return {
        "visual_regression": "visual_snapshot_api",
        "network_contract": "network_request_response_contract",
        "element_presence": "element_presence",
        "interactive_state": "interactive_state_or_event_counter",
        "style_or_visual_state": "style_layout_css",
        "content_correctness": "user_facing_text_content",
        "api_or_data_contract": "api_object_or_result_contract",
        "value_or_attribute_correctness": "scalar_property_or_attribute",
        "collection_size": "true_collection_cardinality",
        "accessibility_compliance": "accessibility_structure",
        "navigation_outcome": "navigation_location",
    }.get(intent, "unspecified")


def _detail(intent: str, basis: str, confidence: str, signal: str, codebook_path: str = "") -> Dict[str, str]:
    return {
        "verification_intent": intent,
        "verification_intent_evidence_basis": basis,
        "verification_intent_confidence": confidence,
        "verification_intent_matched_signal": signal,
        "verification_intent_codebook_path": codebook_path or _codebook_path_for_intent(intent),
    }


def _json_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if not isinstance(value, str) or not value.strip():
        return []
    try:
        loaded = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    if not isinstance(loaded, list):
        return []
    return [str(item).strip() for item in loaded if str(item).strip()]


def _subject_path(feature: Dict[str, Any]) -> list[str]:
    return _json_list(feature.get("assertion_subject_path_json"))


def _lower_items(items: list[str]) -> set[str]:
    return {item.lower() for item in items if item}


def _path_has_any(path: list[str], names: set[str]) -> bool:
    low = _lower_items(path)
    return bool(low & names)


def _path_has_fragment(path: list[str], fragments: set[str]) -> bool:
    return any(fragment in item.lower() for item in path for fragment in fragments)


def _strong_locator_subject(subject: str, subject_basis: str) -> bool:
    return subject in {"locator", "element"} and subject_basis in (
        STRONG_SUBJECT_BASES
        | {"ast_locator_call"}
    )


def _network_subject_from_ast(subject: str, subject_basis: str, path: list[str]) -> bool:
    if subject in NETWORK_SUBJECTS and subject_basis in (STRONG_SUBJECT_BASES | {"ast_subject_property_path"}):
        return True
    low = _lower_items(path)
    if "interception" in low or "xhr" in low:
        return True
    if _path_has_fragment(path, {"postdatajson", "request", "response"}):
        if _path_has_fragment(path, {"body", "data", "header", "method", "postdatajson", "status", "url"}):
            return True
    return bool(
        low & {"request", "response", "req", "res"}
        and low & {"body", "status", "headers", "url", "method", "data"}
    )


def _navigation_subject_from_ast(path: list[str]) -> bool:
    low = _lower_items(path)
    return bool(
        low & {"currenturl", "iframesrc", "href", "location", "pathname", "requestedpage", "url", "urlpattern", "path"}
        or _path_has_fragment(path, {"currenturl", "iframesrc", "requestedpage", "urlpattern", "pathname"})
    )


def _accessibility_subject_from_ast(path: list[str]) -> bool:
    return _path_has_fragment(path, {"accessib", "a11y", "aria", "focusable", "tabindex"})


def _api_config_boolean_subject_from_ast(path: list[str]) -> bool:
    if not path:
        return False
    low = _lower_items(path)
    return bool(
        _path_has_fragment(path, {"enabled", "disabled", "featureflag", "config", "setting"})
        and not low & {"button", "input", "checkbox", "select", "locator", "element"}
    )


def _api_config_boolean_text_context(text: str) -> bool:
    return bool(
        re.search(r"\b(?:is|has|should)?[A-Za-z0-9_$]*(?:enabled|disabled|featureflag)[A-Za-z0-9_$]*\b", text or "", re.I)
        and not re.search(r"\b(?:locator|button|checkbox|input|select|radio|element)\b", text or "", re.I)
    )


def _network_alias_wait_context(text: str) -> bool:
    return bool(
        re.search(r"\bcy\.wait\s*\(\s*['\"]@", text or "", re.I)
        and re.search(r"\b(?:request|response|status|body|headers?|method|url)\b", text or "", re.I)
    )


def _accessibility_text_context(text: str) -> bool:
    return bool(
        re.search(r"(?:accessibility|a11y|aria|accessible|focusable|focusindicators?|tabindex)", text or "", re.I)
    )


def _scalar_identifier_existence_subject(path: list[str]) -> bool:
    if not path:
        return False
    low = _lower_items(path)
    if low & {"locator", "element", "node"}:
        return False
    return len(path) == 1 or _path_has_fragment(path, {"id", "token", "uuid", "key"})


def _api_subject_from_ast(subject: str, subject_basis: str, path: list[str]) -> bool:
    if subject in API_DATA_SUBJECTS and subject_basis in STRONG_SUBJECT_BASES:
        return True
    low = _lower_items(path)
    if "json" in low and "stringify" in low:
        return False
    return bool(low & {"body", "payload", "json", "data", "headers"} and not _network_subject_from_ast(subject, subject_basis, path))


def _collection_subject_from_ast(path: list[str], matcher: str) -> bool:
    return matcher in {"length", "lengthof", "tohavelength", "tohavecount", "count", "size"} or _path_has_any(
        path,
        {"length", "lengthof", "count", "size"},
    )


def _cardinality_context(path: list[str], text: str, matcher: str) -> bool:
    if _network_request_count_context(path, text, matcher):
        return False
    if _path_has_fragment(path, {"numbervalue", "timestamp"}) or re.search(r"\bnew\s+date\s*\(", text or "", re.I):
        return False
    if _collection_subject_from_ast(path, matcher):
        return True
    if re.search(r"\b(?:callcount|clickcount|calledonce|spy|stub|changespy|clickspy|blurspy)\b", text or "", re.I):
        return False
    return bool(
        matcher in STATUS_MATCHERS | GENERIC_EQUALITY_MATCHERS
        and re.search(
            r"\b(?:actualcount|initialcount|totalcount|[A-Za-z0-9_$]*rowcount|"
            r"[A-Za-z0-9_$]*itemcount|[A-Za-z0-9_$]*recordcount|"
            r"[A-Za-z0-9_$]*resultcount|[A-Za-z0-9_$]*membercount|"
            r"[A-Za-z0-9_$]*optioncount|[A-Za-z0-9_$]*columncount|[A-Za-z0-9_$]*legendcount|"
            r"row_count|item_count|record_count|count|length|size|"
            r"num[A-Za-z0-9_$]*|total[A-Za-z0-9_$]*)\b",
            text or "",
            re.I,
        )
    )


def _style_subject_from_ast(path: list[str]) -> bool:
    low_joined = " ".join(item.lower() for item in path)
    if any(
        token in low_joined
        for token in (
            "overflowx",
            "overflowy",
            "contentbottom",
            "contenttop",
            "footertop",
            "footerbottom",
            "heightattop",
            "heightatbottom",
        )
    ):
        return True
    return _path_has_fragment(
        path,
        {
            "scroll",
            "overflow",
            "height",
            "width",
            "bounding",
            "offset",
            "client",
            "style",
            "class",
            "css",
            "rect",
        },
    )


def _interactive_subject_from_ast(path: list[str]) -> bool:
    return _path_has_fragment(path, {"focus", "focused", "enabled", "disabled", "checked", "selected"})


def _text_subject_from_ast(path: list[str]) -> bool:
    return _path_has_fragment(path, {"text", "title", "label", "content", "html"})


def _presence_matcher(matcher: str) -> bool:
    return matcher in {
        "exist",
        "exists",
        "toexist",
        "notexist",
        "tobevisible",
        "tobehidden",
        "bevisible",
        "benotvisible",
        "beexist",
        "notbeexist",
        "tobeattached",
        "tobeinthedocument",
        "tobeinviewport",
    }


def _content_matcher(matcher: str) -> bool:
    return matcher in AMBIGUOUS_CONTENT_MATCHERS | {
        "tohavetext",
        "tocontaintext",
        "havetext",
        "containtext",
        "includetext",
        "havehtml",
    }


def _specific_semantic_matcher_intent(matcher: str) -> str:
    intent = MATCHER_TO_VERIFICATION_INTENT.get(matcher, "")
    if not intent:
        return ""
    if matcher in GENERIC_EQUALITY_MATCHERS or matcher in GENERIC_SCALAR_MATCHERS:
        return ""
    if matcher in STATUS_MATCHERS:
        return ""
    if matcher in AMBIGUOUS_CONTENT_MATCHERS:
        return ""
    return intent


def _api_contract_boolean_subject_from_ast(path: list[str]) -> bool:
    low = _lower_items(path)
    if "gotresponse" in low:
        return True
    response_roots = {"res", "response", "result", "apiresponse", "httpresponse"}
    return bool("ok" in low and low & response_roots)


def _network_response_boolean_subject_from_ast(path: list[str]) -> bool:
    low = _lower_items(path)
    response_roots = {"res", "response", "apiresponse", "httpresponse"}
    return bool("ok" in low and low & response_roots)


def _network_status_subject_from_ast(path: list[str]) -> bool:
    low = _lower_items(path)
    if not low & {"status", "statuscode"}:
        return False
    return bool(
        low & {"res", "response", "request", "req", "fetch", "xhr", "apiresponse", "httpresponse", "interception"}
        or _path_has_fragment(path, {"response", "request", "interception", "xhr", "httpresponse", "apiresponse"})
    )


def _event_counter_subject_from_ast(path: list[str], text: str) -> bool:
    low = _lower_items(path)
    if not (low & {"counter", "count", "callcount"} or _path_has_fragment(path, {"clickcount", "eventcount", "callcount"})):
        return False
    return bool(
        _path_has_fragment(path, {"event", "summary", "receivedevent", "callback", "handler", "clickcount"})
        or re.search(r"\b(?:event|callback|handler|emitted|received|clickcount)\b", text or "", re.I)
    )


def _textual_content_subject_from_ast(path: list[str], text: str) -> bool:
    low = _lower_items(path)
    if low & {"body", "payload", "data"} and _path_has_fragment(path, {"response", "request", "interception"}):
        return False
    return bool(
        low & {"subject", "title", "message", "label"}
        or _path_has_fragment(path, {"title", "subject", "message", "labeltext"})
        or re.search(r"\b(?:headers?|json|mail|email)\s*\.\s*(?:subject|title|message|label)\b", text or "", re.I)
    )


def _actual_visual_snapshot_context(text: str, matcher: str = "") -> bool:
    normalized = _normalize_matcher(f"{matcher} {text}")
    if any(token in normalized for token in ("tomatchsnapshot", "tomatchscreenshot", "tohavescreenshot")):
        return True
    return bool(
        re.search(
            r"\b(?:page|locator|expect\([^)]*screenshot|image)[A-Za-z0-9_$.\s]*"
            r"(?:screenshot|snapshot)\s*\(",
            text or "",
            re.I,
        )
    )


def _network_request_or_response_context(text: str) -> bool:
    return bool(
        re.search(r"\bcy\.request\s*\(", text or "", re.I)
        or re.search(r"\bcy\.wait\s*\(\s*['\"]@", text or "", re.I)
        or re.search(r"\b[A-Za-z0-9_$]*(?:res|response)[A-Za-z0-9_$]*\s*\.\s*status(?:code)?\b", text or "", re.I)
        or re.search(r"\b(?:request|response|res|req|fetch|xhr|interception|httpresponse|apiresponse)\b", text or "", re.I)
        and re.search(r"\b(?:status(?:code)?|headers?|body|payload|postdata|method|url)\b", text or "", re.I)
    )


def _network_payload_context(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:xhr\.request\.body|xhr\.response\.body|request\.body|response\.body|"
            r"interception\.(?:request|response)\.(?:body|headers?|status(?:code)?))\b",
            text or "",
            re.I,
        )
        or re.search(
            r"\b[A-Za-z0-9_$]*(?:request|response|xhr|interception)[A-Za-z0-9_$]*\s*\.\s*"
            r"(?:body|headers?|status(?:code)?)\b",
            text or "",
            re.I,
        )
    )


def _request_payload_object_contract_context(path: list[str], text: str, matcher: str) -> bool:
    low = _lower_items(path)
    if not (low and ("requestpayload" in low or _path_has_fragment(path, {"requestpayload"}))):
        return False
    if low & {"status", "statuscode", "headers", "header", "body", "method", "url"}:
        return False
    if re.search(r"\b(?:status(?:code)?|headers?|method|url)\b", text or "", re.I):
        return False
    return matcher in (
        GENERIC_EQUALITY_MATCHERS
        | STATUS_MATCHERS
        | GENERIC_SCALAR_MATCHERS
        | {"members", "includemembers", "havemembers", "haveorderedmembers", "orderedmembers"}
    )


def _network_request_count_context(path: list[str], text: str, matcher: str) -> bool:
    if matcher not in (STATUS_MATCHERS | GENERIC_EQUALITY_MATCHERS | COLLECTION_CONTEXT_MATCHERS):
        return False
    return bool(re.search(r"\b(?:matchedRequests|requestsMatched|networkRequests|requestCount|requestsCount)\b", text or "", re.I))


def _enum_membership_scalar_context(path: list[str], text: str, matcher: str) -> bool:
    if matcher not in AMBIGUOUS_CONTENT_MATCHERS:
        return False
    if not re.search(r"\bexpect\s*\(\s*\[[^\]]+['\"][^\]]*\]\s*\)\s*\.\s*(?:to)?contain", text or "", re.I):
        return False
    low = _lower_items(path)
    return bool(low & {"status", "state", "type", "kind", "mode", "name"} or re.search(r"\b(?:status|state|type|kind|mode)\b", text or "", re.I))


def _message_text_context(text: str) -> bool:
    if re.search(r"\.filter\s*\(", text or "", re.I):
        return False
    return bool(
        re.search(r"\b(?:error|err)\s*\.\s*(?:reason|message)\b", text or "", re.I)
        or re.search(r"\b[A-Za-z0-9_$]*(?:error|err)msg\b", text or "", re.I)
        or re.search(r"\b(?:notification|toast|alert|warning)[\s\S]{0,120}\b(?:body|title|subject|message|text)\b", text or "", re.I)
    )


def _array_type_contract_context(path: list[str], text: str, matcher: str) -> bool:
    if matcher not in {"bea", "bean", "be", "tobe", "toequal", "equal", "eq"}:
        return False
    return bool(
        re.search(r"\b(?:be|toBe)\.a[n]?\s*\(\s*['\"]array['\"]", text or "", re.I)
        or re.search(r"\bArray\.isArray\s*\(", text or "", re.I)
        or re.search(r"\btoBeInstanceOf\s*\(\s*Array\s*\)", text or "", re.I)
    )


def _typeof_object_shape_context(path: list[str], text: str, matcher: str) -> bool:
    if matcher not in (GENERIC_EQUALITY_MATCHERS | GENERIC_SCALAR_MATCHERS):
        return False
    return bool(re.search(r"\btypeof\s+[A-Za-z0-9_$.[\]?]+\.[A-Za-z0-9_$[\]?]+", text or "", re.I))


def _http_status_scalar_context(path: list[str], text: str) -> bool:
    low = _lower_items(path)
    if low & {"status", "statuscode"} and (
        low & {"response", "res", "request", "req", "interception", "httpresponse", "apiresponse"}
        or _path_has_fragment(path, {"response", "request", "interception", "http"})
    ):
        return True
    return bool(
        re.search(r"\b[A-Za-z0-9_$]*(?:res|response)[A-Za-z0-9_$]*\s*\.\s*status(?:code)?\b", text or "", re.I)
    )


def _http_status_code_scalar_context(path: list[str], text: str) -> bool:
    low = _lower_items(path)
    if not (low & {"status", "statuscode"} or re.search(r"\bexpect\s*\(\s*status\s*\)", text or "", re.I)):
        return False
    return bool(re.search(r"\b[1-5]\d\d\b", text or "", re.I))


def _bare_status_scalar_context(path: list[str], text: str) -> bool:
    low = _lower_items(path)
    if not (low & {"status", "statuscode"} or re.search(r"\bexpect\s*\(\s*status\s*\)", text or "", re.I)):
        return False
    return not _http_status_scalar_context(path, text) and not _network_request_or_response_context(text)


def _interactive_event_or_spy_context(path: list[str], text: str, matcher: str) -> bool:
    low = _lower_items(path)
    if _path_has_fragment(path, {"selectedrows", "previouslyselectedrows", "event", "disabledparent"}) or low & {
        "detail",
        "eventdetail",
    }:
        return True
    if _event_counter_subject_from_ast(path, text):
        return True
    if re.search(r"@\w*spy\w*\b", text or "", re.I) and matcher in {
        "becalled",
        "called",
        "notcalled",
        "havebeencalled",
        "havebeennotcalled",
        "notbeencalled",
    }:
        return True
    return bool(
        re.search(
            r"\b(?:geteventsummary|receivedevent|eventsummary|blur|change|click|selection|selectedrows|previouslyselectedrows|"
            r"disabledparent|@?[A-Za-z0-9_$]*(?:change|blur|click|select|selection)[A-Za-z0-9_$]*spy|have\.callcount|callcount)\b",
            text or "",
            re.I,
        )
        and matcher in (GENERIC_EQUALITY_MATCHERS | GENERIC_SCALAR_MATCHERS | COLLECTION_CONTEXT_MATCHERS | STATUS_MATCHERS | {"havecallcount"})
    )


def _presence_visibility_text_context(text: str) -> bool:
    return bool(
        re.search(r"\bshould\s*\([^)]*['\"](?:not\.)?(?:be\.)?(?:visible|hidden|exist)['\"]", text or "", re.I)
        or re.search(r"\b(?:isPresent|exists?)\s*\(", text or "", re.I)
        or re.search(r"\b(?:be\.visible|not\.be\.visible|be\.hidden|not\.exist)\b", text or "", re.I)
    )


def _presence_boolean_helper_context(text: str) -> bool:
    return bool(re.search(r"\bis[A-Za-z0-9_$]*(?:Visible|Present|Attached|InViewport|Displayed)\s*\(", text or "", re.I))


def _interactive_boolean_helper_context(text: str) -> bool:
    return bool(re.search(r"\bis[A-Za-z0-9_$]*(?:Enabled|Disabled|Checked|Focused|Selected|Clickable)\s*\(", text or "", re.I))


def _testcafe_exists_property_assertion(text: str) -> bool:
    return bool(
        re.search(
            r"\bt\.expect\s*\([\s\S]{0,240}\.exists\s*\)\s*\.\s*(?:ok|notOk)\s*\(",
            text or "",
            re.I,
        )
    )


def _object_or_result_contract_context(path: list[str], text: str, matcher: str) -> bool:
    low = _lower_items(path)
    if _array_type_contract_context(path, text, matcher) or _typeof_object_shape_context(path, text, matcher):
        return True
    if low & {"result", "parseddata", "parseddata", "itemlistelement", "error"} and (
        matcher in GENERIC_SCALAR_MATCHERS | {"tobeinstanceof", "instanceof", "beinstanceof"}
    ):
        return True
    return bool(
        re.search(r"\btoBeInstanceOf\s*\(\s*(?:Array|[A-Za-z0-9_$]*Page)\b", text or "", re.I)
        or re.search(r"\b(?:result|parsedData|apiResult|payload|responseData)\s*\.\s*(?:error|itemListElement|data|payload)\b", text or "", re.I)
        or re.search(r"\btypeof\s+[A-Za-z0-9_$.[\]?]+\.(?:selector|target|nodes?|impact|rule|violation|[A-Za-z0-9_$]+)\b", text or "", re.I)
    )


def _style_property_context(text: str) -> bool:
    return bool(
        _STYLE_RE.search(text or "")
        or _LAYOUT_MEASUREMENT_RE.search(text or "")
        or re.search(r"\b(?:fill-opacity|opacity|rgba?|font[-_]?size|background[-_]?color|border[-_]?color)\b", text or "", re.I)
        or re.search(r"\b[A-Za-z0-9_$]*(?:color|style|css)[A-Za-z0-9_$]*\b", text or "", re.I)
    )


def _editor_text_assertion_context(text: str, matcher: str) -> bool:
    return bool(
        matcher in (AMBIGUOUS_CONTENT_MATCHERS | {"should", "and", "contain", "contains", "include"})
        and re.search(r"\b(?:tiptap|prosemirror|editor|contenteditable|find\s*\(\s*['\"]h[1-6]['\"]|<h[1-6])\b", text or "", re.I)
        and re.search(r"\b(?:contain|contains|include|have\.text|tohavetext|text)\b", text or "", re.I)
    )


def _payload_scalar_property_context(path: list[str], text: str, matcher: str) -> bool:
    if matcher not in (GENERIC_EQUALITY_MATCHERS | STATUS_MATCHERS | GENERIC_SCALAR_MATCHERS):
        return False
    if re.search(r"\b(?:deep|include|members|matchobject|schema|instanceof|be\.an?\s*\(\s*['\"]object)", text or "", re.I):
        return False
    if re.search(r"\b(?:result|payload|data)\.(?:error|gotresponse|body|headers?|request|response|interception)\b", text or "", re.I):
        return False
    return bool(
        re.search(r"\b(?:payload|result|data)\.[A-Za-z_$][A-Za-z0-9_$]*(?:_[A-Za-z0-9_$]+)?\b", text or "", re.I)
        and not re.search(r"\b(?:body|headers?|request|response|interception)\b", text or "", re.I)
    )


def _text_payload_context(text: str) -> bool:
    if _network_request_or_response_context(text):
        return False
    return bool(
        re.search(r"\b(?:args|payload|detail|notification|notify|mail|message)[\s\S]{0,240}\b(?:body|title|subject|message|text)\b", text or "", re.I)
        or re.search(r"\b(?:body|title|subject|message|text)\s*[:.]\s*(?:string|['\"`])", text or "", re.I)
    )


def _payload_membership_context(path: list[str], matcher: str, text: str) -> bool:
    if matcher not in {"includemembers", "members", "includeallmembers", "havemembers"}:
        return False
    if re.search(r"\b(?:locator|element|text|contains?|html)\b", text or "", re.I):
        return False
    low = _lower_items(path)
    return bool(not path or low & {"result", "results", "payload", "body", "data", "json", "values", "items"})


def _event_or_spy_contract_context(text: str, matcher: str) -> bool:
    if matcher in {
        "tohavebeencalled",
        "tohavebeencalledwith",
        "tohavebeencalledtimes",
        "called",
        "calledwith",
        "calledwithmatch",
        "calledonce",
        "calledtwice",
        "calledthrice",
        "havebeencalled",
        "havebeencalledwith",
    }:
        return True
    return bool(_CALL_SPY_RE.search(text) and re.search(r"\b(?:called|spy|stub|mock)\b", text, re.I))


def classify_verification_intent_detail(
    oracle_category: str,
    name: str = "",
    raw: str = "",
    feature: Dict[str, Any] | None = None,
) -> Dict[str, str]:
    """Classify verification intent, preferring AST assertion-chain metadata."""
    feature = feature or {}
    semantic_matcher = str(feature.get("assertion_semantic_matcher_ast") or "")
    matcher_raw = semantic_matcher or str(feature.get("assertion_matcher") or "")
    matcher_normalized = _normalize_matcher(matcher_raw)
    matcher = _matcher_lookup_key(matcher_normalized)
    subject = str(feature.get("assertion_subject_kind") or "").strip().lower()
    subject_basis = str(feature.get("assertion_subject_basis_ast") or "").strip()
    subject_path = _subject_path(feature)
    oracle_mapped = map_verification_intent(oracle_category)
    subject_text = str(feature.get("assertion_subject_text_ast") or "")
    text_for_context = f"{name} {raw} {matcher_raw} {subject_text}".lower()
    callback_hint = str(feature.get("assertion_callback_intent_hint_ast") or "").strip()
    callback_basis = str(feature.get("assertion_callback_intent_basis_ast") or "").strip()
    subject_semantic_role = str(feature.get("assertion_subject_semantic_role_ast") or "").strip()
    weak_subject_roles = {"scalar_property", "api_object_contract", "text_content_payload"}

    if matcher in {
        "tohaveaccessiblename",
        "tohaveaccessibledescription",
        "tohaveaccessibleerror",
        "tohaveaccessibleerrormessage",
        "tohaverole",
        "tomatchariasnapshot",
    }:
        return _detail(
            "accessibility_compliance",
            "ast_assertion_matcher",
            "high",
            f"matcher:{matcher}",
        )

    if subject_semantic_role == "network_payload":
        return _detail(
            "network_contract",
            "ast_assertion_subject_semantic_role",
            "high",
            f"subject_semantic_role:{subject_semantic_role};matcher:{matcher}",
            "network_request_response_contract",
        )

    if (
        subject in PAGE_NAVIGATION_SUBJECTS
        and subject_basis in STRONG_NAVIGATION_SUBJECT_BASES
        and matcher in (AMBIGUOUS_MATCHERS | {"endwith"})
    ):
        return _detail(
            "navigation_outcome",
            "ast_assertion_subject",
            "medium",
            f"subject:{subject};basis:{subject_basis};matcher:{matcher}",
            "navigation_location",
        )

    if _network_subject_from_ast(subject, subject_basis, subject_path):
        return _detail(
            "network_contract",
            "ast_assertion_subject",
            "high" if subject_basis in STRONG_SUBJECT_BASES else "medium",
            f"subject:{subject};basis:{subject_basis or 'path'}",
            "network_request_response_contract",
        )

    if _network_request_or_response_context(text_for_context) and (
        matcher in STATUS_MATCHERS | AMBIGUOUS_MATCHERS | GENERIC_SCALAR_MATCHERS | VALUE_ATTRIBUTE_MATCHERS | {"includematch", "property", "haveproperty"}
    ):
        return _detail(
            "network_contract",
            "lexical_network_context",
            "medium",
            f"matcher:{matcher};network_context",
            "network_request_response_contract",
        )

    if _accessibility_text_context(text_for_context) and matcher in (
        STATUS_MATCHERS
        | GENERIC_SCALAR_MATCHERS
        | ATTRIBUTE_MATCHERS
        | {"topass", "tohavecount", "tohavelength", "haveattr", "tohaveattr", "tohaveattribute"}
    ):
        return _detail(
            "accessibility_compliance",
            "lexical_accessibility_context",
            "medium",
            f"matcher:{matcher};accessibility_context",
            "accessibility_structure",
        )

    if matcher in VALUE_ATTRIBUTE_MATCHERS and re.search(r"\b(?:href|url|link|pathname|currenturl|requestedpage)\b", text_for_context, re.I):
        return _detail(
            "navigation_outcome",
            "ast_assertion_semantic_matcher" if semantic_matcher else "lexical_navigation_context",
            "medium",
            f"matcher:{matcher};href_or_url_attribute",
            "navigation_location",
        )

    if matcher in VALUE_ATTRIBUTE_MATCHERS and _style_property_context(text_for_context):
        return _detail(
            "style_or_visual_state",
            "ast_assertion_semantic_matcher" if semantic_matcher else "lexical_style_context",
            "medium",
            f"matcher:{matcher};style_attribute_context",
            "style_layout_css",
        )

    if matcher in VALUE_ATTRIBUTE_MATCHERS:
        return _detail(
            "value_or_attribute_correctness",
            "ast_assertion_semantic_matcher" if semantic_matcher else "ast_assertion_matcher",
            "high" if matcher_raw else "medium",
            f"matcher:{matcher};value_attribute_current_matcher",
            "scalar_property_or_attribute",
        )

    if matcher in AMBIGUOUS_CONTENT_MATCHERS and re.search(r"\b(?:href|url|link|pathname|currenturl|requestedpage)\b", text_for_context, re.I):
        return _detail(
            "navigation_outcome",
            "ast_assertion_semantic_matcher" if semantic_matcher else "lexical_navigation_context",
            "medium",
            f"matcher:{matcher};href_or_url_content_matcher",
            "navigation_location",
        )

    if subject_semantic_role == "text_content_payload" and matcher in {"havetext", "tohavetext", "containtext", "tocontaintext"}:
        return _detail(
            "content_correctness",
            "ast_assertion_subject_semantic_role",
            "high",
            f"subject_semantic_role:{subject_semantic_role};matcher:{matcher}",
            "user_facing_text_content",
        )

    if subject_semantic_role == "text_content_payload" and matcher in AMBIGUOUS_CONTENT_MATCHERS:
        return _detail(
            "content_correctness",
            "ast_assertion_subject_semantic_role",
            "medium",
            f"subject_semantic_role:{subject_semantic_role};matcher:{matcher}",
            "user_facing_text_content",
        )

    if matcher in {"havetext", "tohavetext", "containtext", "tocontaintext"}:
        return _detail(
            "content_correctness",
            "ast_assertion_semantic_matcher" if semantic_matcher else "ast_assertion_matcher",
            "high" if semantic_matcher else "medium",
            f"matcher:{matcher};current_text_matcher",
            "user_facing_text_content",
        )

    if _request_payload_object_contract_context(subject_path, text_for_context, matcher):
        return _detail(
            "api_or_data_contract",
            "ast_assertion_subject_path" if subject_path else "lexical_object_contract_context",
            "medium",
            f"subject_path:{'.'.join(subject_path[:8])};matcher:{matcher};request_payload_object_contract",
            "api_object_or_result_contract",
        )

    if _network_request_count_context(subject_path, text_for_context, matcher):
        return _detail(
            "network_contract",
            "ast_assertion_subject_path" if subject_path else "lexical_network_context",
            "medium",
            f"subject_path:{'.'.join(subject_path[:8])};matcher:{matcher};network_request_count",
            "network_request_response_contract",
        )

    if _enum_membership_scalar_context(subject_path, text_for_context, matcher):
        return _detail(
            "value_or_attribute_correctness",
            "ast_assertion_subject_path" if subject_path else "lexical_scalar_property_context",
            "medium",
            f"subject_path:{'.'.join(subject_path[:8]) or 'enum'};matcher:{matcher};enum_membership",
            "scalar_property_or_attribute",
        )

    if _message_text_context(text_for_context):
        return _detail(
            "content_correctness",
            "lexical_text_property_context",
            "medium",
            f"matcher:{matcher};message_text_context",
            "user_facing_text_content",
        )

    if _array_type_contract_context(subject_path, text_for_context, matcher) or _typeof_object_shape_context(subject_path, text_for_context, matcher):
        return _detail(
            "api_or_data_contract",
            "ast_assertion_subject_path" if subject_path else "lexical_object_contract_context",
            "medium",
            f"subject_path:{'.'.join(subject_path[:8])};matcher:{matcher};type_or_shape_contract",
            "api_object_or_result_contract",
        )

    if _network_payload_context(text_for_context) and not _network_subject_from_ast(subject, subject_basis, subject_path):
        return _detail(
            "network_contract",
            "lexical_network_payload_context",
            "medium",
            f"matcher:{matcher};network_payload_context",
        )

    if re.search(r"\b(?:cy\.url|cy\.location|currenturl|location\.(?:href|pathname|search|hash)|window\.location)\b", text_for_context, re.I):
        return _detail(
            "navigation_outcome",
            "lexical_navigation_context",
            "medium",
            "url_or_location_subject_context",
        )

    if matcher in {"havehtml", "containhtml", "tohavehtml"} or re.search(r"\b(?:contain|have)\.html\b", text_for_context, re.I):
        return _detail(
            "content_correctness",
            "ast_assertion_semantic_matcher" if semantic_matcher else "lexical_html_content_context",
            "high" if semantic_matcher else "medium",
            f"matcher:{matcher};html_content_context",
        )

    if re.search(r"\b(?:getcssclasses|classlist|classname|getelementstyle)\b|\b(?:fill-opacity|padding|margin|font|layout|css)\b", text_for_context, re.I):
        return _detail(
            "style_or_visual_state",
            "lexical_style_context",
            "medium",
            "style_or_class_subject_context",
        )

    if _style_subject_from_ast(subject_path) and matcher in (
        AMBIGUOUS_CONTENT_MATCHERS
        | STATUS_MATCHERS
        | GENERIC_EQUALITY_MATCHERS
        | {"includes", "include", "atmost", "beatmost", "most", "closeto", "tobecloseto"}
    ):
        return _detail(
            "style_or_visual_state",
            "ast_assertion_subject_path",
            "medium",
            f"subject_path:{'.'.join(subject_path[:8])};matcher:{matcher};style_subject_context",
            "style_layout_css",
        )

    if _presence_boolean_helper_context(text_for_context):
        return _detail(
            "element_presence",
            "lexical_presence_property_context",
            "medium",
            f"matcher:{matcher};presence_boolean_helper",
        )

    if _interactive_boolean_helper_context(text_for_context):
        return _detail(
            "interactive_state",
            "lexical_interactive_state_context",
            "medium",
            f"matcher:{matcher};interactive_boolean_helper",
        )

    if re.search(r"\b(?:componentdidload|componentdidrender|componentwillload|componentdidupdate|callcount|changespy|clickspy|blurspy)\b", text_for_context, re.I):
        return _detail(
            "interactive_state",
            "lexical_interactive_state_context",
            "medium",
            "event_or_lifecycle_counter_context",
        )

    if re.search(r"\b[A-Za-z0-9_$?.]+\s*\)\s*\.\s*(?:to|be)\.a[n]?\s*\(\s*['\"]function['\"]", text_for_context, re.I) or re.search(
        r"\b_satellite\??\.\s*track\b", text_for_context, re.I
    ):
        return _detail(
            "api_or_data_contract",
            "lexical_object_contract_context",
            "medium",
            f"matcher:{matcher};function_contract_context",
            "api_object_or_result_contract",
        )

    if (
        subject_semantic_role == "scalar_property"
        and matcher in STATUS_MATCHERS
        and re.search(r"\bexpect\s*\(\s*status\s*\)", text_for_context, re.I)
        and re.search(r"\b[1-5]\d\d\b", text_for_context)
    ):
        return _detail(
            "network_contract",
            "lexical_api_status_context",
            "medium",
            f"matcher:{matcher};bare_status_http_code_context",
            "network_request_response_contract",
        )

    if _bare_status_scalar_context(subject_path, text_for_context) and matcher in STATUS_MATCHERS:
        return _detail(
            "value_or_attribute_correctness",
            "ast_assertion_subject_path" if subject_path else "lexical_scalar_status_context",
            "medium",
            f"subject_path:{'.'.join(subject_path[:8]) or 'status'};matcher:{matcher};bare_status_scalar",
            "scalar_property_or_attribute",
        )

    if re.search(r"\b(?:getnodes|selector\s*\([^)]*\))?\s*\.count\b|\bcount\s*\)", text_for_context, re.I):
        return _detail(
            "collection_size",
            "lexical_collection_context",
            "medium",
            "count_property_context",
        )

    if (
        subject_semantic_role == "scalar_property"
        and matcher in STATUS_MATCHERS
        and _http_status_scalar_context(subject_path, text_for_context)
    ):
        return _detail(
            "network_contract",
            "ast_assertion_subject_path" if subject_path else "lexical_api_status_context",
            "medium",
            f"subject_path:{'.'.join(subject_path[:8])};matcher:{matcher};status_context",
        )

    if (
        subject_semantic_role == "scalar_property"
        and matcher in STATUS_MATCHERS
        and re.search(r"\bexpect\s*\(\s*status\s*\)", text_for_context, re.I)
        and re.search(r"\b[1-5]\d\d\b", text_for_context)
    ):
        return _detail(
            "network_contract",
            "lexical_api_status_context",
            "medium",
            f"matcher:{matcher};bare_status_http_code_context",
            "network_request_response_contract",
        )

    if subject_semantic_role == "scalar_property" and _event_counter_subject_from_ast(subject_path, text_for_context):
        return _detail(
            "interactive_state",
            "ast_assertion_subject_path" if subject_path else "lexical_interactive_state_context",
            "medium",
            f"subject_path:{'.'.join(subject_path[:8])};matcher:{matcher};event_counter_scalar",
            "interactive_state_or_event_counter",
        )

    if (
        subject_semantic_role == "ui_control_state"
        and matcher in (GENERIC_EQUALITY_MATCHERS | {"notok"})
        and (
            _testcafe_exists_property_assertion(text_for_context)
            or _presence_visibility_text_context(text_for_context)
        )
    ):
        return _detail(
            "element_presence",
            "lexical_presence_property_context",
            "medium",
            f"matcher:{matcher};presence_visibility_context",
        )

    if _presence_matcher(matcher) and (
        subject_semantic_role in weak_subject_roles
        or _accessibility_text_context(text_for_context)
        or re.search(r"\b(?:findbyattribute|aria-label|aria-labelledby|findbytitle|locator|getby)\b", text_for_context, re.I)
    ):
        return _detail(
            "element_presence",
            "ast_assertion_semantic_matcher" if semantic_matcher else "ast_assertion_matcher",
            "high" if semantic_matcher else "medium",
            f"matcher:{matcher};presence_over_weak_subject_role",
        )

    if subject_semantic_role in {"ui_control_state", "ui_event_counter"}:
        return _detail(
            "interactive_state",
            "ast_assertion_subject_semantic_role",
            "high",
            f"subject_semantic_role:{subject_semantic_role};matcher:{matcher}",
            "interactive_state_or_event_counter",
        )

    if (
        subject_semantic_role != "collection_size"
        and _cardinality_context(subject_path, text_for_context, matcher)
        and not _network_request_or_response_context(text_for_context)
        and not _accessibility_text_context(text_for_context)
    ):
        return _detail(
            "collection_size",
            "ast_assertion_subject_path" if subject_path else "lexical_collection_context",
            "medium",
            f"subject_path:{'.'.join(subject_path[:8])};matcher:{matcher}",
        )

    if _navigation_subject_from_ast(subject_path) and matcher in (AMBIGUOUS_MATCHERS | STATUS_MATCHERS | {"endwith"}):
        return _detail(
            "navigation_outcome",
            "ast_assertion_subject_path",
            "medium",
            f"subject_path:{'.'.join(subject_path[:8])};matcher:{matcher}",
        )

    if _style_property_context(text_for_context) and (
        matcher in STATUS_MATCHERS | GENERIC_EQUALITY_MATCHERS
        or _specific_semantic_matcher_intent(matcher) == "style_or_visual_state"
    ):
        return _detail(
            "style_or_visual_state",
            "ast_assertion_semantic_matcher" if semantic_matcher else "lexical_style_context",
            "high" if semantic_matcher else "medium",
            f"matcher:{matcher};style_context",
        )

    if _editor_text_assertion_context(text_for_context, matcher):
        return _detail(
            "content_correctness",
            "lexical_text_property_context",
            "medium",
            f"matcher:{matcher};editor_text_context",
            "text_payload_context",
        )

    if _accessibility_text_context(text_for_context) and matcher in (
        STATUS_MATCHERS
        | GENERIC_SCALAR_MATCHERS
        | ATTRIBUTE_MATCHERS
        | {"topass", "tohavecount", "tohavelength", "haveattr", "tohaveattr", "tohaveattribute"}
    ):
        return _detail(
            "accessibility_compliance",
            "lexical_accessibility_context",
            "medium",
            f"matcher:{matcher};accessibility_context",
        )

    if _payload_scalar_property_context(subject_path, text_for_context, matcher):
        return _detail(
            "value_or_attribute_correctness",
            "ast_assertion_subject_path" if subject_path else "lexical_scalar_property_context",
            "medium",
            f"subject_path:{'.'.join(subject_path[:8]) or 'payload'};matcher:{matcher};payload_scalar",
            "scalar_property_or_attribute",
        )

    if subject_semantic_role in SUBJECT_SEMANTIC_ROLE_TO_INTENT and subject_semantic_role not in weak_subject_roles:
        return _detail(
            SUBJECT_SEMANTIC_ROLE_TO_INTENT[subject_semantic_role],
            "ast_assertion_subject_semantic_role",
            "high",
            f"subject_semantic_role:{subject_semantic_role}",
        )

    if _actual_visual_snapshot_context(text_for_context, matcher):
        return _detail(
            "visual_regression",
            "lexical_visual_context",
            "medium",
            f"matcher:{matcher};visual_context",
        )

    if not semantic_matcher and re.search(r"\bgetelementstyle\s*\([^)]*['\"]visibility['\"]", text_for_context, re.I):
        return _detail(
            "style_or_visual_state",
            "lexical_style_context",
            "medium",
            "style_or_layout_subject_context",
        )

    if not semantic_matcher and not (
        subject in PAGE_NAVIGATION_SUBJECTS and subject_basis in STRONG_NAVIGATION_SUBJECT_BASES
    ) and (
        re.search(r"\bcy\.location\s*\(|\bloc\.(?:href|pathname|origin|host|hostname|search|hash)\b", text_for_context, re.I)
        or (
            _NAV_RE.search(text_for_context)
            and not _network_request_or_response_context(text_for_context)
        )
    ):
        return _detail(
            "navigation_outcome",
            "lexical_navigation_context",
            "medium",
            "location_or_url_subject_context",
        )

    if not semantic_matcher and (
        re.search(r"\.(?:exists|isconnected)\b|\bto(beattached|beinviewport)\s*\(", text_for_context, re.I)
    ):
        return _detail(
            "element_presence",
            "lexical_presence_context",
            "medium",
            "element_presence_subject_context",
        )

    if not semantic_matcher and (
        re.search(r"\bis(?:disabled|enabled|checked|focused|selected)\s*\(", text_for_context, re.I)
        or re.search(r"\b(?:ariaselectedtext|typedsignatureenabled)\b", text_for_context, re.I)
    ):
        return _detail(
            "interactive_state",
            "lexical_interactive_state_context",
            "medium",
            "control_or_selection_state_context",
        )

    if not subject_semantic_role and _object_or_result_contract_context(subject_path, text_for_context, matcher):
        return _detail(
            "api_or_data_contract",
            "ast_assertion_subject_path" if subject_path else "lexical_object_contract_context",
            "medium",
            f"subject_path:{'.'.join(subject_path[:8])};matcher:{matcher};object_contract_context",
            "api_object_or_result_contract",
        )

    if subject_semantic_role in SUBJECT_SEMANTIC_ROLE_TO_INTENT:
        return _detail(
            SUBJECT_SEMANTIC_ROLE_TO_INTENT[subject_semantic_role],
            "ast_assertion_subject_semantic_role",
            "high",
            f"subject_semantic_role:{subject_semantic_role}",
        )

    if (
        callback_basis == "ast_callback_nested_assertion"
        and (
            _network_subject_from_ast(subject, subject_basis, subject_path)
            or re.search(r"\bcy\.wait\s*\(\s*['\"]@", text_for_context, re.I)
            or _INTERCEPT_RESPONSE_VALUE_RE.search(text_for_context)
        )
    ):
        count = str(feature.get("assertion_callback_nested_assertion_count") or "").strip()
        count_signal = f";nested_count:{count}" if count else ""
        return _detail(
            "network_contract",
            "ast_callback_nested_assertion",
            "medium",
            f"callback_network_context{count_signal}",
        )

    if (
        callback_basis == "ast_callback_nested_assertion"
        and callback_hint in VERIFICATION_INTENT_LABELS
        and callback_hint != "unspecified"
    ):
        nested_matchers = {
            _matcher_lookup_key(_normalize_matcher(item))
            for item in _json_list(feature.get("assertion_callback_nested_matchers_json"))
        }
        if callback_hint == "element_presence" or nested_matchers & {
            "tobevisible",
            "bevisible",
            "exist",
            "exists",
            "toexist",
            "tobeattached",
            "tobeinviewport",
        }:
            return _detail(
                "element_presence",
                "ast_callback_nested_assertion",
                "medium",
                "callback_nested_presence_matcher",
                "callback_element_presence",
            )
        if _style_property_context(text_for_context):
            return _detail(
                "style_or_visual_state",
                "lexical_style_context",
                "medium",
                "callback_style_context",
            )
        if "includemembers" in _normalize_matcher(text_for_context):
            return _detail(
                "api_or_data_contract",
                "ast_callback_nested_assertion",
                "medium",
                "callback_nested_matcher:include.members",
            )
        if nested_matchers & {
            "value",
            "havevalue",
            "tohavevalue",
            "attr",
            "haveattr",
            "haveattribute",
            "tohaveattribute",
        }:
            return _detail(
                "value_or_attribute_correctness",
                "ast_callback_nested_assertion",
                "medium",
                f"callback_nested_matcher:{sorted(nested_matchers)[0]}",
            )
        count = str(feature.get("assertion_callback_nested_assertion_count") or "").strip()
        count_signal = f";nested_count:{count}" if count else ""
        return _detail(
            callback_hint,
            "ast_callback_nested_assertion",
            "medium",
            f"callback_hint:{callback_hint}{count_signal}",
        )

    if matcher:
        if _actual_visual_snapshot_context(text_for_context, matcher):
            return _detail(
                "visual_regression",
                "lexical_visual_context",
                "medium",
                f"matcher:{matcher};visual_context",
            )
        if (
            subject in PAGE_NAVIGATION_SUBJECTS
            and subject_basis in STRONG_NAVIGATION_SUBJECT_BASES
            and matcher in (AMBIGUOUS_MATCHERS | {"endwith"})
        ):
            return _detail(
                "navigation_outcome",
                "ast_assertion_subject",
                "medium",
                f"subject:{subject};basis:{subject_basis};matcher:{matcher}",
            )
        if (
            _NAV_RE.search(text_for_context)
            and matcher in (STATUS_MATCHERS | AMBIGUOUS_MATCHERS)
            and not _network_request_or_response_context(text_for_context)
        ):
            return _detail(
                "navigation_outcome",
                "lexical_navigation_context",
                "medium",
                f"matcher:{matcher};navigation_context",
            )
        if _network_subject_from_ast(subject, subject_basis, subject_path):
            return _detail(
                "network_contract",
                "ast_assertion_subject",
                "high" if subject_basis in STRONG_SUBJECT_BASES else "medium",
                f"subject:{subject};basis:{subject_basis or 'path'}",
            )
        if _network_request_or_response_context(text_for_context) and (
            matcher in STATUS_MATCHERS | AMBIGUOUS_MATCHERS | GENERIC_SCALAR_MATCHERS | {"includematch", "property", "haveproperty"}
        ):
            return _detail(
                "network_contract",
                "lexical_network_context",
                "medium",
                f"matcher:{matcher};network_context",
            )
        if _bare_status_scalar_context(subject_path, text_for_context) and matcher in STATUS_MATCHERS:
            return _detail(
                "value_or_attribute_correctness",
                "ast_assertion_subject_path" if subject_path else "lexical_scalar_status_context",
                "medium",
                f"subject_path:{'.'.join(subject_path[:8]) or 'status'};matcher:{matcher};bare_status_scalar",
                "scalar_property_or_attribute",
            )
        if _http_status_scalar_context(subject_path, text_for_context) and matcher in STATUS_MATCHERS:
            return _detail(
                "network_contract",
                "ast_assertion_subject_path" if subject_path else "lexical_api_status_context",
                "medium",
                f"subject_path:{'.'.join(subject_path[:8])};matcher:{matcher}",
            )
        if _style_property_context(text_for_context) and (
            matcher in STATUS_MATCHERS | GENERIC_EQUALITY_MATCHERS
            or _specific_semantic_matcher_intent(matcher) == "style_or_visual_state"
        ):
            return _detail(
                "style_or_visual_state",
                "ast_assertion_semantic_matcher" if semantic_matcher else "lexical_style_context",
                "high" if semantic_matcher else "medium",
                f"matcher:{matcher};style_context",
            )
        if _interactive_event_or_spy_context(subject_path, text_for_context, matcher):
            return _detail(
                "interactive_state",
                "ast_assertion_subject_path" if subject_path else "lexical_event_detail_context",
                "medium",
                f"subject_path:{'.'.join(subject_path[:8])};matcher:{matcher}",
            )
        if _presence_visibility_text_context(text_for_context) and not semantic_matcher:
            return _detail(
                "element_presence",
                "lexical_presence_property_context",
                "medium",
                f"matcher:{matcher};presence_visibility_context",
            )
        if _object_or_result_contract_context(subject_path, text_for_context, matcher):
            return _detail(
                "api_or_data_contract",
                "ast_assertion_subject_path" if subject_path else "lexical_object_contract_context",
                "medium",
                f"subject_path:{'.'.join(subject_path[:8])};matcher:{matcher}",
            )
        if _text_payload_context(text_for_context):
            return _detail(
                "content_correctness",
                "lexical_text_property_context",
                "medium",
                f"matcher:{matcher};text_payload_context",
            )
        if matcher in VALUE_ATTRIBUTE_MATCHERS:
            return _detail(
                "value_or_attribute_correctness",
                "ast_assertion_semantic_matcher" if semantic_matcher else "ast_assertion_matcher",
                "high" if matcher_raw else "medium",
                f"matcher:{matcher};value_attribute_current_matcher",
                "scalar_property_or_attribute",
            )
        if _accessibility_text_context(text_for_context) and matcher in (
            STATUS_MATCHERS | GENERIC_SCALAR_MATCHERS | {"topass", "tohavecount", "tohavelength"}
        ):
            return _detail(
                "accessibility_compliance",
                "lexical_accessibility_context",
                "medium",
                f"matcher:{matcher};accessibility_context",
            )
        if _cardinality_context(subject_path, text_for_context, matcher):
            return _detail(
                "collection_size",
                "ast_assertion_subject_path" if subject_path else "lexical_collection_context",
                "medium",
                f"subject_path:{'.'.join(subject_path[:8])};matcher:{matcher}",
            )
        if _network_status_subject_from_ast(subject_path):
            return _detail(
                "network_contract",
                "ast_assertion_subject_path",
                "medium",
                f"subject_path:{'.'.join(subject_path[:8])};matcher:{matcher}",
            )
        if _network_response_boolean_subject_from_ast(subject_path) and matcher in (
            GENERIC_EQUALITY_MATCHERS | GENERIC_SCALAR_MATCHERS
        ):
            return _detail(
                "network_contract",
                "ast_assertion_subject_path",
                "medium",
                f"subject_path:{'.'.join(subject_path[:8])};matcher:{matcher}",
            )
        if _event_counter_subject_from_ast(subject_path, text_for_context) and matcher in (
            GENERIC_EQUALITY_MATCHERS | STATUS_MATCHERS | COLLECTION_CONTEXT_MATCHERS
        ):
            return _detail(
                "interactive_state",
                "ast_assertion_subject_path",
                "medium",
                f"subject_path:{'.'.join(subject_path[:8])};matcher:{matcher}",
            )
        if _navigation_subject_from_ast(subject_path) and matcher in (AMBIGUOUS_MATCHERS | STATUS_MATCHERS | {"endwith"}):
            return _detail(
                "navigation_outcome",
                "ast_assertion_subject_path",
                "medium",
                f"subject_path:{'.'.join(subject_path[:8])};matcher:{matcher}",
            )
        if _payload_membership_context(subject_path, matcher, text_for_context):
            return _detail(
                "api_or_data_contract",
                "ast_assertion_subject_path",
                "medium",
                f"subject_path:{'.'.join(subject_path[:8]) or 'payload'};matcher:{matcher}",
            )
        if _scalar_identifier_existence_subject(subject_path) and _presence_matcher(matcher) and matcher not in {
            "tobevisible",
            "tobehidden",
            "bevisible",
            "benotvisible",
        } and not _strong_locator_subject(subject, subject_basis):
            return _detail(
                "value_or_attribute_correctness",
                "ast_assertion_subject_path",
                "medium",
                f"subject_path:{'.'.join(subject_path[:8])};matcher:{matcher}",
            )
        if _presence_matcher(matcher):
            return _detail(
                "element_presence",
                "ast_assertion_semantic_matcher"
                if semantic_matcher
                else ("ast_assertion_subject_and_matcher" if _strong_locator_subject(subject, subject_basis) else "ast_assertion_matcher"),
                "high" if _strong_locator_subject(subject, subject_basis) else "medium",
                f"subject:{subject or 'unknown'};matcher:{matcher}",
            )
        if _FILTERED_COLLECTION_RE.search(text_for_context) and matcher in GENERIC_EQUALITY_MATCHERS:
            return _detail(
                "collection_size",
                "lexical_collection_filter_context",
                "medium",
                f"matcher:{matcher};filtered_collection",
            )
        if _LENGTH_RE.search(text_for_context) and matcher in (
            GENERIC_EQUALITY_MATCHERS | {"should", "and", "notok", "ok"}
        ):
            return _detail(
                "collection_size",
                "lexical_collection_context",
                "medium",
                f"matcher:{matcher};collection_context",
            )
        if _textual_content_subject_from_ast(subject_path, text_for_context) and matcher in (
            GENERIC_EQUALITY_MATCHERS | AMBIGUOUS_CONTENT_MATCHERS | GENERIC_SCALAR_MATCHERS
        ):
            return _detail(
                "content_correctness",
                "ast_assertion_subject_path" if subject_path else "lexical_text_property_context",
                "medium",
                f"subject_path:{'.'.join(subject_path[:8])};matcher:{matcher}",
            )
        if _collection_subject_from_ast(subject_path, matcher) and matcher in COLLECTION_CONTEXT_MATCHERS:
            intent = "network_contract" if _network_subject_from_ast(subject, subject_basis, subject_path) else "collection_size"
            return _detail(
                intent,
                "ast_assertion_subject_path",
                "medium",
                f"subject_path:{'.'.join(subject_path[:8])};matcher:{matcher}",
            )
        if _network_subject_from_ast(subject, subject_basis, subject_path):
            return _detail(
                "network_contract",
                "ast_assertion_subject",
                "high" if subject_basis in STRONG_SUBJECT_BASES else "medium",
                f"subject:{subject};basis:{subject_basis or 'path'}",
            )
        if matcher in VALUE_ATTRIBUTE_MATCHERS:
            return _detail(
                "value_or_attribute_correctness",
                "ast_assertion_semantic_matcher" if semantic_matcher else "ast_assertion_matcher",
                "high" if matcher_raw else "medium",
                f"matcher:{matcher};value_attribute_current_matcher",
                "scalar_property_or_attribute",
            )
        if _accessibility_subject_from_ast(subject_path):
            return _detail(
                "accessibility_compliance",
                "ast_assertion_subject_path",
                "medium",
                f"subject_path:{'.'.join(subject_path[:8])};matcher:{matcher}",
            )
        if _api_config_boolean_subject_from_ast(subject_path) and matcher in (
            GENERIC_EQUALITY_MATCHERS | GENERIC_SCALAR_MATCHERS
        ):
            return _detail(
                "api_or_data_contract",
                "ast_assertion_subject_path",
                "medium",
                f"subject_path:{'.'.join(subject_path[:8])};matcher:{matcher}",
            )
        if _api_config_boolean_text_context(text_for_context) and matcher in (
            GENERIC_EQUALITY_MATCHERS | GENERIC_SCALAR_MATCHERS
        ):
            return _detail(
                "api_or_data_contract",
                "lexical_api_config_boolean_context",
                "medium",
                f"matcher:{matcher};api_config_boolean_context",
            )
        if (
            subject in PAGE_NAVIGATION_SUBJECTS
            and subject_basis in STRONG_NAVIGATION_SUBJECT_BASES
            and matcher in (AMBIGUOUS_MATCHERS | {"endwith"})
        ):
            return _detail(
                "navigation_outcome",
                "ast_assertion_subject",
                "medium",
                f"subject:{subject};basis:{subject_basis};matcher:{matcher}",
            )
        if (
            _NAV_RE.search(text_for_context)
            and matcher in (STATUS_MATCHERS | AMBIGUOUS_MATCHERS)
            and not _network_request_or_response_context(text_for_context)
        ):
            return _detail(
                "navigation_outcome",
                "lexical_navigation_context",
                "medium",
                f"matcher:{matcher};navigation_context",
            )
        if _api_subject_from_ast(subject, subject_basis, subject_path) and (
            matcher in GENERIC_EQUALITY_MATCHERS or oracle_mapped == "api_or_data_contract"
        ):
            return _detail(
                "api_or_data_contract",
                "ast_assertion_subject",
                "medium",
                f"subject:{subject};basis:{subject_basis or 'path'};matcher:{matcher}",
            )
        if _EVENT_DETAIL_RE.search(text_for_context) and matcher in (
            AMBIGUOUS_MATCHERS | {"should", "and", "exist", "toexist", "instanceof", "tobeinstanceof"}
        ) and _event_or_spy_contract_context(text_for_context, matcher):
            return _detail(
                "api_or_data_contract",
                "lexical_event_detail_context",
                "medium",
                f"matcher:{matcher};event_detail_context",
            )
        if _api_contract_boolean_subject_from_ast(subject_path) and matcher in (
            GENERIC_EQUALITY_MATCHERS | GENERIC_SCALAR_MATCHERS
        ):
            return _detail(
                "api_or_data_contract",
                "ast_assertion_subject_path",
                "medium",
                f"subject_path:{'.'.join(subject_path[:8])};matcher:{matcher}",
            )
        if matcher in {"attr", "haveattr", "haveattribute", "tohaveattr", "tohaveattribute"} and (
            _STYLE_RE.search(text_for_context) or _style_subject_from_ast(subject_path)
        ):
            return _detail(
                "style_or_visual_state",
                "ast_assertion_matcher",
                "medium",
                f"matcher:{matcher};style_attribute_context",
            )
        if _accessibility_text_context(text_for_context) and matcher in (
            STATUS_MATCHERS | GENERIC_SCALAR_MATCHERS | {"topass", "tohavecount", "tohavelength"}
        ):
            return _detail(
                "accessibility_compliance",
                "lexical_accessibility_context",
                "medium",
                f"matcher:{matcher};accessibility_context",
            )
        specific_matcher_intent = _specific_semantic_matcher_intent(matcher)
        if specific_matcher_intent:
            return _detail(
                specific_matcher_intent,
                "ast_assertion_semantic_matcher" if semantic_matcher else "ast_assertion_matcher",
                "high",
                f"matcher:{semantic_matcher or feature.get('assertion_matcher') or matcher}",
            )
        if _A11Y_RE.search(text_for_context) and not _collection_subject_from_ast(subject_path, matcher):
            return _detail(
                "accessibility_compliance",
                "lexical_accessibility_context",
                "medium",
                f"matcher:{matcher};accessibility_context",
            )
        if _strong_locator_subject(subject, subject_basis):
            if _presence_matcher(matcher):
                return _detail(
                    "element_presence",
                    "ast_assertion_subject_and_matcher",
                    "high",
                    f"subject:{subject};matcher:{matcher}",
                )
            if _content_matcher(matcher):
                return _detail(
                    "content_correctness",
                    "ast_assertion_subject_and_matcher",
                    "high" if semantic_matcher else "medium",
                    f"subject:{subject};matcher:{matcher}",
                )
        if _interactive_subject_from_ast(subject_path):
            return _detail(
                "interactive_state",
                "ast_assertion_subject_path",
                "medium",
                f"subject_path:{'.'.join(subject_path[:8])};matcher:{matcher}",
            )
        if _style_subject_from_ast(subject_path):
            return _detail(
                "style_or_visual_state",
                "ast_assertion_subject_path",
                "medium",
                f"subject_path:{'.'.join(subject_path[:8])};matcher:{matcher}",
            )
        if _text_subject_from_ast(subject_path):
            return _detail(
                "content_correctness",
                "ast_assertion_subject_path",
                "medium",
                f"subject_path:{'.'.join(subject_path[:8])};matcher:{matcher}",
            )
        if (
            subject in NETWORK_SUBJECTS
            and subject_basis in HEURISTIC_SUBJECT_BASES
            and matcher in {"ok", "toequal", "tobe", "tobetruthy", "betruthy", "true"}
            and re.search(r"\b(?:res|response|apiresponse|httpresponse)\s*\.\s*ok\s*\(", text_for_context)
        ):
            return _detail(
                "api_or_data_contract",
                "lexical_response_ok_contract_context",
                "medium",
                f"subject:{subject};basis:{subject_basis or 'missing'};matcher:{matcher}",
            )
        if subject in NETWORK_SUBJECTS and subject_basis in HEURISTIC_SUBJECT_BASES and matcher in GENERIC_EQUALITY_MATCHERS:
            return _detail(
                "api_or_data_contract",
                "subject_name_heuristic_fallback",
                "medium",
                f"subject:{subject};basis:{subject_basis or 'missing'};matcher:{matcher}",
            )
        if (
            _STATUS_RE.search(text_for_context)
            and matcher in STATUS_MATCHERS
            and not _NAV_RE.search(text_for_context)
        ):
            return _detail(
                "network_contract"
                if (
                    _NETWORK_CONTRACT_CONTEXT_RE.search(text_for_context)
                    or _network_subject_from_ast(subject, subject_basis, subject_path)
                    or _network_alias_wait_context(text_for_context)
                    or re.search(r"\b(?:res|response|request|req|fetch|xhr|httpresponse|apiresponse)\s*\.\s*status", text_for_context)
                )
                else "api_or_data_contract",
                "lexical_api_status_context",
                "medium",
                f"matcher:{matcher};status_context",
            )
        if _API_RESPONSE_VALUE_RE.search(text_for_context) and matcher in AMBIGUOUS_MATCHERS | {"endwith"}:
            intent = "network_contract" if _INTERCEPT_RESPONSE_VALUE_RE.search(text_for_context) else "api_or_data_contract"
            return _detail(
                intent,
                "lexical_api_response_value_context",
                "medium",
                f"matcher:{matcher};api_response_value_context",
            )
        if _NAV_RE.search(text_for_context) and matcher in AMBIGUOUS_MATCHERS:
            return _detail(
                "navigation_outcome",
                "lexical_navigation_context",
                "medium",
                f"matcher:{matcher};navigation_context",
            )
        if (
            _REQUESTED_RESOURCE_RE.search(text_for_context)
            and matcher in AMBIGUOUS_CONTENT_MATCHERS
            and not _strong_locator_subject(subject, subject_basis)
        ):
            return _detail(
                "network_contract",
                "lexical_requested_resource_context",
                "medium",
                f"matcher:{matcher};requested_resource_context",
            )
        if _actual_visual_snapshot_context(text_for_context, matcher):
            return _detail(
                "visual_regression",
                "lexical_visual_context",
                "medium",
                f"matcher:{matcher};visual_context",
            )
        if (
            subject in API_DATA_SUBJECTS
            and subject_basis in STRONG_SUBJECT_BASES
            and _NETWORK_RE.search(text_for_context)
        ):
            if not re.search(r"\b(intercept|route|xhr|network)\b", text_for_context):
                return _detail(
                    "api_or_data_contract",
                    "ast_assertion_subject",
                    "medium",
                    f"subject:{subject};basis:{subject_basis or 'missing'};matcher:{matcher}",
                )
            return _detail(
                "network_contract",
                "ast_assertion_subject_network_context",
                "medium",
                f"subject:{subject};basis:{subject_basis or 'missing'};matcher:{matcher}",
            )
        if (
            subject in API_DATA_SUBJECTS
            and subject_basis in HEURISTIC_SUBJECT_BASES
            and _NETWORK_RE.search(text_for_context)
        ):
            if re.search(r"\b(intercept|route|xhr|network)\b", text_for_context):
                return _detail(
                    "network_contract",
                    "subject_name_heuristic_network_context",
                    "medium",
                    f"subject:{subject};basis:{subject_basis or 'missing'};matcher:{matcher}",
                )
            return _detail(
                "api_or_data_contract",
                "subject_name_heuristic_fallback",
                "medium",
                f"subject:{subject};basis:{subject_basis or 'missing'};matcher:{matcher}",
            )
        if (
            subject in API_DATA_SUBJECTS
            and subject_basis in STRONG_SUBJECT_BASES
            and (matcher in GENERIC_EQUALITY_MATCHERS or oracle_mapped == "api_or_data_contract")
        ):
            return _detail(
                "api_or_data_contract",
                "ast_assertion_subject",
                "medium",
                f"subject:{subject};basis:{subject_basis};matcher:{matcher}",
            )
        if (
            subject in API_DATA_SUBJECTS
            and subject_basis in HEURISTIC_SUBJECT_BASES
            and (matcher in GENERIC_EQUALITY_MATCHERS or oracle_mapped == "api_or_data_contract")
        ):
            return _detail(
                "api_or_data_contract",
                "subject_name_heuristic_fallback",
                "medium",
                f"subject:{subject};basis:{subject_basis or 'missing'};matcher:{matcher}",
            )
        if _TEXT_VALUE_CONTEXT_RE.search(text_for_context) and matcher in GENERIC_EQUALITY_MATCHERS:
            return _detail(
                "content_correctness",
                "lexical_text_property_context",
                "medium",
                f"matcher:{matcher};text_property_context",
            )
        if _ATTRIBUTE_CONTEXT_RE.search(text_for_context) and matcher in AMBIGUOUS_MATCHERS:
            return _detail(
                "value_or_attribute_correctness",
                "lexical_attribute_context",
                "medium",
                f"matcher:{matcher};attribute_context",
            )
        if _PRESENCE_PROPERTY_RE.search(text_for_context) and matcher in (GENERIC_EQUALITY_MATCHERS | {"notok"}):
            return _detail(
                "element_presence",
                "lexical_presence_property_context",
                "medium",
                f"matcher:{matcher};presence_property",
            )
        if (_STYLE_RE.search(text_for_context) or _LAYOUT_MEASUREMENT_RE.search(text_for_context)) and matcher in (
            STATUS_MATCHERS | {"above", "greaterthan", "gt", "least", "lessthan", "lt", "gte", "lte", "closeto", "tobecloseto"}
        ):
            return _detail(
                "style_or_visual_state",
                "lexical_style_context",
                "medium",
                f"matcher:{matcher};style_context",
            )
        if (
            oracle_mapped == "navigation_outcome"
            and matcher in AMBIGUOUS_MATCHERS
            and (
                subject in PAGE_NAVIGATION_SUBJECTS
                and subject_basis in (STRONG_NAVIGATION_SUBJECT_BASES | HEURISTIC_SUBJECT_BASES)
                or not subject
                or subject == "unknown"
            )
        ):
            return _detail(
                "navigation_outcome",
                "lexical_oracle_category_fallback",
                "medium",
                f"{oracle_category};matcher:{matcher};subject:{subject or 'unknown'}",
            )
        if _HTML_CONTENT_RE.search(text_for_context):
            return _detail(
                "content_correctness",
                "lexical_html_content_context",
                "medium",
                f"matcher:{matcher};html_content_context",
            )
        if oracle_mapped != "unspecified" and matcher in AMBIGUOUS_MATCHERS:
            return _detail(
                oracle_mapped,
                "lexical_oracle_category_fallback",
                "medium",
                oracle_category,
            )
        if matcher in MATCHER_TO_VERIFICATION_INTENT:
            confidence = "medium" if matcher in GENERIC_EQUALITY_MATCHERS else "high"
            return _detail(
                MATCHER_TO_VERIFICATION_INTENT[matcher],
                "ast_assertion_semantic_matcher" if semantic_matcher else "ast_assertion_matcher",
                confidence,
                f"matcher:{semantic_matcher or feature.get('assertion_matcher') or matcher}",
            )
        if matcher in ("toequal", "tostrictequal", "equal", "eql"):
            if oracle_mapped != "unspecified":
                return _detail(
                    oracle_mapped,
                    "lexical_oracle_category_fallback",
                    "medium",
                    oracle_category,
                )
            if subject in API_DATA_SUBJECTS and subject_basis in STRONG_SUBJECT_BASES:
                return _detail(
                    "api_or_data_contract",
                    "ast_assertion_subject",
                    "medium",
                    f"subject:{subject};basis:{subject_basis}",
                )
            if subject in API_DATA_SUBJECTS and subject_basis in HEURISTIC_SUBJECT_BASES:
                return _detail(
                    "api_or_data_contract",
                    "subject_name_heuristic_fallback",
                    "medium",
                    f"subject:{subject};basis:{subject_basis or 'missing'}",
                )
        if matcher in {"should", "and"} and not semantic_matcher:
            mapped = _classify_verification_intent_lexical(oracle_category, name, raw, feature)
            if mapped != "unspecified":
                return _detail(mapped, "lexical_fallback", "medium", "nested_callback_or_raw_assertion")
            if re.search(r"\bexpect\s*\(", raw or "", re.IGNORECASE):
                return _detail(
                    "value_or_attribute_correctness",
                    "lexical_fallback",
                    "low",
                    "nested_callback_assertion_untyped",
                )
            if re.search(r"\b(?:should|and)\s*\(\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>|\bfunction\s*\(", raw or "", re.IGNORECASE):
                return _detail(
                    "value_or_attribute_correctness",
                    "lexical_fallback",
                    "low",
                    "cypress_callback_assertion_untyped",
                )
            if subject in ("locator", "element", "unknown", "") and re.search(r"\b(?:should|and)\s*\(", raw or "", re.IGNORECASE):
                return _detail(
                    "value_or_attribute_correctness",
                    "lexical_fallback",
                    "low",
                    "cypress_dynamic_predicate_assertion",
                )
        if oracle_mapped != "unspecified":
            return _detail(
                oracle_mapped,
                "lexical_oracle_category_fallback",
                "medium",
                oracle_category,
            )
        return _detail("unspecified", "ast_assertion_matcher_unmapped", "low", f"matcher:{matcher}")

    mapped = _classify_verification_intent_lexical(oracle_category, name, raw, feature)
    if mapped != "unspecified" and mapped != oracle_mapped:
        return _detail(mapped, "lexical_fallback", "medium", "name_raw_match")
    if oracle_mapped != "unspecified":
        return _detail(
            oracle_mapped,
            "lexical_oracle_category_fallback",
            "medium",
            oracle_category,
        )
    if mapped != "unspecified":
        return _detail(mapped, "lexical_fallback", "medium", "name_raw_match")
    return _detail("unspecified", "lexical_oracle_category_fallback", "low", oracle_category)


_VALUE_ATTR_RE = re.compile(
    r"\b(tohavevalue|tohaveid|have\.value|value|tohaveattribute|have\.attr|attr|attribute|prop(?:erty)?|"
    r"tohaveproperty|haveownproperty|tohavejsproperty|tohavecustomstate|customstate|"
    r"tohavereceivedevent(?:detail)?|receivedevent(?:detail)?|"
    r"tobedefined|tobeundefined|tobeempty|tobeemptystring|"
    r"tobetruthy|tobefalsy|truthy|falsy|defined|undefined|null|empty|"
    r"toequal|tostrictequal|toeq|equal|equals|isequal|eqls?|eq|not\.eq|match|tomatch|tomatchobject|topass|"
    r"satisfy|instanceof|tobeinstanceof|isboolean|be\.a|be\.an|any\.keys|have\.any\.keys|"
    r"greaterthan|lessthan|tobegreaterthan(?:orequal)?|tobelessthan(?:orequal)?|"
    r"at\.least|at\.most|isatmost|\b(?:gt|gte|lt|lte)\b|closeTo|closeto|tobecloseto|approximately|oneof|throw)\b",
    re.IGNORECASE,
)
_STYLE_RE = re.compile(
    r"\b(tohavecss|tohaveclass|have\.css|have\.class|css|class|style|computedstyle|"
    r"font[-_]?size|color|width|height|layout|boundingbox|offsetwidth|offsetheight|clientwidth|clientheight)\b",
    re.IGNORECASE,
)
_PRESENCE_RE = re.compile(
    r"\b(tobevisible|tobehidden|should\s*\(\s*['\"](?:be\.)?(?:visible|hidden)|"
    r"should\s*\(\s*['\"](?:not\.)?(?:be\.)?exist|not\.toexist|toexist|"
    r"tobeattached|tobeinthedocument|tobeinviewport|attached|inviewport|exists?|present)\b",
    re.IGNORECASE,
)
_INTERACTIVE_RE = re.compile(
    r"\b(tobeenabled|tobedisabled|tobechecked|tobefocused|tobeeditable|focused|focus|editable|"
    r"enabled|disabled|checked|unchecked|selected)\b",
    re.IGNORECASE,
)
_CONTENT_RE = re.compile(
    r"\b(tohavetext|tocontaintext|tohavetitle|have\.text|have\.title|contain\.text|document\.title|pagetitle|"
    r"textcontent|innertext|gettext|innerhtml|outerhtml|gethtml|html\(\)|have\.html|have\.string|"
    r"contains?text|contains?|includes?)\b",
    re.IGNORECASE,
)
_HTML_CONTENT_RE = re.compile(r"\b(innerhtml|outerhtml|gethtml|html\(\)|htmlcontent|markup)\b", re.IGNORECASE)
_NAV_RE = re.compile(
    r"\b(tohaveurl|url|currenturl|iframesrc|urlpattern|pathname|location|href)\b|forurl\b",
    re.IGNORECASE,
)
_NETWORK_RE = re.compile(
    r"\b(response|status|headers?|intercept|route|request|apiresponse|httpresponse|fetch|xhr|network)\b",
    re.IGNORECASE,
)
_NETWORK_CONTRACT_CONTEXT_RE = re.compile(
    r"\b(intercept|route|xhr|fetch|network)\b",
    re.IGNORECASE,
)
_API_RESPONSE_VALUE_RE = re.compile(
    r"\b(?:intercept|response|res|apiresponse|httpresponse|request|req|fetch|xhr)\b[^;\n]*(?:\bbody\b|\.body|\.json|\.data)",
    re.IGNORECASE,
)
_INTERCEPT_RESPONSE_VALUE_RE = re.compile(
    r"\b(?:intercept|xhr|network|request|response)\b[^;\n]*(?:\bbody\b|\.body|\.json|\.data)",
    re.IGNORECASE,
)
_STATUS_RE = re.compile(
    r"(?:\b(?:response|res|apiresponse|httpresponse|request|req|fetch|xhr)\s*\.\s*status(?:code)?\b|"
    r"\bstatus(?:code)?\b)",
    re.IGNORECASE,
)
_ATTRIBUTE_CONTEXT_RE = re.compile(
    r"\b(?:attr(?:ibute)?|prop(?:erty)?|jsproperty|data-|aria-|id|name|value)\b|"
    r"\b(?:have\.attr|have\.prop|tohaveattribute|tohavejsproperty|tohaveid|tohavevalue)\b",
    re.IGNORECASE,
)
_TEXT_VALUE_CONTEXT_RE = re.compile(r"\b(?:textcontent|innertext|gettext|labeltext|titletext)\b", re.IGNORECASE)
_LAYOUT_MEASUREMENT_RE = re.compile(
    r"\b(?:scroll(?:top|left|height|width)?[A-Za-z0-9_$]*|"
    r"client(?:height|width)[A-Za-z0-9_$]*|offset(?:height|width)[A-Za-z0-9_$]*|"
    r"content(?:height|width)[A-Za-z0-9_$]*|viewport(?:height|width)[A-Za-z0-9_$]*|"
    r"boundingbox|height|width)\b",
    re.IGNORECASE,
)
_EVENT_DETAIL_RE = re.compile(
    r"\b(?:stub|firstcall|lastcall|args|event\.detail|\.detail\b|receivedevent)\b",
    re.IGNORECASE,
)
_REQUESTED_RESOURCE_RE = re.compile(
    r"\b(?:requested|request|response|api|asset|image|script|stylesheet|font|resource)[A-Za-z0-9_$]*(?:path|url|src|href|name)\b",
    re.IGNORECASE,
)
_FILTERED_COLLECTION_RE = re.compile(
    r"(?:\bfilter\s*\(|\.filter\s*\(|\[[^\]]*\]\s*\.filter\s*\(|"
    r"\b(?:errors?|items?|rows?|results?|matches?)\s*\.filter\s*\()",
    re.IGNORECASE,
)
_CALL_SPY_RE = re.compile(
    r"\b(spy|stub|mock|sinon|firstcall|lastcall|called\w*|notcalled|tohavebeencalled\w*)\b",
    re.IGNORECASE,
)
_NETWORK_SPY_CONTEXT_RE = re.compile(
    r"((response|request|intercept|route|api|http|fetch|xhr|network)[A-Za-z0-9_$]*spy|"
    r"spy[A-Za-z0-9_$]*(response|request|intercept|route|api|http|fetch|xhr|network))",
    re.IGNORECASE,
)
_API_DATA_RE = re.compile(r"\b(body|payload|json|graphql|api|contract|schema)\b", re.IGNORECASE)
_LENGTH_RE = re.compile(
    r"\b(length|count|size|tohavelength|tohavecount|have\.length|have\.count|calledtimes|callcount|"
    r"tohavebeencalledtimes|tohavereceivedeventtimes|receivedeventtimes)\b",
    re.IGNORECASE,
)
_VISUAL_RE = re.compile(r"\b(snapshot|screenshot|visual|image|diff|tomatchscreenshot|tohavescreenshot)\b", re.IGNORECASE)
_VISUAL_SNAPSHOT_RE = re.compile(
    r"\b(snapshot|screenshot|tomatchscreenshot|tohavescreenshot|tomatchsnapshot)\b",
    re.IGNORECASE,
)
_A11Y_RE = re.compile(
    r"\b(accessibility|a11y|axe|violations?|aria[A-Z_a-z0-9]*|aria|"
    r"accessible(?:name|description|error|errormessage)?|"
    r"tohaveaccessible(?:name|description|error|errormessage)|tohaverole|"
    r"tomatchariasnapshot|matchariasnapshot|have\.role|tohavenoviolations)\b",
    re.IGNORECASE,
)
_PRESENCE_PROPERTY_RE = re.compile(r"(?:^|[.\s])(exists?|ispresent|present)(?:\b|\s*\))", re.IGNORECASE)


def classify_verification_intent(
    oracle_category: str,
    name: str = "",
    raw: str = "",
    feature: Dict[str, Any] | None = None,
) -> str:
    return classify_verification_intent_detail(oracle_category, name, raw, feature)["verification_intent"]


def _classify_verification_intent_lexical(
    oracle_category: str,
    name: str = "",
    raw: str = "",
    feature: Dict[str, Any] | None = None,
) -> str:
    """Map an assertion to a coarse verification intent.

    The lexical layer only assigns broad observable oracle types; it avoids
    inferring high-level behavioral concerns such as login success.
    """
    feature = feature or {}
    matcher = str(feature.get("assertion_matcher") or "")
    subject = str(feature.get("assertion_subject_kind") or "").lower()
    text = f"{name} {raw} {matcher}".lower()
    normalized_text = _normalize_matcher(text)

    if re.search(r"\b(?:tohavereceivedeventtimes|receivedeventtimes)\b", text, re.IGNORECASE):
        return "interactive_state"
    if re.search(r"\b(?:tohavebeencalledtimes|calledtimes|callcount|have\.callcount)\b", text, re.IGNORECASE):
        return "interactive_state"
    if _actual_visual_snapshot_context(text, matcher):
        return "visual_regression"
    if "includemembers" in normalized_text or "havemembers" in normalized_text:
        return "api_or_data_contract"
    if _network_request_or_response_context(text) or _http_status_scalar_context(_subject_path(feature), text):
        return "network_contract"
    if _interactive_event_or_spy_context(_subject_path(feature), text, _matcher_lookup_key(_normalize_matcher(matcher))):
        return "interactive_state"
    if _presence_visibility_text_context(text):
        return "element_presence"
    if _object_or_result_contract_context(_subject_path(feature), text, _matcher_lookup_key(_normalize_matcher(matcher))):
        return "api_or_data_contract"
    if _text_payload_context(text):
        return "content_correctness"
    if _style_property_context(text):
        return "style_or_visual_state"
    if _api_config_boolean_text_context(text):
        return "api_or_data_contract"
    if _network_alias_wait_context(text):
        return "network_contract"
    if _accessibility_text_context(text) and re.search(r"\b(?:topass|focusable|focusindicators?)\b", text, re.I):
        return "accessibility_compliance"
    if _FILTERED_COLLECTION_RE.search(text) or _LENGTH_RE.search(text):
        return "collection_size"
    if _A11Y_RE.search(text):
        return "accessibility_compliance"
    if _EVENT_DETAIL_RE.search(text) and _event_or_spy_contract_context(text, _normalize_matcher(matcher)):
        return "api_or_data_contract"
    if _API_RESPONSE_VALUE_RE.search(text):
        if _INTERCEPT_RESPONSE_VALUE_RE.search(text):
            return "network_contract"
        return "api_or_data_contract"
    if _STATUS_RE.search(text):
        if re.search(r"\b(?:res|response|request|req|fetch|xhr|httpresponse|apiresponse)\s*\.\s*status", text, re.I):
            return "network_contract"
        return "api_or_data_contract"
    if _STYLE_RE.search(text) or _LAYOUT_MEASUREMENT_RE.search(text):
        return "style_or_visual_state"
    if _TEXT_VALUE_CONTEXT_RE.search(text):
        return "content_correctness"
    if _ATTRIBUTE_CONTEXT_RE.search(text):
        return "value_or_attribute_correctness"
    if _REQUESTED_RESOURCE_RE.search(text):
        return "network_contract"
    if _NAV_RE.search(text):
        return "navigation_outcome"
    if _HTML_CONTENT_RE.search(text):
        return "content_correctness"
    if _CONTENT_RE.search(text):
        return "content_correctness"
    if _actual_visual_snapshot_context(text, matcher):
        return "visual_regression"
    if _PRESENCE_PROPERTY_RE.search(text):
        return "element_presence"
    if _API_DATA_RE.search(text):
        return "api_or_data_contract"
    if _VALUE_ATTR_RE.search(text):
        return "value_or_attribute_correctness"
    if _INTERACTIVE_RE.search(text):
        return "interactive_state"
    if _PRESENCE_RE.search(text) and subject in ("", "locator", "element", "unknown"):
        return "element_presence"
    if _NETWORK_RE.search(text):
        if re.search(r"\b(intercept|route|xhr|network|request)\b", text):
            return "network_contract"
        return "api_or_data_contract"
    if _CALL_SPY_RE.search(text):
        if _NETWORK_SPY_CONTEXT_RE.search(text) or subject in ("response", "request", "api", "network"):
            return "network_contract"
        return "api_or_data_contract"
    if re.search(r"\b(?:should|and)\s*\(", text, re.IGNORECASE):
        return "value_or_attribute_correctness"
    return map_verification_intent(oracle_category)
