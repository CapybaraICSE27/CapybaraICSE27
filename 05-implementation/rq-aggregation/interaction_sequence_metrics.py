"""RQ4-A v1: sequence repetition metrics from ordered UI action events (Milestone 1)."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

# Events with missing/invalid line numbers sort after known-line events.
_MISSING_LINE_SORT_KEY = 10**9

_HTTP_METHODS = frozenset({
    "GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "TRACE", "CONNECT",
})
_NAVIGATION_METHODS = frozenset({
    "goto",
    "visit",
    "url",
    "navigateto",
    "navigate",
    "open",
    "loadurl",
})

# User-interaction categories for workflow repetition (excludes locator_query).
USER_ACTION_CATEGORIES = frozenset({
    "click",
    "text_input",
    "keyboard_input",
    "navigation",
    "selection",
    "hover",
    "drag_drop",
    "file_upload",
    "scroll",
    "wait_synchronization",
    "visual_action",
    "unknown_action",
})

# Paper-facing classified user actions exclude locator-only queries, explicit
# synchronization calls, and unclassified script/execution events.
CLASSIFIED_USER_ACTION_CATEGORIES = USER_ACTION_CATEGORIES - frozenset({
    "wait_synchronization",
    "unknown_action",
})


def normalize_action_signature(category: str, name: str) -> str:
    """v1 signature: interaction category + normalized callee/name token."""
    cat = (category or "unknown_action").strip().lower()
    n = " ".join((name or "").strip().lower().split())
    return f"{cat}|{n}" if n else cat


def navigation_api_signature_from_event(event: Dict[str, Any]) -> str:
    """Target-insensitive navigation API signature (v2 category+terminal_action, else v1)."""
    raw_json = str(event.get("action_signature_json") or "").strip()
    if raw_json:
        try:
            payload = json.loads(raw_json)
            if int(payload.get("v") or 0) >= 2:
                parts = [
                    payload.get("category", ""),
                    payload.get("terminal_action", ""),
                ]
                sig = "|".join(str(p).strip().lower() for p in parts if str(p).strip())
                if sig:
                    return sig
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    return normalize_action_signature(
        str(event.get("category") or ""),
        str(event.get("name") or ""),
    )


def action_signature_from_event(event: Dict[str, Any]) -> str:
    """Prefer action_signature_json v2 when present; fall back to v1."""
    raw_json = str(event.get("action_signature_json") or "").strip()
    if raw_json:
        try:
            payload = json.loads(raw_json)
            if int(payload.get("v") or 0) >= 2:
                parts = [
                    payload.get("category", ""),
                    payload.get("terminal_action", ""),
                    payload.get("locator_strategy", ""),
                    payload.get("input_channel", ""),
                    payload.get("navigation_target", ""),
                ]
                sig = "|".join(str(p).strip().lower() for p in parts if str(p).strip())
                if sig:
                    return sig
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    return normalize_action_signature(
        str(event.get("category") or ""),
        str(event.get("name") or ""),
    )


def is_user_action_category(category: str) -> bool:
    return (category or "").strip().lower() in USER_ACTION_CATEGORIES


def is_classified_user_action_category(category: str) -> bool:
    return (category or "").strip().lower() in CLASSIFIED_USER_ACTION_CATEGORIES


def _is_http_method_literal(target: str) -> bool:
    token = (target or "").strip()
    if not token:
        return False
    return token.upper() in _HTTP_METHODS


def extract_navigation_target(raw_code: str, name: str = "") -> str:
    """
    Extract a static URL/path literal from a recognized navigation call (v1).

    Literal-only approximation: parses recognized navigation call arguments and
    rejects HTTP method literals, concatenation, variables, object-literal URLs,
    and dynamic template literals (${...}). Prefer AST-extracted navigation args
    in Phase 2B (Milestone 3).

    Returns target with original casing, or empty string when not extractable.
    """
    target, _basis = resolve_navigation_target_fields(raw_code, name)
    return target


def resolve_navigation_target_fields(raw_code: str, name: str = "") -> tuple[str, str]:
    """
    Return (navigation_target, navigation_target_evidence_basis) for audit CSVs.

    evidence_basis:
      navigation_api_literal_arg - static quoted route literal from a recognized navigation call
      dynamic_template_literal - template literal contains ${...}
      http_method_literal - quoted token is an HTTP verb (e.g. POST), not a route
      not_extractable - no usable quoted literal found
    """
    text = (raw_code or name or "").strip()
    if not text:
        return "", "not_extractable"
    arg = _first_navigation_call_arg(text)
    if arg is None:
        return "", "not_extractable"
    literal = _static_string_literal_value(arg)
    if literal is None:
        return "", "not_extractable"
    target, is_template = literal
    if is_template and "${" in target:
        return "", "dynamic_template_literal"
    if not target:
        return "", "not_extractable"
    if _is_http_method_literal(target):
        return "", "http_method_literal"
    return target, "navigation_api_literal_arg"


def _first_navigation_call_arg(text: str) -> Optional[str]:
    for open_idx, callee in _iter_call_openings(text):
        terminal = callee.rsplit(".", 1)[-1].lower()
        if terminal not in _NAVIGATION_METHODS:
            continue
        close_idx = _matching_close_paren(text, open_idx)
        if close_idx < 0:
            return None
        args = _split_top_level_args(text[open_idx + 1 : close_idx])
        return args[0].strip() if args else ""
    return None


def _iter_call_openings(text: str):
    for idx, ch in enumerate(text):
        if ch != "(":
            continue
        j = idx - 1
        while j >= 0 and text[j].isspace():
            j -= 1
        end = j + 1
        while j >= 0 and (text[j].isalnum() or text[j] in "_.$"):
            j -= 1
        callee = text[j + 1 : end].strip(".")
        if callee:
            yield idx, callee


def _matching_close_paren(text: str, open_idx: int) -> int:
    depth = 0
    quote = ""
    escape = False
    for idx in range(open_idx, len(text)):
        ch = text[idx]
        if quote:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == quote:
                quote = ""
            continue
        if ch in ("'", '"', "`"):
            quote = ch
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return idx
    return -1


def _split_top_level_args(args: str) -> List[str]:
    out: List[str] = []
    start = 0
    depth = 0
    quote = ""
    escape = False
    for idx, ch in enumerate(args):
        if quote:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == quote:
                quote = ""
            continue
        if ch in ("'", '"', "`"):
            quote = ch
            continue
        if ch in "([{":
            depth += 1
        elif ch in ")]}" and depth > 0:
            depth -= 1
        elif ch == "," and depth == 0:
            out.append(args[start:idx])
            start = idx + 1
    tail = args[start:]
    if tail.strip() or args.strip():
        out.append(tail)
    return out


def _static_string_literal_value(arg: str) -> Optional[Tuple[str, bool]]:
    a = (arg or "").strip()
    if len(a) < 2:
        return None
    quote = a[0]
    if quote not in ("'", '"', "`"):
        return None
    if a[-1] != quote:
        return None
    return a[1:-1].strip(), quote == "`"


def navigation_target_signature(category: str, name: str, navigation_target: str) -> str:
    """Signature for URL/view revisit detection when a static literal target is known."""
    target = (navigation_target or "").strip()
    if target:
        return f"navigation_target|{target}"
    return normalize_action_signature(category, name)


def _parse_line_sort_key(line: Any) -> int:
    try:
        val = int(line)
    except (TypeError, ValueError):
        return _MISSING_LINE_SORT_KEY
    return val if val > 0 else _MISSING_LINE_SORT_KEY


def _sorted_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Order by source line, then ingestion order. Never sort by name."""
    return sorted(
        events,
        key=lambda e: (
            _parse_line_sort_key(e.get("line")),
            int(e.get("_ingest_index") or 0),
        ),
    )


