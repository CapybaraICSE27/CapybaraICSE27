"""RQ6 source-review semantic enrichment for agent prompts."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Sequence


GENERIC_ASSERTION_INTENTS = {
    "expected browser or ui behavior occurs",
    "the expected observable behavior occurs",
    "observable assertion",
    "generic assertion",
    "unspecified",
}

SAFE_COMMON_CALL_NAMES = {
    "click",
    "describe",
    "expect",
    "fill",
    "filter",
    "first",
    "goto",
    "hover",
    "last",
    "not",
    "nth",
    "on",
    "page",
    "poll",
    "push",
    "test",
    "toBe",
    "toBeAttached",
    "toBeTruthy",
    "toBeVisible",
    "toContain",
    "toContainText",
    "toEqual",
    "toHaveAttribute",
    "toHaveClass",
    "toHaveText",
    "toMatch",
    "toStrictEqual",
    "window",
}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def humanize_identifier(value: str) -> str:
    text = str(value or "")
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    text = text.replace("_", " ").replace("-", " ").replace(".", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def deidentify_path_hint(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return "the relevant application view"
    if text in {"/", "#"}:
        return "the starting application view"
    parts = [p for p in re.split(r"[/?#&=._-]+", text) if p and not p.isdigit()]
    if not parts:
        return "the relevant application route"
    return "the " + " ".join(parts[:4]) + " view"


def strip_numbered_snippet(snippet: str) -> str:
    lines: List[str] = []
    for line in str(snippet or "").splitlines():
        if ": " in line:
            prefix, rest = line.split(": ", 1)
            if prefix.strip().isdigit():
                lines.append(rest)
                continue
        lines.append(line)
    return "\n".join(lines)


def first_literal_arg(call_name: str, code: str) -> str:
    pattern = re.compile(rf"{re.escape(call_name)}\s*\(\s*(['\"])(.*?)\1", re.DOTALL)
    match = pattern.search(code)
    return match.group(2) if match else ""


def source_action(
    action_type: str,
    target_hint: str,
    *,
    basis: str,
    source_layer: str = "source_review",
) -> Dict[str, Any]:
    return {
        "type": action_type,
        "target_hint": target_hint,
        "source_layer": source_layer,
        "helper_depth": 0,
        "evidence_basis": basis,
    }


def source_assertion(kind: str, intent: str, *, basis: str) -> Dict[str, Any]:
    return {
        "kind": kind,
        "intent": intent,
        "source_layer": "source_review",
        "helper_depth": 0,
        "evidence_basis": basis,
    }


def append_unique(items: List[Dict[str, Any]], item: Dict[str, Any], keys: Sequence[str] = ("type", "target_hint")) -> None:
    identity = tuple(str(item.get(key) or "") for key in keys)
    for existing in items:
        if tuple(str(existing.get(key) or "") for key in keys) == identity:
            return
    item = dict(item)
    item["index"] = len(items) + 1
    items.append(item)


def _extract_call_names(code: str) -> List[str]:
    names: List[str] = []
    seen: set[str] = set()
    masked = re.sub(r"""(?P<quote>['"`])(?:\\.|(?!\1).)*?(?P=quote)""", "''", code, flags=re.DOTALL)
    for pattern in [r"\b([A-Za-z_$][\w$]*)\s*\(", r"\.([A-Za-z_$][\w$]*)\s*\("]:
        for match in re.finditer(pattern, masked):
            name = match.group(1)
            if name in seen or name in SAFE_COMMON_CALL_NAMES:
                continue
            if name and (re.search(r"[a-z][A-Z]|[_$]", name) or name in {"exposeBinding", "addEventListener"}):
                seen.add(name)
                names.append(name)
    return names


def _append_text_item(items: List[Dict[str, Any]], text: str, *, basis: str, confidence: str, **extra: Any) -> None:
    text = _clean(text)
    if not text:
        return
    if any(existing.get("text") == text for existing in items):
        return
    item = {
        "text": text,
        "evidence_basis": basis,
        "confidence": confidence,
    }
    item.update(extra)
    items.append(item)


def _append_expected_result(
    items: List[Dict[str, Any]],
    outcome: str,
    *,
    channel: str,
    basis: str,
    confidence: str,
) -> None:
    outcome = _clean(outcome)
    if not outcome:
        return
    if any(existing.get("observable_outcome") == outcome for existing in items):
        return
    items.append(
        {
            "observable_outcome": outcome,
            "observation_channel": channel,
            "evidence_basis": basis,
            "confidence": confidence,
        }
    )


def _is_generic_assertion(assertion: Dict[str, Any]) -> bool:
    intent = _clean(assertion.get("intent")).lower()
    kind = _clean(assertion.get("kind")).lower()
    return intent in GENERIC_ASSERTION_INTENTS or kind in GENERIC_ASSERTION_INTENTS


def _semantic_confidence(expected_results: Sequence[Dict[str, Any]], workflow_steps: Sequence[Dict[str, Any]]) -> str:
    if not expected_results:
        return "low"
    expected_confidences = {
        _clean(item.get("confidence")).lower()
        for item in expected_results
        if _clean(item.get("confidence"))
    }
    if expected_confidences == {"high"} and workflow_steps:
        return "high"
    if expected_confidences and not (expected_confidences - {"high", "medium"}):
        return "medium"
    return "low"


def build_prompt_semantics(
    *,
    actions: Sequence[Dict[str, Any]],
    assertions: Sequence[Dict[str, Any]],
    setup: Sequence[Dict[str, Any]],
    code: str,
    title: str,
    goal: str,
) -> Dict[str, Any]:
    lower = code.lower()
    title_lower = title.lower()
    preconditions: List[Dict[str, Any]] = []
    workflow_steps: List[Dict[str, Any]] = []
    expected_results: List[Dict[str, Any]] = []
    prompt_safe_terms: List[str] = []
    warnings: List[str] = []

    event_observer = "addeventlistener" in lower or "hooks.on(" in lower or "exposebinding(" in lower
    event_title = "event" in title_lower or "bubble" in title_lower

    if event_observer:
        _append_text_item(
            preconditions,
            "register a page-level or window-level event observer",
            basis="source_event_listener_or_hook",
            confidence="high",
        )
        prompt_safe_terms.extend(["custom DOM event", "window-level event observer"])

    for item in setup:
        kind = _clean(item.get("kind"))
        if not kind or "event" in kind.lower() or "hook" in kind.lower():
            continue
        _append_text_item(
            preconditions,
            kind,
            basis=_clean(item.get("evidence_basis")) or "source_review_setup",
            confidence="medium",
        )

    for action in actions:
        action_type = _clean(action.get("type")).lower()
        target = _clean(action.get("target_hint"))
        basis = _clean(action.get("evidence_basis")) or "source_review_action"
        text = ""
        safe_detail = ""
        if action_type == "click" and ("navigation" in target.lower() or "clickonlink(" in lower):
            text = "trigger navigation through a visible or internal navigation link"
            safe_detail = "the interaction should cause the app to emit a custom DOM event" if event_observer else ""
            prompt_safe_terms.append("navigation link")
        elif action_type == "navigate":
            text = f"navigate to {target}" if target else "navigate through the relevant application flow"
        elif action_type == "wait":
            text = target or "wait for the application to reach the expected state"
        elif action_type:
            text = f"{action_type} {target or 'the relevant UI control'}"
        if text:
            _append_text_item(
                workflow_steps,
                text,
                basis=basis,
                confidence="high" if action.get("source_layer") == "source_review" else "medium",
                action_type=action_type or "exercise",
                safe_detail=safe_detail,
            )

    if event_observer and event_title:
        _append_expected_result(
            expected_results,
            "a page-level or window-level observer receives the custom event after the interaction",
            channel="event",
            basis="source_event_listener_or_hook_and_title",
            confidence="high",
        )

    for assertion in assertions:
        if _is_generic_assertion(assertion):
            continue
        _append_expected_result(
            expected_results,
            _clean(assertion.get("intent")) or _clean(assertion.get("kind")),
            channel=_clean(assertion.get("kind")).lower() or "ui_state",
            basis=_clean(assertion.get("evidence_basis")) or "source_review_assertion",
            confidence="medium",
        )

    if not expected_results and assertions:
        _append_expected_result(
            expected_results,
            f"verify that {goal}",
            channel="ui_state",
            basis="source_title_derived_from_generic_assertion",
            confidence="low",
        )
        warnings.append("generic_expected_result_derived_from_title")

    confidence = _semantic_confidence(expected_results, workflow_steps)
    needs_manual_review = confidence == "low" or not expected_results or not workflow_steps

    return {
        "scenario_summary": _clean(goal),
        "preconditions": preconditions,
        "user_workflow_steps": workflow_steps,
        "expected_results": expected_results,
        "prompt_safe_terms": sorted({term for term in prompt_safe_terms if term}),
        "blocked_terms": sorted(set(_extract_call_names(code))),
        "semantic_confidence": confidence,
        "needs_manual_review": needs_manual_review,
        "warnings": warnings,
        "abstraction_notes": [
            "Prompt-safe semantics are behavior descriptions; hidden selectors, helper names, exact code, and source paths remain blocked."
        ],
    }


def extract_source_review_semantics(snippet: str, test_name: str, describe_path: Sequence[str]) -> Dict[str, Any]:
    code = strip_numbered_snippet(snippet)
    lower = code.lower()
    scope = " / ".join([str(p) for p in describe_path if str(p).strip()])
    title = f"{scope}: {test_name}" if scope else str(test_name or "")
    title_lower = title.lower()
    actions: List[Dict[str, Any]] = []
    assertions: List[Dict[str, Any]] = []
    setup: List[Dict[str, Any]] = []
    notes: List[str] = []

    goto_target = first_literal_arg("page.goto", code)
    if goto_target:
        append_unique(actions, source_action("navigate", deidentify_path_hint(goto_target), basis="source_page_goto_literal"))
    if "navigatewithswup(" in lower:
        append_unique(actions, source_action("navigate", "a route through the application navigation flow", basis="source_named_navigation_helper"))
    if "clickonlink(" in lower:
        append_unique(actions, source_action("click", "a navigation link", basis="source_named_click_helper"))
    if ".goback(" in lower:
        append_unique(actions, source_action("navigate", "back through browser history", basis="source_page_history_api"))
    if "clickplay(" in lower:
        append_unique(actions, source_action("click", "the media play control", basis="source_named_media_helper"))
    if "clickpause(" in lower:
        append_unique(actions, source_action("click", "the media pause control", basis="source_named_media_helper"))
    if "opensettings(" in lower:
        append_unique(actions, source_action("click", "the media player settings control", basis="source_named_settings_helper"))
    if "opensubmenu(" in lower:
        append_unique(actions, source_action("click", "a media player submenu option", basis="source_named_settings_helper"))
    if ".click(" in lower or "page.click(" in lower:
        append_unique(actions, source_action("click", "the relevant visible control", basis="source_click_call"))
    if ".fill(" in lower:
        append_unique(actions, source_action("input", "the relevant text input", basis="source_fill_call"))
    if "waitforrequest(" in lower:
        append_unique(actions, source_action("wait", "a network request triggered by the interaction", basis="source_wait_for_request"))
    if "scrolltop" in lower or "scrollleft" in lower or "scrolltoposition(" in lower:
        append_unique(actions, source_action("scroll", "the relevant scroll container or page", basis="source_scroll_mutation_or_helper"))
    if "page.mouse.down" in lower and "page.mouse.up" in lower:
        target = "a draggable item"
        if "auto-scroll" in title_lower or "auto scroll" in title_lower:
            target = "a draggable item near the scroll-container edge"
        elif "drag scroll" in title_lower:
            target = "the draggable element while scrolling"
        append_unique(actions, source_action("drag", target, basis="source_mouse_drag_sequence"))
    elif "page.mouse.move" in lower:
        append_unique(actions, source_action("move_pointer", "the relevant pointer target", basis="source_mouse_move_sequence"))
    if ".hover(" in lower:
        append_unique(actions, source_action("hover", "the relevant draggable or interactive item", basis="source_hover_call"))

    if "addeventlistener" in lower or "hooks.on(" in lower or "exposebinding(" in lower:
        setup.append({"kind": "event or hook observer setup", "count": 1, "evidence_basis": "source_event_listener_or_hook"})
    if "waitforselector" in lower:
        setup.append({"kind": "initial element readiness wait", "count": lower.count("waitforselector"), "evidence_basis": "source_wait_for_selector"})

    if "tobeinviewport" in lower:
        assertions.append(source_assertion("viewport assertion", "target content is scrolled into view", basis="source_expect_to_be_in_viewport"))
    if "tobevisible" in lower:
        assertions.append(source_assertion("visibility assertion", "expected UI element is visible", basis="source_expect_to_be_visible"))
    if "tobeattached" in lower:
        assertions.append(source_assertion("dom attachment assertion", "expected UI element is mounted in the DOM", basis="source_expect_to_be_attached"))
    if "tohaveclass" in lower or "nottHaveClass".lower() in lower:
        assertions.append(source_assertion("state/class assertion", "control or page state class reflects expected state", basis="source_expect_to_have_class"))
    if "tohaveattribute" in lower:
        assertions.append(source_assertion("attribute assertion", "control attribute reflects expected state", basis="source_expect_to_have_attribute"))
    if "tocontaintext" in lower:
        assertions.append(source_assertion("text assertion", "expected visible text is present", basis="source_expect_to_contain_text"))
    if "tomatch(/^blob" in lower or "mediasource blob" in title_lower:
        assertions.append(source_assertion("media source assertion", "media source is replaced with a MediaSource blob URL", basis="source_blob_url_assertion"))
    if "waitforrequest" in lower:
        assertions.append(source_assertion("network assertion", "expected network request is fired", basis="source_wait_for_request"))
    if "texttracks" in lower:
        assertions.append(source_assertion("media track assertion", "native text track state matches captions selection", basis="source_text_track_assertion"))
    if ".url()" in lower or "new url(" in lower or "waitforurl" in lower:
        assertions.append(source_assertion("navigation assertion", "browser URL changes to the expected page", basis="source_url_assertion"))
    if "boundingbox(" in lower:
        assertions.append(source_assertion("layout/position assertion", "target element remains present and positioned", basis="source_bounding_box_assertion"))
    if "textcontent(" in lower:
        assertions.append(source_assertion("text/value assertion", "displayed value updates as expected", basis="source_text_content_assertion"))
    if not assertions and "expect(" in lower:
        assertions.append(source_assertion("observable assertion", "expected browser or UI behavior occurs", basis="source_expect_call"))

    if not actions:
        if "renders" in title_lower or "mounted" in title_lower or "exported" in title_lower:
            append_unique(actions, source_action("observe", "the target page or component after it renders", basis="source_title_render_behavior"))
        elif "toggle" in title_lower:
            append_unique(actions, source_action("click", "the relevant toggle control", basis="source_title_toggle_behavior"))

    if any(action.get("type") in {"drag", "scroll"} for action in actions):
        notes.append("Source-reviewed workflow includes pointer/scroll behavior that Phase 2 aggregate events can under-specify.")
    if any(action.get("type") == "click" for action in actions):
        notes.append("Source-reviewed workflow includes click behavior.")

    goal = title or str(test_name or "")
    prompt_semantics = build_prompt_semantics(
        actions=actions,
        assertions=assertions,
        setup=setup,
        code=code,
        title=title,
        goal=goal,
    )
    if prompt_semantics.get("semantic_confidence") == "low":
        notes.append("Prompt semantics are low-confidence and should receive manual enrichment before large RQ6 runs.")

    return {
        "actions": actions,
        "assertions": assertions,
        "setup": setup,
        "notes": notes,
        "prompt_semantics": prompt_semantics,
        "source_review_semantics_available": bool(actions or assertions or setup or prompt_semantics.get("expected_results")),
    }