def _consecutive_runs(signatures: List[str]) -> List[Tuple[str, int]]:
    if not signatures:
        return []
    runs: List[Tuple[str, int]] = []
    cur_sig = signatures[0]
    cur_len = 1
    for sig in signatures[1:]:
        if sig == cur_sig:
            cur_len += 1
        else:
            runs.append((cur_sig, cur_len))
            cur_sig = sig
            cur_len = 1
    runs.append((cur_sig, cur_len))
    return runs


def _repeat_fields_from_signatures(signatures: List[str]) -> Dict[str, Any]:
    n = len(signatures)
    if n == 0:
        return {
            "repeat_fraction": "",
            "max_consecutive_identical_action": 0,
            "top_repeated_action_signature": "",
        }
    runs = _consecutive_runs(signatures)
    max_run = max(length for _, length in runs)
    repeated_events = sum(length for _, length in runs if length >= 2)
    repeat_fraction = round(repeated_events / n, 6)

    top_sig = ""
    top_len = 0
    for sig, length in runs:
        if length >= 2 and length > top_len:
            top_len = length
            top_sig = sig

    return {
        "repeat_fraction": repeat_fraction,
        "max_consecutive_identical_action": max_run,
        "top_repeated_action_signature": top_sig,
    }


def _empty_metrics(prefix: str = "") -> Dict[str, Any]:
    p = prefix
    return {
        f"{p}sequence_event_count": 0,
        f"{p}unique_action_signature_count": 0,
        f"{p}repeat_action_fraction": "",
        f"{p}max_consecutive_identical_action": 0,
        f"{p}repeated_navigation_api_count": 0,
        f"{p}navigation_target_revisit_count": 0,
        f"{p}top_repeated_action_signature": "",
        f"{p}unique_action_signature_v2_count": 0,
        f"{p}sequence_signature_version_mixed": 0,
        f"{p}sequence_signature_version": "",
        f"{p}user_action_event_count": 0,
        f"{p}user_action_repeat_fraction": "",
        f"{p}user_action_max_consecutive_identical_action": 0,
        f"{p}classified_user_action_event_count": 0,
        f"{p}classified_user_action_repeat_fraction": "",
        f"{p}classified_user_action_max_consecutive_identical_action": 0,
    }


def compute_sequence_metrics(
    events: List[Dict[str, Any]],
    *,
    column_prefix: str = "",
) -> Dict[str, Any]:
    """
    Compute per-test sequence repetition metrics from UI action events.

    repeat_action_fraction counts repeated UI-test event signatures (includes
    locator_query). user_action_repeat_fraction excludes locator_query but keeps
    synchronization/unknown events for backward compatibility.
    classified_user_action_repeat_fraction uses the paper-facing classified
    user-action denominator.

    Each event should include:
      line, category, name, _ingest_index
    Navigation events may include navigation_target (from extract_navigation_target).
    """
    prefix = column_prefix
    ordered = _sorted_events(events)
    n = len(ordered)
    if n == 0:
        return _empty_metrics(prefix)

    signatures = [action_signature_from_event(e) for e in ordered]
    repeat_fields = _repeat_fields_from_signatures(signatures)
    v2_events = [e for e in ordered if str(e.get("action_signature_json") or "").strip()]
    v2_signatures = [action_signature_from_event(e) for e in v2_events]
    has_v2 = bool(v2_events)
    mixed_v2 = has_v2 and len(v2_events) < len(ordered)

    user_ordered = [e for e in ordered if is_user_action_category(str(e.get("category") or ""))]
    user_signatures = [action_signature_from_event(e) for e in user_ordered]
    user_repeat_fields = _repeat_fields_from_signatures(user_signatures)
    classified_user_ordered = [
        e for e in ordered if is_classified_user_action_category(str(e.get("category") or ""))
    ]
    classified_user_signatures = [action_signature_from_event(e) for e in classified_user_ordered]
    classified_user_repeat_fields = _repeat_fields_from_signatures(classified_user_signatures)

    api_sigs_seen: set[str] = set()
    repeated_nav_api = 0
    target_sigs_seen: set[str] = set()
    target_revisits = 0

    for e in ordered:
        if (e.get("category") or "").strip().lower() != "navigation":
            continue
        api_sig = navigation_api_signature_from_event(e)
        if api_sig in api_sigs_seen:
            repeated_nav_api += 1
        else:
            api_sigs_seen.add(api_sig)

        nav_target = str(e.get("navigation_target") or "").strip()
        nav_basis = str(e.get("navigation_target_evidence_basis") or "").strip()
        if not nav_target:
            nav_target, nav_basis = resolve_navigation_target_fields(
                str(e.get("raw_code") or ""),
                str(e.get("name") or ""),
            )
        if nav_basis in ("dynamic_template_literal", "http_method_literal"):
            continue
        target_sig = navigation_target_signature(
            str(e.get("category") or ""),
            str(e.get("name") or ""),
            nav_target,
        )
        if nav_target:
            if target_sig in target_sigs_seen:
                target_revisits += 1
            else:
                target_sigs_seen.add(target_sig)

    return {
        f"{prefix}sequence_event_count": n,
        f"{prefix}unique_action_signature_count": len(set(signatures)),
        f"{prefix}repeat_action_fraction": repeat_fields["repeat_fraction"],
        f"{prefix}max_consecutive_identical_action": repeat_fields["max_consecutive_identical_action"],
        f"{prefix}repeated_navigation_api_count": repeated_nav_api,
        f"{prefix}navigation_target_revisit_count": target_revisits,
        f"{prefix}top_repeated_action_signature": repeat_fields["top_repeated_action_signature"],
        f"{prefix}unique_action_signature_v2_count": len(set(v2_signatures)),
        f"{prefix}sequence_signature_version": "v2" if has_v2 and not mixed_v2 else ("mixed" if mixed_v2 else "v1"),
        f"{prefix}sequence_signature_version_mixed": 1 if mixed_v2 else 0,
        f"{prefix}user_action_event_count": len(user_ordered),
        f"{prefix}user_action_repeat_fraction": user_repeat_fields["repeat_fraction"]
        if user_ordered
        else "",
        f"{prefix}user_action_max_consecutive_identical_action": user_repeat_fields[
            "max_consecutive_identical_action"
        ],
        f"{prefix}classified_user_action_event_count": len(classified_user_ordered),
        f"{prefix}classified_user_action_repeat_fraction": classified_user_repeat_fields[
            "repeat_fraction"
        ]
        if classified_user_ordered
        else "",
        f"{prefix}classified_user_action_max_consecutive_identical_action": classified_user_repeat_fields[
            "max_consecutive_identical_action"
        ],
    }


def compute_dual_scope_sequence_metrics(
    all_layer_events: List[Dict[str, Any]],
    test_body_events: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    All-layer metrics (approximate order when helpers expanded) + test-body-only metrics.

    For paper claims, prefer test_body_* columns; all-layer metrics are secondary when
    sequence_all_layers_includes_non_test_body_events=1.
    """
    metrics = compute_sequence_metrics(all_layer_events, column_prefix="")
    metrics.update(
        compute_sequence_metrics(test_body_events, column_prefix="test_body_")
    )
    includes_non_test_body = len(all_layer_events) != len(test_body_events)
    metrics["sequence_all_layers_includes_non_test_body_events"] = (
        1 if includes_non_test_body else 0
    )
    metrics["sequence_scope_all_layers_approximate"] = 1 if includes_non_test_body else 0
    return metrics
